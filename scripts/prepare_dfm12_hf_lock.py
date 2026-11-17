"""Resolve DFM12's preserved component inventory to immutable HF packages."""
import sys,json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from huggingface_hub import HfApi,hf_hub_download
from scripts.acquire_dfm10_hf import sha,save
WORK=ROOT/'data/rebuild_hf_dfm/serial-queue/dfm12'

def main():
    registry=json.loads((ROOT/'data/sampled_dfm12/source-registry.json').read_text())
    api=HfApi();published={x.id for x in api.list_datasets(author='schneiderkamplab')}
    tasks=registry['additions'];repos={}
    for t in tasks:
        direct='schneiderkamplab/'+t['name']
        repo=direct if direct in published else t['hf_repo_id']
        repos.setdefault(repo,[]).append(t['name'])
    def resolve(repo):
        dest=WORK/'lock-metadata'/repo.split('/')[-1];receipt=dest/'resolved.json'
        if receipt.exists():return repo,json.loads(receipt.read_text())
        info=HfApi().dataset_info(repo,files_metadata=True)
        files={}
        for f in info.siblings:
            rel=f.rfilename
            if rel.startswith('data/') or rel in ('metadata/manifest.json','README.md'):
                record={'bytes':f.size,'sha256':f.lfs.sha256 if f.lfs else None,'git_blob':f.blob_id}
                if not record['sha256'] or rel=='metadata/manifest.json':
                    p=Path(hf_hub_download(repo,rel,repo_type='dataset',revision=info.sha,local_dir=dest));record['sha256']=sha(p)
                files[rel]=record
        result={'repo_id':repo,'revision':info.sha,'files':files,'components':repos[repo]}
        save(receipt,result);return repo,result
    found={};errors={}
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures={pool.submit(resolve,r):r for r in repos}
        for f in as_completed(futures):
            try:
                r,v=f.result();found[r]=v;print('Pinned',r,len(found),'/',len(repos),flush=True)
            except Exception as e:errors[futures[f]]=str(e);print('ERROR',futures[f],str(e),flush=True)
    save(WORK/'discovery.json',{'registry_sha256':sha(ROOT/'data/sampled_dfm12/source-registry.json'),'packages':found,'errors':errors,'components':tasks})
    if errors:raise ValueError('HF package discovery incomplete')
if __name__=='__main__':main()
