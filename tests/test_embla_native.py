import torch
from models.baselines.embla import Embla, EmblaLMHead
from test_embla_model import tiny_config


def test_native_shifted_loss_and_padding():
    cfg = {'embla_config':tiny_config().to_dict(),'vocab_size':64,'attn_type':'prefixlm'}
    model = Embla(cfg)
    head = EmblaLMHead(model,cfg)
    batch = dict(inputs=torch.tensor([1,2,3,4,5,0,0]),labels=torch.tensor([-100,3,4,-100,6,-100,-100]),
                 position_ids=torch.tensor([0,1,2,0,1,0,0]),cu_seqlens=torch.tensor([0,3,5,7]),
                 prefix_lens=torch.tensor([2,2,0]),total_seqlen=torch.tensor(5))
    _,loss,metrics = head(None,batch)
    expected_logits = model(batch['inputs'][:5][None],position_ids=batch['position_ids'][:5][None],
                            prompt_mask=torch.tensor([[True,True,False,True,True]]))[0]
    expected = torch.nn.functional.cross_entropy(expected_logits.float(),batch['labels'][:5])
    torch.testing.assert_close(loss,expected)
    loss.backward()
    assert metrics['accuracy'][1] == 3
    assert model.engram.table.grad.abs().sum() > 0


def test_target_head_only_preserves_loss_metrics_and_gradients():
    import copy
    cfg={'embla_config':tiny_config().to_dict(),'vocab_size':64,'attn_type':'prefixlm'}
    for labels in [torch.tensor([-100,3,4,-100,6]),torch.full((5,),-100)]:
        torch.manual_seed(77)
        reference=EmblaLMHead(Embla(cfg),cfg);candidate=copy.deepcopy(reference);candidate.target_head_only=True
        batch=dict(inputs=torch.tensor([1,2,3,4,5]),labels=labels,position_ids=torch.tensor([0,1,2,0,1]),cu_seqlens=torch.tensor([0,3,5]),prefix_lens=torch.tensor([2,1]),total_seqlen=torch.tensor(5))
        _,a,am=reference(None,batch);_,b,bm=candidate(None,batch)
        torch.testing.assert_close(a,b);assert am.keys()==bm.keys()
        for key in am:
            for x,y in zip(am[key],bm[key]):torch.testing.assert_close(x,y)
        a.backward();b.backward()
        for x,y in zip(reference.parameters(),candidate.parameters()):
            assert (x.grad is None)==(y.grad is None)
            if x.grad is not None:torch.testing.assert_close(x.grad,y.grad,atol=1e-6,rtol=1e-4)
