"""Prepare reviewable candidate configs; never modifies the scheduler or qualifies them."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch,yaml
from models.embla.upstream.configuration_embla import EmblaConfig
from models.embla.model import EmblaTrainingModel


def scaled_config(width):
    return EmblaConfig(vocab_size=262144,hidden_size=width,head_dim=width//16,
        intermediate_size=((width+63)//64)*64,moe_intermediate_size=((width//4+63)//64)*64,
        shared_expert_intermediate_size=((width//2+63)//64)*64,
        engram_pages=round(209716*(width/2048)**2),use_cache=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    base=yaml.safe_load((ROOT/'logs/training/ouroB_dfm11_prefixlm_targetonly_20261115/resolved-config.yaml').read_text())
    manifest={'qualified':False,'queue_mutated':False,'required_before_launch':['profiler-backed FLOP freeze','full-size eight-rank capacity','throughput/long-context probes','scheduler preflight and insertion'], 'candidates':[]}
    for name,width,loops,prefix in [('embla-causal-all',1536,1,False),('embla-prefix-target',1536,1,True),('embla-loop-prefix-target',1024,4,True)]:
        cfg=scaled_config(width)
        if loops == 4:
            cfg.shared_expert_intermediate_size = 320
        else:
            cfg.shared_expert_intermediate_size = 704
        with torch.device('meta'):model=EmblaTrainingModel(cfg,decoder_loops=loops,prefix_lm=prefix)
        params=sum(p.numel() for p in model.parameters())
        recipe=json.loads(json.dumps(base))
        recipe['arch']={'name':'baselines.embla@Embla','head':'baselines.embla@EmblaLMHead',
                        'decoder_loops':loops,'attn_type':'prefixlm' if prefix else 'causal',
                        'embla_attention_backend':'tiled','embla_config':cfg.to_dict()}
        recipe['data']['target_only']=prefix
        recipe.update(run_name=name+'-dfm11-epoch1',wandb_run_id=name+'-dfm11-epoch1',
                      checkpoint_path=str(ROOT/'checkpoints/embla'/name),compile_train_batch=False,
                      suspend_control_dir=str(ROOT/'logs/training'/(name+'_dfm11')/'control'),
                      resume_checkpoint_path=None,resume_checkpoint_tag=None,lr_auto=False,gradient_accumulation_steps=4)
        # Eager per-document dispatch is deliberate until compiled kernels are qualified.
        path=args.output/(name+'.yaml');path.write_text(yaml.safe_dump(recipe,sort_keys=False))
        manifest['candidates'].append({'name':name,'width':width,'loops':loops,'parameters':params,
            'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
