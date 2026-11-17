import pytest
import torch

from models.ngram_memory import NGramMemory


@pytest.mark.parametrize("heads", [1, 4])
def test_identity_gradients_and_cache(heads):
    torch.manual_seed(17)
    model = NGramMemory(8, (2, 3), 31, heads, True)
    model.alpha.fill_(1)
    x = torch.randn(2, 7, 8)
    tokens = torch.randint(0, 99, (2, 7))
    positions = torch.arange(7).expand(2, -1)
    assert torch.equal(model(x, tokens, positions), x)
    model(x, tokens, positions).sum().backward()
    assert all(t.grad.abs().sum() > 0 for t in model.tables)
    with torch.no_grad():
        for table in model.tables:
            table.normal_(std=.1)
    model.zero_grad()
    full = model(x, tokens, positions)
    history = {}
    cached = torch.cat([
        model(x[:, i:i+1], tokens[:, i:i+1], positions[:, i:i+1], history)
        for i in range(7)
    ], dim=1)
    torch.testing.assert_close(full, cached)
    full.sum().backward()
    assert model.query.weight.grad.abs().sum() > 0
    assert model.key.weight.grad.abs().sum() > 0
    # A packed reset must match an independently processed new example.
    packed_positions = positions.clone()
    packed_positions[:, 3:] -= 3
    packed = model(x, tokens, packed_positions)
    separate = model(x[:, 3:], tokens[:, 3:], positions[:, :4])
    torch.testing.assert_close(packed[:, 3:], separate)
    changed = tokens.clone()
    changed[:, -1] += 1
    torch.testing.assert_close(model(x, changed, positions)[:, :-1], full[:, :-1])


def test_head_validation_and_budget():
    with pytest.raises(ValueError):
        NGramMemory(8, heads=3)
    a = NGramMemory(8, heads=1)
    b = NGramMemory(8, heads=4)
    assert sum(t.numel() for t in a.tables) == sum(t.numel() for t in b.tables)
