import pytest
import torch
from models.embla.loss import softcapped_cross_entropy


@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
@pytest.mark.parametrize('cap',[0.,30.])
def test_chunked_loss_and_gradient(dtype,cap):
    torch.manual_seed(4)
    x=(torch.randn(11,37)*12).to(dtype).requires_grad_()
    reference=x.detach().clone().requires_grad_()
    labels=torch.tensor([1,-100,5,10,0,36,-100,2,2,17,11])
    loss,predictions=softcapped_cross_entropy(x,labels,cap,chunk=3)
    capped=(reference/cap).tanh()*cap if cap else reference
    expected=torch.nn.functional.cross_entropy(capped.float(),labels,ignore_index=-100,reduction='sum')
    torch.testing.assert_close(loss,expected)
    torch.testing.assert_close(predictions,capped.argmax(-1))
    (loss*.17).backward();(expected*.17).backward()
    torch.testing.assert_close(x.grad,reference.grad,rtol=.008 if dtype==torch.bfloat16 else 1e-5,atol=.0005 if dtype==torch.bfloat16 else 1e-7)
    assert not x.grad[labels==-100].any()
