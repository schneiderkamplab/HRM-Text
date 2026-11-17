import copy
import pytest
import torch
from models.lm_head import LMHead

class Core(torch.nn.Module):
    def __init__(self):
        super().__init__();self.proj=torch.nn.Linear(8,8);self.head_hint={'in':{'dim':8,'init_std':.02},'out':{'dim':8,'init_std':.02}}
        self.create_cache=lambda **k:None;self.compute_train_extra_args=lambda *a:{}
    def forward(self,carry,x,**kwargs):return carry,self.proj(x)

@pytest.mark.parametrize('goldfish',[False,True])
@pytest.mark.parametrize('masked',[False,True])
def test_selected_head_preserves_loss_metrics_and_gradients(masked,goldfish):
    torch.manual_seed(41);a=LMHead(Core(),{'vocab_size':32,'goldfish_strategy':'hash' if goldfish else None,'goldfish_k':2});b=copy.deepcopy(a);b.target_head_only=True
    labels=torch.tensor([2,3,4,5,6,7]);labels[::2]=-100 if masked else 2
    batch={'inputs':torch.arange(6),'labels':labels,'cu_seqlens':torch.tensor([0,3,6])}
    _,x,xm=a(None,batch);_,y,ym=b(None,batch)
    torch.testing.assert_close(x,y)
    for k in xm:
        for p,q in zip(xm[k],ym[k]):torch.testing.assert_close(p,q)
    x.backward();y.backward()
    for p,q in zip(a.parameters(),b.parameters()):torch.testing.assert_close(p.grad,q.grad,atol=1e-7,rtol=1e-5)
    no_labels={k:v for k,v in batch.items() if k!='labels'}
    torch.testing.assert_close(a(None,no_labels)[1],b(None,no_labels)[1])


def test_selected_head_all_ignored_is_finite_zero():
    m=LMHead(Core(),{'vocab_size':32,'target_head_only':True})
    _,loss,metrics=m(None,{'inputs':torch.arange(6),'labels':torch.full((6,),-100),'cu_seqlens':torch.tensor([0,3,6])})
    assert loss==0 and metrics['loss'][1]==0
    loss.backward()
    assert all(torch.isfinite(p.grad).all() and not p.grad.any() for p in m.parameters())
