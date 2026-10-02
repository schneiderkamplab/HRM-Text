"""Metadata-only HF access check for the proposed multilingual registry."""
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import argparse
import ast
import hashlib
import json
from pathlib import Path
import time
import shutil
import runpy

from huggingface_hub import HfApi, get_hf_file_metadata, hf_hub_url
import yaml

ACCESS_TOKEN = True


def runtime_credential(config):
    """Use the installed framework's normal access path; never emit the credential."""
    from importlib.metadata import version
    if version('euroeval')!=config['execution']['version']:
        raise ValueError('Use the pinned cached EuroEval interpreter for runtime-auth preflight')
    guard=Path('scripts/euroeval_api_no_flash_attn_guard.py').resolve()
    runpy.run_path(str(guard),run_name='dfm12_cpu_access_probe')
    from euroeval.string_utils import unscramble
    path=Path(config['source_evidence']['cached_18_1']['path'])/'data_loading.py'
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node,ast.keyword) and node.arg=='token' and isinstance(node.value,ast.Call):
            call=node.value
            if isinstance(call.func,ast.Name) and call.func.id=='unscramble':
                return unscramble(ast.literal_eval(call.args[0]))
    raise ValueError('Installed runtime credential path not found; do not guess')


def check_source(item):
    repo,names=item
    result=dict(source_dataset=repo,datasets=sorted(names),status='blocked_remote',
                revision=None,gated=None,checked_at=time.time())
    try:
        api=HfApi()
        initial=api.dataset_info(repo,token=ACCESS_TOKEN)
        pinned=api.dataset_info(repo,revision=initial.sha,token=ACCESS_TOKEN)
        if pinned.sha!=initial.sha:raise ValueError('Pinned revision mismatch')
        result.update(revision=pinned.sha,gated=pinned.gated,private=pinned.private,
                      files=[s.rfilename for s in pinned.siblings])
        payloads=[s.rfilename for s in pinned.siblings if s.rfilename.endswith(
            ('.parquet','.arrow','.csv','.tsv','.jsonl','.jsonl.gz'))]
        if payloads:
            filename=sorted(payloads)[0]
            metadata=get_hf_file_metadata(hf_hub_url(repo,filename,repo_type='dataset',revision=pinned.sha),token=ACCESS_TOKEN)
            result.update(status='accessible',head_file=filename,head_bytes=metadata.size,
                          head_commit=metadata.commit_hash)
        else:
            result.update(status='metadata_only_no_data_head',reason='No recognizable payload file; inspect before scheduling.')
    except Exception as error:
        result.update(error_type=type(error).__name__,
            http_status=getattr(getattr(error,'response',None),'status_code',None))
    print(repo,result['status'],result.get('http_status',''),flush=True)
    return result


def apply_results(config,results):
    by_repo={r['source_dataset']:r for r in results}
    expected={e['source_dataset'] for e in config['entries'] if e['dataset']}
    if set(by_repo)!=expected:raise ValueError('Access receipt source coverage mismatch')
    for entry in config['entries']:
        if not entry['dataset']:continue
        access=by_repo[entry['source_dataset']]
        entry.setdefault('catalog_status',entry['status'])
        entry.setdefault('catalog_include_in_average',entry['include_in_average'])
        entry['remote_access_status']=access['status']
        entry['dataset_revision']=access['revision']
        # Infrastructure readiness must never redefine the benchmark population.
        entry['status']=entry['catalog_status']
        entry['include_in_average']=entry['catalog_include_in_average']
        entry['remote_probe']=dict(status=access['status'],revision=access['revision'],
            error_type=access.get('error_type'),http_status=access.get('http_status'),
            classification='accessible' if access['status']=='accessible' else 'unresolved_remote_access')
    for language,coverage in config['coverage'].items():
        subset=[e for e in config['entries'] if e['language']==language]
        coverage['catalog_average_eligible']=sum(e.get('catalog_include_in_average',False) for e in subset)
        coverage['average_eligible']=sum(e['include_in_average'] for e in subset)
        coverage['remote_accessible']=sum(e.get('remote_access_status')=='accessible' for e in subset)
        coverage['remote_blocked']=sum(e.get('remote_access_status') not in (None,'accessible') for e in subset)


def main(reuse_receipt=False,framework_auth=False):
    global ACCESS_TOKEN
    path=Path('config/euroeval_dfm12_multilingual.yaml')
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    config=yaml.safe_load(path.read_text());sources={}
    for entry in config['entries']:
        if entry['dataset']:sources.setdefault(entry['source_dataset'],set()).add(entry['dataset'])
    receipt_path=Path('config/euroeval_dfm12_multilingual_access.json')
    if reuse_receipt:
        receipt=json.loads(receipt_path.read_text());results=receipt['sources']
    else:
        if framework_auth:
            ACCESS_TOKEN=runtime_credential(config)
            if receipt_path.exists():
                previous=receipt_path.with_name(receipt_path.stem+'_user_token.json')
                if not previous.exists():shutil.copy2(receipt_path,previous)
        HfApi().whoami(token=ACCESS_TOKEN)  # Verify credentials; never print them.
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(check_source,sorted(sources.items())))
        receipt=dict(schema='dfm12-euroeval-access-v1',checked_at=time.time(),
            input_config_sha256=before,unique_sources=len(sources),unique_datasets=sum(len(v) for v in sources.values()),
            metadata_only=True,mass_download=False,
            authentication='installed_framework_primary_credential' if framework_auth else 'existing_cached_token',
            counts=dict(Counter(r['status'] for r in results)),sources=results)
        receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
    # Refuse to overwrite concurrent registry edits during the network check.
    if hashlib.sha256(path.read_bytes()).hexdigest()!=before:
        raise ValueError('Registry changed while checking access; receipt saved, config untouched')
    apply_results(config,results)
    config['execution']['data_access_preflight']=str(receipt_path)
    config['execution']['revision_policy']='Metadata revisions pinned in entries; runtime must check/reuse these revisions. A named --dataset alone does not enforce the pin.'
    config['execution']['dataset_authentication']='Installed EuroEval loader uses its framework credential first, then user-token fallback; no credentials are stored in this registry.'
    config['source_evidence']['access_receipt_sha256']=hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    dependency_path=Path('config/euroeval_dfm12_multilingual_dependencies.json')
    if dependency_path.exists():
        config['source_evidence']['dependency_receipt']=str(dependency_path)
        config['source_evidence']['dependency_receipt_sha256']=hashlib.sha256(dependency_path.read_bytes()).hexdigest()
    loader=Path(config['source_evidence']['cached_18_1']['path'])/'data_loading.py'
    config['source_evidence']['runtime_loader_sha256']=hashlib.sha256(loader.read_bytes()).hexdigest()
    path.write_text(yaml.safe_dump(config,sort_keys=False,allow_unicode=False))
    print(json.dumps(receipt['counts']),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--reuse-receipt',action='store_true')
    parser.add_argument('--framework-auth',action='store_true')
    args=parser.parse_args()
    main(args.reuse_receipt,args.framework_auth)
