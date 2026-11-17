"""Small compiled GPU training smoke plus real DFM11 loader label/routing check."""
import json,copy
from pathlib import Path
import numpy as np
import torch
from dataset_new import V1Dataset,V1DatasetConfig,V1DatasetIndices
from models.baselines.transformer_wrapper import TransformerWrapper
from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModel
from models.lm_head import LMHead
from models.mixedlm import routing
from models.common import prepare_prefixlm_batch,wrap_tensor

def main():
    ds=V1Dataset(V1DatasetConfig(seed=0,dataset_path='data/sampled_dfm11',batch_max_length=32768,drop_last_batch=True,target_only=True,mixed_lm=True,rank=0,num_replicas=8))
    root=Path(ds.config.dataset_path);ds._data=np.load(root/'tokens.npy',mmap_mode='r');ds._data_indices=V1DatasetIndices(**{k:np.load(root/'epoch_0'/f'{k}.npy',mmap_mode='r') for k in ('inst_start','inst_len','resp_start','resp_len')})
    indices=np.arange(4);batch,scalars=ds._load_batch(indices);ds.config.mixed_lm=False;ordinary,_=ds._load_batch(indices)
    for k,v in ordinary.items():assert torch.equal(v,batch[k]),k
    used=int(sum(ds._data_indices.inst_len[indices]+ds._data_indices.resp_len[indices]-1))
    allq=torch.cat([batch['mixed_prefix_q'],batch['mixed_answer_q']]);assert torch.equal(allq.sort().values,torch.arange(used))
    from transformers import AutoTokenizer
    tok=AutoTokenizer.from_pretrained(str(Path(ds.metadata.tokenizer_info['tokenizer_path']).parent),local_files_only=True)
    assert tok.encode('<|turn>model\n',add_special_tokens=False)==ds._mixed_header
    losses=[]
    for recurrent in (False,True):
        cfg=dict(name='baselines.hrm_nocarry_bp_warmup@HierarchicalReasoningModel' if recurrent else 'baselines.transformer_wrapper@TransformerWrapper',n_layers=2,half_layers=True,hidden_size=128,num_heads=4,H_cycles=2,L_cycles=3,bp_min_steps=2,bp_max_steps=8,bp_warmup_ratio=.1,fwd_bwd_dtype='bfloat16',expansion=4.,attn_type='mixedlm',init_type='fixed_normal',init_std=.02,norm_type='pre',norm_eps=1e-6,pos_emb_type='rope',rope_theta=10000.,max_seq_len=128,vocab_size=64)
        model=LMHead(HierarchicalReasoningModel(cfg) if recurrent else TransformerWrapper(cfg),cfg).cuda().bfloat16();compiled=torch.compile(model);opt=torch.optim.AdamW(model.parameters(),lr=.0003)
        for step,prompt in enumerate(([1,7,8,2,3,7,8],[1,7,8],[1,7,8,3,7,8])):
            ids=torch.tensor(prompt+[4,5],device='cuda');routes={k:v.cuda() for k,v in routing([np.array(prompt)],[2],[7,8]).items()}
            for v in routes.values():torch._dynamo.mark_dynamic(v,0)
            _,logits=compiled(None,{'inputs':ids,'position_ids':torch.arange(len(ids),device='cuda'),**routes},**({'bp_steps':2 if step==0 else 8} if recurrent else {}))
            loss=logits[-3:].float().square().mean();loss.backward();assert torch.isfinite(loss)
            bad=[(n,'missing' if p.grad is None else 'nonfinite') for n,p in model.named_parameters() if p.grad is None or not torch.isfinite(p.grad).all()];assert bad==([('embed_tokens.embedding_weight','missing')] if recurrent and step==0 else []),(recurrent,step,bad);opt.step();opt.zero_grad();losses.append(float(loss.detach()))
    torch.cuda.synchronize()
    result={'passed':True,'real_sample_rows':len(indices),'real_tokens':used,'header_tokens':ds._mixed_header,'compiled_optimizer_steps':len(losses),'losses':losses,'peak_gpu_bytes':torch.cuda.max_memory_allocated()}
    Path('logs/diagnostics/mixedlm-20261115/training-smoke.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
