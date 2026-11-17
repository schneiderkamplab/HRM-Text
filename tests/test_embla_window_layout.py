import pytest
import torch
from models.embla.fa4_window import prepare_window_layout


def test_layout_covers_packed_queries_and_preserves_prefix_suffix_alignment():
    spans=[[(0,3),(3,6)],[(0,2),(2,6)]]
    prompt=torch.tensor([[1,1,0,1,1,1],[0,0,1,0,0,0]],dtype=torch.bool)
    plans=prepare_window_layout(spans,prompt,prefix=True)
    torch.testing.assert_close(torch.cat([p['q'] for p in plans]).sort().values,torch.arange(12))
    for p in plans:
        for a,z,c,e in zip(p['cu_q'][:-1],p['cu_q'][1:],p['cu_k'][:-1],p['cu_k'][1:]):
            q=p['q'][a:z];k=p['k'][c:e]
            if p['causal']:torch.testing.assert_close(q,k[-len(q):])
            else:
                torch.testing.assert_close(q,k)
                assert prompt.flatten()[q].all()


def test_layout_rejects_noncontiguous_prompts():
    with pytest.raises(ValueError,match='contiguous'):
        prepare_window_layout([[(0,3)]],torch.tensor([[True,False,True]]),prefix=True)
