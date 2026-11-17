"""Full-model kernel parity across causal/PrefixLM and four decoder loops."""
import sys,json,copy,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch
from models.embla.model import EmblaTrainingModel
spec=importlib.util.spec_from_file_location('test_embla_model',ROOT/'tests/test_embla_model.py');tests=importlib.util.module_from_spec(spec);spec.loader.exec_module(tests)

def main():
 torch.set_num_threads(4);torch.cuda.set_per_process_memory_fraction(.03);results=[]
 for flag in ['fa4_window','fused_relu','fused_sparse','single_topk']:
  prefix,loops=False,1
  torch.manual_seed(83);cfg=tests.tiny_config();cfg.hidden_size=128;cfg.head_dim=64;cfg.num_attention_heads=2;cfg.num_key_value_heads=1;cfg.sliding_num_attention_heads=2;cfg.sliding_num_key_value_heads=1;cfg.sliding_window=32
  ref=EmblaTrainingModel(cfg,prefix_lm=prefix,decoder_loops=loops).cuda().bfloat16()
  opt=copy.deepcopy(ref);setattr(opt,flag,True)
  ids=torch.randint(0,64,(1,137),device='cuda');pos=torch.arange(137,device='cuda')[None]%71;prompt=pos<33
  a=ref(ids,position_ids=pos,prompt_mask=prompt);b=opt(ids,position_ids=pos,prompt_mask=prompt)
  a.float().square().mean().backward();b.float().square().mean().backward()
  out_error=float((a.float()-b.float()).norm()/a.float().norm())
  denom=diff=0.
  for x,y in zip(ref.parameters(),opt.parameters()):
   assert (x.grad is None)==(y.grad is None)
   if x.grad is not None:
    assert torch.isfinite(y.grad).all()
    diff+=float((x.grad.float()-y.grad.float()).square().sum());denom+=float(x.grad.float().square().sum())
  error=(diff/denom)**.5
  print(json.dumps(dict(flag=flag,out=out_error,grad=error)),flush=True)
  # Packed future answer isolation is required for both objectives.
  changed=ids.clone();changed[0,70]=(changed[0,70]+1)%64
  with torch.no_grad():
   before=opt(ids,position_ids=pos,prompt_mask=prompt);after=opt(changed,position_ids=pos,prompt_mask=prompt)
   torch.testing.assert_close(before[:,:70],after[:,:70],atol=0,rtol=0)
   torch.testing.assert_close(before[:,71:],after[:,71:],atol=0,rtol=0)
  result=dict(prefix=prefix,loops=loops,output_relative_l2=out_error,parameter_gradient_relative_l2=error,passed=True);results.append(result);print(json.dumps(result),flush=True)
 (ROOT/'logs/diagnostics/embla/fused-model-component-tests.json').write_text(json.dumps(results,indent=2))
if __name__=='__main__':main()
