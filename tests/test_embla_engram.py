import torch
from models.embla.engram import TrainableEngram
from models.embla.upstream.configuration_embla import EmblaConfig
from models.embla.upstream.modeling_embla import Engram, EmblaCache


def test_trainable_table_parity_gradient_and_restore():
    cfg = EmblaConfig(hidden_size=32, engram_pages=2, engram_head_dim=64,
                      engram_heads=4, engram_page_heads=4)
    model = TrainableEngram(cfg)
    reference = Engram(cfg)
    reference.load_state_dict({k:v for k,v in model.state_dict().items() if k != 'table'})
    reference.host_table = model.table.detach().clone()
    ids = torch.tensor([[3,4,5,6,7,8]])
    positions = torch.tensor([[0,1,2,0,1,2]])
    x = torch.randn(1,6,32,requires_grad=True)
    embeddings = model.lookup(ids,torch.float32,positions)
    expected = reference.lookup(ids,torch.float32,positions)
    torch.testing.assert_close(embeddings,expected)
    actual = model.read(x,embeddings,positions)
    torch.testing.assert_close(actual,reference.read(x,expected,positions))
    actual.square().sum().backward()
    assert torch.isfinite(model.table.grad).all() and model.table.grad.abs().sum() > 0
    restored = TrainableEngram(cfg)
    restored.load_state_dict(model.state_dict())
    torch.testing.assert_close(restored.lookup(ids,torch.float32,positions), embeddings)


def test_engram_packed_reset():
    cfg = EmblaConfig(hidden_size=32,engram_pages=2,engram_head_dim=64,engram_heads=4,engram_page_heads=4)
    model = TrainableEngram(cfg)
    ids = torch.tensor([[3,4,5,6,7,8]])
    positions = torch.tensor([[0,1,2,0,1,2]])
    packed = model.lookup(ids,torch.float32,positions)
    single = model.lookup(ids[:,3:],torch.float32,positions[:,3:])
    torch.testing.assert_close(packed[:,3:],single)
