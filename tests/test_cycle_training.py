"""Exercise real baseline attention, optimizer, accumulation and checkpoint contracts."""
import copy
import io
import random
import numpy as np
import pytest
import torch
from models.cycle_schedule import BASELINE, cycle_contract, validate_cycle_resume, step_schemes
from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModel
from models.lm_head import LMHead
from models.module_learning_rates import configured_module_rates, update_auto_module_rates
from pretrain import PretrainConfig, TrainState, train_accumulated_batches, prewarm_cycle_variants
from models.adam_atan2 import AdamATan2
from models.accelerator import set_accelerator_type


def config(mode='full_budget', attention='causal', budget=5):
    return PretrainConfig(arch=dict(name=BASELINE,head='lm_head@LMHead',
        n_layers=2,half_layers=True,hidden_size=16,num_heads=2,expansion=1.,
        H_cycles=2,L_cycles=3,bp_min_steps=2,bp_max_steps=budget,bp_warmup_ratio=.1,
        cycle_variants=mode,attn_type=attention,init_type='fixed_normal',init_std=.02,
        norm_type='pre',norm_eps=1e-6,pos_emb_type='rope',rope_theta=10000.),
        data=dict(path='unused'),global_batch_size=12,epochs=1,gradient_accumulation_steps=2,
        lr=3e-4,lr_min_ratio=1.,lr_warmup_steps=0,weight_decay=.1,beta1=.9,beta2=.95,
        fwd_bwd_dtype='float32',distributed_strategy='none',accelerator_type='cpu',ema=.99)


def state(c):
    set_accelerator_type('cpu')
    a=c.arch.model_dump() | dict(max_seq_len=8,vocab_size=32,fwd_bwd_dtype='float32')
    m=LMHead(HierarchicalReasoningModel(a),a)
    o=AdamATan2(m.parameters(),lr=c.lr,ema=c.ema,weight_decay=c.weight_decay)
    return TrainState(m,None,o,1,100,torch.float32,False)


def batch(valid=4, attention='causal'):
    ids=torch.tensor([1,7,8,2,3,4]); labels=torch.tensor([-100]*(6-valid)+[1]*valid)
    b=dict(inputs=ids,labels=labels,position_ids=torch.arange(6),
           prefix_lens=torch.tensor([2],dtype=torch.int32),causal_lens=torch.tensor([4],dtype=torch.int32),
           cu_seqlens=torch.tensor([0,6],dtype=torch.int32),total_seqlen=torch.tensor(6),
           numseqs=torch.tensor(1),max_seqlen_prefix=torch.tensor(2),max_seqlen_causal=torch.tensor(4),max_seqlen_all=torch.tensor(6))
    if attention=='mixedlm':
        from models.mixedlm import routing
        b.update(routing([np.array([1,7,8])],[3],[7,8]))
    return b


@pytest.fixture(autouse=True)
def single_thread():
    old=torch.get_num_threads();torch.set_num_threads(1)
    yield
    torch.set_num_threads(old)


@pytest.mark.parametrize('attention',['causal','prefixlm','mixedlm'])
@pytest.mark.parametrize('scheme',[(1,1),(2,3),(4,3),(1,15)])
def test_override_matches_fixed_depth_gradients(attention,scheme):
    c=config(attention=attention); s=state(c); ref=copy.deepcopy(s.model)
    h,l=scheme;ref.model.H_cycles=h;ref.model.L_cycles=l
    x=batch(attention=attention)
    _,loss,_=s.model(None,x,H_cycles=h,L_cycles=l,bp_steps=h*(l+1))
    _,other,_=ref(None,x,bp_steps=h*(l+1))
    loss.backward();other.backward()
    torch.testing.assert_close(loss,other,rtol=0,atol=0)
    for p,q in zip(s.model.parameters(),ref.parameters()):
        assert p.grad is not None
        torch.testing.assert_close(p.grad,q.grad,rtol=0,atol=0)
    assert (s.model.model.H_cycles,s.model.model.L_cycles)==(2,3)


def test_accumulation_matches_manual_weighted_update():
    c=config();s=state(c);r=state(c);r.model.load_state_dict(s.model.state_dict())
    batches=[batch(2),batch(4)]
    schemes=step_schemes(c,s.step,2,5)
    h=sum(w*x for w,(x,y) in zip((1/3,2/3),schemes))
    l=sum(w*x*y for w,(x,y) in zip((1/3,2/3),schemes))
    update_auto_module_rates(c,r.model,r.optim,5,(h,l))
    for b,(x,y),w in zip(batches,schemes,(1/3,2/3)):
        (_,loss,_)=r.model(None,b,H_cycles=x,L_cycles=y,bp_steps=x*(y+1))
        (loss*w).backward()
    r.optim.step()
    metrics,_=train_accumulated_batches(c,0,s,batches,False,bp_steps=5)
    assert metrics['cycles/h_calls'][0].item()==pytest.approx(h)
    for p,q in zip(s.model.parameters(),r.model.parameters()):torch.testing.assert_close(p,q,rtol=0,atol=0)


def test_disabled_and_diagnostic_replay():
    c=config('off');s=state(c);r=state(c);r.model.load_state_dict(s.model.state_dict())
    for st in (s,r):update_auto_module_rates(c,st.model,st.optim,5)
    train_accumulated_batches(c,0,s,[batch()],False,bp_steps=5,optimizer_step_enabled=False)
    train_accumulated_batches(c,0,s,[batch()],False,bp_steps=5)
    train_accumulated_batches(c,0,r,[batch()],False,bp_steps=5)
    for p,q in zip(s.model.parameters(),r.model.parameters()):torch.testing.assert_close(p,q,rtol=0,atol=0)
    assert not any('cycle' in k for k in cycle_contract(c) if k!='mode')


def test_disk_restart_exact_replay():
    c=config();s=state(c)
    train_accumulated_batches(c,0,s,[batch(2),batch()],False,bp_steps=5)
    f=io.BytesIO();torch.save(dict(model=s.model.state_dict(),optim=s.optim.state_dict(),step=s.step),f);f.seek(0)
    saved=torch.load(f,weights_only=True);r=state(c);r.model.load_state_dict(saved['model']);r.optim.load_state_dict(saved['optim']);r.step=saved['step']
    for st in (s,r):
        st.step+=1;train_accumulated_batches(c,0,st,[batch(2),batch()],False,bp_steps=5)
    for p,q in zip(s.model.parameters(),r.model.parameters()):
        torch.testing.assert_close(p,q,rtol=0,atol=0)
        for k,v in s.optim.state[p].items():torch.testing.assert_close(v,r.optim.state[q][k],rtol=0,atol=0)


def test_contract_and_config_validation():
    c=config();old=cycle_contract(c,100)
    validate_cycle_resume(old,cycle_contract(c,100))
    for change in ({'seed':8},{'gradient_accumulation_steps':3}):
        with pytest.raises(ValueError,match='contract changed'):validate_cycle_resume(old,cycle_contract(c.model_copy(update=change),100))
    with pytest.raises(ValueError):validate_cycle_resume({'mode':'off'},old)
    validate_cycle_resume({'mode':'off'},old,True)
    validate_cycle_resume({'mode':'off'},cycle_contract(config('off')))
    for overrides in (dict(cycle_variants='bad'),dict(cycle_sampler_version=2),dict(bp_min_steps=1),dict(name='baselines.hrm_v2@HierarchicalReasoningModel')):
        d=c.model_dump();d['arch'].update(overrides)
        with pytest.raises(ValueError):PretrainConfig(**d)


def test_prewarm_preserves_state_and_batches(monkeypatch):
    import pretrain
    c=config();s=state(c);batches=[batch(2),batch()]
    optim_before=copy.deepcopy(s.optim.state_dict())
    before=copy.deepcopy(s.model.state_dict());rng=torch.get_rng_state();py=random.getstate();npstate=np.random.get_state()
    for p in s.model.parameters():p.grad=torch.ones_like(p)
    grads=[p.grad.clone() for p in s.model.parameters()]
    seen=[]
    def back(st,b,scale,**kw):
        seen.append((kw['H_cycles'],kw['L_cycles']))
        return pretrain.forward_backward_batch_uncompiled(st,b,scale,**kw)
    monkeypatch.setattr(pretrain,'compiled_forward_backward_batch',lambda mode:back)
    report=prewarm_cycle_variants(c,s,batches)
    assert len(report['schemes'])==5 and len(seen)==10
    assert s.step==1
    for key,values in optim_before["state"].items():
        for name,value in values.items():
            torch.testing.assert_close(value,s.optim.state_dict()["state"][key][name],rtol=0,atol=0)
    assert torch.equal(rng,torch.get_rng_state()) and py==random.getstate()
    assert np.array_equal(npstate[1],np.random.get_state()[1])
    for k,v in s.model.state_dict().items():torch.testing.assert_close(v,before[k],rtol=0,atol=0)
    for p,g in zip(s.model.parameters(),grads):torch.testing.assert_close(p.grad,g,rtol=0,atol=0)
    assert prewarm_cycle_variants(c,s,batches) is None
    assert batches[0]['labels'].tolist()==[-100]*4+[1]*2


def test_actual_compiled_step_and_prewarm(monkeypatch):
    import pretrain
    c=config(budget=4);s=state(c);r=state(c);r.model.load_state_dict(s.model.state_dict())
    compiled=torch.compile(pretrain.forward_backward_batch_uncompiled,backend='aot_eager',dynamic=False)
    monkeypatch.setattr(pretrain,'compiled_forward_backward_batch',lambda mode:compiled)
    prewarm_cycle_variants(c,s,[batch(2),batch()])
    for step in (1,2,3):
        for st,use in ((s,True),(r,False)):
            st.step=step
            train_accumulated_batches(c,0,st,[batch(2),batch()],use,bp_steps=4)
    for p,q in zip(s.model.parameters(),r.model.parameters()):torch.testing.assert_close(p,q,rtol=1e-5,atol=1e-7)


def test_metadata_roundtrip_and_cache_rejection(tmp_path):
    import json
    from pretrain import save_checkpoint_metadata
    c=config();c.checkpoint_path=str(tmp_path);s=state(c)
    save_checkpoint_metadata(c,s,'step_1',1,2,0,'step',6,carry_policy='none')
    saved=json.loads((tmp_path/'checkpoint_state_step_1.json').read_text())
    assert saved['cycle_sampling']==cycle_contract(c,s.total_steps)
    with pytest.raises(ValueError,match='inference caches'):
        s.model.model(None,torch.zeros(6,16),cache={},H_cycles=1,L_cycles=1)
    with pytest.raises(ValueError,match='Both cycle overrides'):
        s.model.model(None,torch.zeros(6,16),H_cycles=1)


def test_diagnostic_replay_keeps_actual_lr_and_draws():
    c=config();s=state(c);r=state(c);r.model.load_state_dict(s.model.state_dict())
    # A preceding step populated effective LR counts; diagnostics may not replace them.
    update_auto_module_rates(c,s.model,s.optim,5,(1.,4.))
    cached=s.optim._auto_lr_bp_steps
    shadow,_=train_accumulated_batches(c,0,s,[batch(1),batch(2)],False,bp_steps=5,optimizer_step_enabled=False)
    assert s.optim._auto_lr_bp_steps==cached
    actual,_=train_accumulated_batches(c,0,s,[batch(2),batch(4)],False,bp_steps=5)
    train_accumulated_batches(c,0,r,[batch(2),batch(4)],False,bp_steps=5)
    assert {k:v[0].item() for k,v in shadow.items() if 'draw_' in k}=={k:v[0].item() for k,v in actual.items() if 'draw_' in k}
    for p,q in zip(s.model.parameters(),r.model.parameters()):torch.testing.assert_close(p,q,rtol=0,atol=0)


def test_real_checkpoint_guard_before_loading(tmp_path):
    import yaml
    from pretrain import save_train_checkpoint,load_train_checkpoint
    c=config();c.checkpoint_path=str(tmp_path);c.checkpoint_format='unsharded'
    s=state(c);train_accumulated_batches(c,0,s,[batch(2),batch()],False,bp_steps=5)
    (tmp_path/'all_config.yaml').write_text(yaml.safe_dump(c.model_dump()))
    save_train_checkpoint(c,s,'step_1',1,2,0,local_batch_size=6)
    c.resume_checkpoint_path=str(tmp_path);c.resume_checkpoint_tag='step_1'
    r=state(c);load_train_checkpoint(c,r,0,6)
    for p,q in zip(s.model.parameters(),r.model.parameters()):torch.testing.assert_close(p,q,rtol=0,atol=0)
    c.arch.cycle_variant_seed=99
    with pytest.raises(ValueError,match='sampling contract changed'):load_train_checkpoint(c,r,0,6)
    c.cycle_variants_allow_resume_change=True
    load_train_checkpoint(c,r,0,6)
    assert r._cycle_resume_contract_change['current']['seed']==99


def test_nominal_export_ignores_training_mixture():
    from types import SimpleNamespace
    from conversion.convert_to_hf import build_hf_config
    c=config(budget=16)
    arch=c.arch.model_dump()|dict(vocab_size=32,max_seq_len=8,fwd_bwd_dtype='float32')
    tokenizer=SimpleNamespace(pad_token_id=0)
    exported=build_hf_config(arch,tokenizer)
    assert (exported['H_cycles'],exported['L_cycles'])==(2,3)
    disabled=build_hf_config(arch|dict(cycle_variants='off'),tokenizer)
    assert exported==disabled
