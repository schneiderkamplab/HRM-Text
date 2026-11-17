import torch
from models.embla.model import EmblaTrainingModel
from models.embla.upstream.configuration_embla import EmblaConfig
from models.embla.upstream.modeling_embla import EmblaForCausalLM


def tiny_config():
    return EmblaConfig(vocab_size=64,hidden_size=32,head_dim=8,num_hidden_layers=8,num_prefill_layers=4,
        layer_types=['sliding_attention','full_attention','sliding_attention','sliding_attention',
                     'full_attention','sparse_attention','full_attention','sparse_attention'],
        kv_sources={1:1,4:4,6:1},attn_res_block=2, num_attention_heads=4,num_key_value_heads=2,
        sliding_num_attention_heads=4,sliding_num_key_value_heads=2,sliding_window=3,
        intermediate_size=32,num_experts=4,num_experts_per_tok=2,moe_intermediate_size=16,
        shared_expert_intermediate_size=16,engram_pages=2,engram_head_dim=64,engram_heads=4,
        engram_page_heads=4,sparse_topk=3,sparse_recent=2,use_cache=False)


def test_full_model_upstream_parity():
    torch.manual_seed(11)
    cfg = tiny_config()
    ours = EmblaTrainingModel(cfg)
    upstream = EmblaForCausalLM(cfg)
    upstream.load_state_dict({k:v for k,v in ours.state_dict().items() if k != 'engram.table'})
    upstream.engram.host_table = ours.engram.table.detach().clone()
    ids = torch.tensor([[1,2,3,4,5,6]])
    pos = torch.tensor([[0,1,2,0,1,2]])
    actual = ours(ids,position_ids=pos)
    expected = upstream(ids,position_ids=pos,use_cache=False).logits
    torch.testing.assert_close(actual,expected,atol=2e-6,rtol=2e-5)
    actual.square().sum().backward()
    assert ours.engram.table.grad.abs().sum() > 0
    assert all(torch.isfinite(p.grad).all() for p in ours.parameters() if p.grad is not None)


def test_loop_full_backprop_and_kv_projection_once():
    model = EmblaTrainingModel(tiny_config(),decoder_loops=4,prefix_lm=True)
    calls = []
    handle = model.transformer.h[4].attn.c_k.register_forward_hook(lambda *args: calls.append(1))
    ids = torch.tensor([[1,2,3,4,5,6]])
    out = model(ids,prompt_mask=torch.tensor([[True,True,True,False,False,False]]))
    out.sum().backward()
    handle.remove()
    assert len(calls) == 1
    assert model.transformer.h[4].attn.c_q.weight.grad.abs().sum() > 0
    assert model.transformer.h[0].attn.c_q.weight.grad.abs().sum() > 0
    assert torch.isfinite(out).all()


def test_prefix_future_answer_isolation():
    model = EmblaTrainingModel(tiny_config(),decoder_loops=2,prefix_lm=True)
    ids = torch.tensor([[1,2,3,4,5,6]])
    prompt = torch.tensor([[True,True,True,False,False,False]])
    before = model(ids,prompt_mask=prompt)
    changed = ids.clone(); changed[0,-1] = 9
    after = model(changed,prompt_mask=prompt)
    torch.testing.assert_close(before[:,:-1],after[:,:-1])


def test_bfloat16_autocast_optimizer_and_checkpoint(tmp_path):
    model = EmblaTrainingModel(tiny_config(),decoder_loops=2,prefix_lm=True)
    optim = torch.optim.AdamW(model.parameters(),lr=3e-4)
    ids = torch.tensor([[1,2,3,4,5,6]])
    prompt = torch.tensor([[True,True,True,False,False,False]])
    for _ in range(2):
        optim.zero_grad()
        with torch.autocast('cpu',dtype=torch.bfloat16):
            out = model(ids,prompt_mask=prompt)
            loss = torch.nn.functional.cross_entropy(out[:,2:].float().reshape(-1,64),ids[:,2:].reshape(-1))
        loss.backward()
        assert torch.isfinite(loss)
        assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
        optim.step()
    path=tmp_path/'checkpoint.pt'
    torch.save({'model':model.state_dict(),'optimizer':optim.state_dict()},path)
    restored=EmblaTrainingModel(tiny_config(),decoder_loops=2,prefix_lm=True)
    restored_optim=torch.optim.AdamW(restored.parameters(),lr=3e-4)
    saved=torch.load(path,weights_only=True)
    restored.load_state_dict(saved['model']);restored_optim.load_state_dict(saved['optimizer'])
    with torch.autocast('cpu',dtype=torch.bfloat16):
        torch.testing.assert_close(restored(ids,prompt_mask=prompt),model(ids,prompt_mask=prompt),atol=0,rtol=0)


@torch.no_grad()
def test_incremental_cache_matches_recomputation():
    from models.embla.upstream.modeling_embla import EmblaCache
    for prefix,loops in [(False,1),(True,1),(True,4)]:
        model=EmblaTrainingModel(tiny_config(),prefix_lm=prefix,decoder_loops=loops).eval()
        cache=EmblaCache()
        ids=torch.tensor([[1,2,3]])
        prompt=torch.ones_like(ids,dtype=torch.bool) if prefix else None
        actual=model(ids,prompt_mask=prompt,cache=cache)
        torch.testing.assert_close(actual,model(ids,prompt_mask=prompt),atol=1e-6,rtol=1e-5)
        for token in (4,5,6):
            ids=torch.cat((ids,torch.tensor([[token]])),-1)
            actual=model(ids[:,-1:],prompt_mask=torch.zeros(1,1,dtype=torch.bool) if prefix else None,cache=cache)
            mask=torch.arange(ids.shape[1])[None]<3 if prefix else None
            expected=model(ids,prompt_mask=mask)[:,-1:]
            torch.testing.assert_close(actual,expected,atol=2e-6,rtol=2e-5)
            assert cache.seen == ids.shape[1]
            assert all(k.shape[1] == ids.shape[1] for k,kn,v in cache.full.values())
            assert all(k.shape[1] <= model.config.sliding_window-1 for k,v in cache.sliding.values())


@torch.no_grad()
def test_early_prefill_and_subsequent_decode_parity():
    from models.embla.upstream.modeling_embla import EmblaCache
    for prefix,loops in [(False,1),(True,1),(True,4)]:
        model=EmblaTrainingModel(tiny_config(),prefix_lm=prefix,decoder_loops=loops).eval()
        ids=torch.tensor([[1,2,3,4,5]])
        prompt=torch.ones_like(ids,dtype=torch.bool) if prefix else None
        full_cache,early_cache=EmblaCache(),EmblaCache()
        lengths=[]
        handle=model.transformer.h[4].attn.c_q.register_forward_pre_hook(lambda module,args:lengths.append(args[0].shape[1]))
        early=model(ids,prompt_mask=prompt,cache=early_cache,last_token_only=True)
        handle.remove()
        assert lengths == [1]*loops
        full=model(ids,prompt_mask=prompt,cache=full_cache)[:,-1:]
        torch.testing.assert_close(early,full,atol=2e-6,rtol=2e-5)
        assert early_cache.seen == full_cache.seen == 5
        for i in early_cache.full:
            for a,b in zip(early_cache.full[i],full_cache.full[i]):torch.testing.assert_close(a,b)
        next_ids=torch.tensor([[6]])
        next_prompt=torch.zeros_like(next_ids,dtype=torch.bool) if prefix else None
        a=model(next_ids,prompt_mask=next_prompt,cache=early_cache)
        b=model(next_ids,prompt_mask=next_prompt,cache=full_cache)
        torch.testing.assert_close(a,b,atol=2e-6,rtol=2e-5)


def test_recomputation_preserves_looped_parameter_gradients(monkeypatch):
    import copy
    import torch.utils.checkpoint
    torch.manual_seed(81)
    model = EmblaTrainingModel(tiny_config(),decoder_loops=4,prefix_lm=True)
    reference = copy.deepcopy(model)
    ids = torch.tensor([[1,2,3,4,5,6]])
    prompt = torch.tensor([[True,True,True,False,False,False]])
    actual = model(ids,prompt_mask=prompt)
    actual.square().sum().backward()
    with monkeypatch.context() as patch:
        def direct(function,*args,**kwargs):
            kwargs.pop('use_reentrant',None)
            return function(*args,**kwargs)
        patch.setattr(torch.utils.checkpoint,'checkpoint',direct)
        expected = reference(ids,prompt_mask=prompt)
        expected.square().sum().backward()
    torch.testing.assert_close(actual,expected,rtol=0,atol=0)
    for (name,p),(_,q) in zip(model.named_parameters(),reference.named_parameters()):
        assert (p.grad is None)==(q.grad is None),name
        if p.grad is not None:
            torch.testing.assert_close(p.grad,q.grad,rtol=1e-5,atol=1e-6,msg=name)
