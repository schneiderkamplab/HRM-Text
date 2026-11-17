"""Fetch verified converted OPUS shards for a future rebuild, without regrouping."""
import argparse
import json
from pathlib import Path
import re
import sys
from huggingface_hub import hf_hub_download
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.acquire_dfm10_hf import safe_file, sha, save


def available(work):
    """Only skip export reconstruction after rechecking the fetched payloads."""
    dest=work/'rebuild-ready/opus_da_en_repaired'
    receipt=dest/'fetch-receipt.json'
    if not receipt.exists(): return False
    spec=json.loads(receipt.read_text())
    if spec.get('status')!='downloaded_sha256_verified' or not re.fullmatch('[0-9a-f]{40}',spec.get('revision','')):
        raise ValueError('Invalid fetched OPUS receipt')
    if sha(dest/'manifest.json')!=spec['manifest_sha256']:
        raise ValueError('Fetched OPUS manifest changed')
    files=json.loads((dest/'manifest.json').read_text())['files']
    if len(files)!=64 or len({x['task'] for x in files})!=64 or files!=spec['files']:
        raise ValueError('Fetched OPUS inventory changed')
    for item in files:
        path=safe_file(dest,item['path'])
        if path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:
            raise ValueError('Fetched OPUS payload changed')
    return True


def fetch(work, registry):
    spec=json.loads(registry.read_text())['opus_da_en_repaired']
    if spec.get('status') != 'uploaded_sha256_verified' or not re.fullmatch('[0-9a-f]{40}',spec['revision']):
        raise ValueError('Verified immutable publication pin required')
    dest=work/'rebuild-ready/opus_da_en_repaired'
    manifest=Path(hf_hub_download(spec['repo_id'],'manifest.json',repo_type='dataset',revision=spec['revision'],local_dir=dest))
    if sha(manifest) != spec['manifest_sha256']: raise ValueError('Manifest changed')
    content=json.loads(manifest.read_text());files=content['files']
    if len(files)!=64 or len({f['task'] for f in files})!=64: raise ValueError('Invalid OPUS task inventory')
    for entry in files:
        task=entry['task']
        if Path(task).name!=task or entry['path']!='data/'+task or not task.endswith('.parquet'):
            raise ValueError('Invalid OPUS task path')
    for entry in files+content['provenance']:
        path=safe_file(dest,entry['path'])
        hf_hub_download(spec['repo_id'],entry['path'],repo_type='dataset',revision=spec['revision'],local_dir=dest)
        if path.stat().st_size!=entry['bytes'] or sha(path)!=entry['sha256']:
            raise ValueError('Pinned package payload changed')
    save(dest/'fetch-receipt.json', dict(spec,files=files,status='downloaded_sha256_verified'))
    print('Fetched 64 verified OPUS task inputs into',dest)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--registry',type=Path,default=ROOT/'config/data/dfm10_rebuild_ready_packages.json')
    a=p.parse_args();fetch(a.work.resolve(),a.registry.resolve())
