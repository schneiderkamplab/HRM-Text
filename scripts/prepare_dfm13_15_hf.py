"""Resolve immutable HF source inventories for the DFM13–15 serial rebuild."""
import json,re,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from huggingface_hub import HfApi,hf_hub_download
from scripts.acquire_dfm10_hf import save,sha
Q=ROOT/'data/rebuild_hf_dfm/serial-queue'

def components(version):
 if version==13:
  result=json.loads((ROOT/'data/sampled_dfm13/source-registry.json').read_text())['additions']
  for t in result:
   n=t['name']
   if not t['hf_repo_id']:
    if n.startswith('dfm13_dala_v2_compact_'):
     lang=n.removeprefix('dfm13_dala_v2_compact_').rsplit('_',2)[0].replace('pt_PT','pt-PT');t['hf_repo_id']='schneiderkamplab/dfm13-dala-v2-'+lang+'-compact'
    elif '_synthetic_' in n:
     lang,family=n.split('_synthetic_',1)[1].split('_',1);t['hf_repo_id']='schneiderkamplab/dfm13-multilingual-'+family.replace('_','-')+'-'+lang
    elif n=='hendrycks_math_worked':t['hf_repo_id']='schneiderkamplab/dfm13-hendrycks-math-worked'
    elif n=='setur_fo_instruct':t['hf_repo_id']='Setur/fo-instruct'
    else:raise ValueError(n)
  return result
 result=json.loads((ROOT/'config/dfm14_sources.json').read_text())['additions']
 for t in result:t['tokenized_parts']=t['parts']
 return result

def run(version):
 w=Q/f'dfm{version}';w.mkdir(exist_ok=True);ts=components(version);repos={}
 for t in ts:repos.setdefault(t['hf_repo_id'],[]).append(t)
 def pin(repo,items):
  dest=w/'lock-metadata'/repo.replace('/','--');receipt=dest/'resolved.json'
  if receipt.exists():return repo,json.loads(receipt.read_text())
  pins={t.get('hf_revision') for t in items if t.get('hf_revision')}
  if len(pins)>1:raise ValueError('Revision conflict '+repo)
  api=HfApi();info=api.dataset_info(repo,revision=next(iter(pins),None),files_metadata=True);files={}
  for f in info.siblings:
   rel=f.rfilename
   if rel.endswith(('.json','.md','.py')) or rel.startswith(('data/','train/')):
    if not rel.startswith(('data/','train/')) and not ('manifest' in rel or rel=='README.md'):continue
    h=f.lfs.sha256 if f.lfs else None
    if not h or ('manifest' in rel and rel.endswith('.json')):
     p=Path(hf_hub_download(repo,rel,repo_type='dataset',revision=info.sha,local_dir=dest));h=sha(p)
    files[rel]={'bytes':f.size,'sha256':h}
  data={'repo_id':repo,'revision':info.sha,'files':files,'components':[t['name'] for t in items]};save(receipt,data);return repo,data
 packages={};errors={}
 with ThreadPoolExecutor(max_workers=12) as pool:
  fs={pool.submit(pin,r,ts):r for r,ts in repos.items()}
  for f in as_completed(fs):
   try:r,d=f.result();packages[r]=d;print(version,'Pinned',r,len(packages),'/',len(repos),flush=True)
   except Exception as e:errors[fs[f]]=str(e);print('ERROR',fs[f],str(e),flush=True)
 save(w/'discovery.json',{'version':version,'components':ts,'packages':packages,'errors':errors})
 if errors:raise ValueError('Incomplete package discovery')
if __name__=='__main__':run(int(sys.argv[1]))
