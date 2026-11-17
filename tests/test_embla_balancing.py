import torch
import pytest
from models.embla.balancing import radix_quantile


def test_radix_exact_bfloat_quantiles():
    torch.manual_seed(7)
    margins = torch.randn(111,13).to(torch.bfloat16)
    for q in [0.,.25,.5,.875,1.]:
        expected = torch.quantile(margins.float(),q,dim=0,interpolation='lower')
        torch.testing.assert_close(radix_quantile(margins,q),expected,rtol=0,atol=0)


def test_accumulator_combines_calls_and_updates_once():
    from models.embla.balancing import RouterBalanceAccumulator
    from models.embla.upstream.modeling_embla import MoE
    from models.embla.upstream.configuration_embla import EmblaConfig
    cfg = EmblaConfig(hidden_size=8,num_experts=4,num_experts_per_tok=2,moe_intermediate_size=8,shared_expert_intermediate_size=8)
    moe = MoE(cfg)
    for p in moe.parameters():
        torch.nn.init.normal_(p,std=.02)
    accumulator = RouterBalanceAccumulator(moe)
    accumulator.begin()
    moe(torch.randn(1,3,8));moe(torch.randn(1,5,8))
    assert len(accumulator.margins) == 2
    assert not moe.expert_bias.any()
    values = torch.cat(accumulator.margins).float()
    expected = torch.quantile(values,.5,dim=0,interpolation='lower')
    accumulator.apply()
    torch.testing.assert_close(moe.expert_bias,expected-expected.mean())
    assert not accumulator.margins and accumulator.handle is None


def _distributed_quantile_worker(rank,path):
    import torch.distributed as dist
    dist.init_process_group('gloo',init_method='file://'+path,rank=rank,world_size=2)
    try:
        torch.manual_seed(34)
        full = torch.randn(37,7).to(torch.bfloat16)
        local = full[:3] if rank == 0 else full[3:]
        expected = torch.quantile(full.float(),.75,dim=0,interpolation='lower')
        torch.testing.assert_close(radix_quantile(local,.75),expected,rtol=0,atol=0)
        if rank == 1:
            local[0,0] = float('nan')
        with pytest.raises(ValueError, match='finite'):
            radix_quantile(local,.75)
    finally:
        dist.destroy_process_group()


def test_distributed_uneven_partitions(tmp_path):
    torch.multiprocessing.spawn(_distributed_quantile_worker,args=(str(tmp_path/'rendezvous'),),nprocs=2,join=True)
