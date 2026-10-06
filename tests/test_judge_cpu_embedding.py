import torch

from scripts.transformers_openai_server import CPUEmbedding


def test_cpu_embedding_preserves_lookup_values_and_dtype():
    embedding = torch.nn.Embedding(10, 8).to(torch.bfloat16)
    ids = torch.tensor([[1, 3, 7]])
    expected = embedding(ids)
    wrapped = CPUEmbedding(embedding)
    actual = wrapped(ids)
    assert torch.equal(actual, expected)
    assert actual.dtype == expected.dtype
    assert wrapped.embedding.weight.device.type == 'cpu'
