"""Publish authorized DFM14 packages and verify every remote attachment and task view."""
import argparse,hashlib,json,os,time,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from huggingface_hub import HfApi,CommitOperationAdd,hf_hub_download,DatasetCard
from huggingface_hub.errors import RepositoryNotFoundError
from .io import load,write_json,file_hash,lock
from .dfm14_dala_release import LANGUAGES,SCOPES,TASKS,publication_row
from .dala_compact_finalize import accepted,canonical,task_row,pin


def git_hash(path):
    h=hashlib.sha1();h.update(f'blob {path.stat().st_size}\0'.encode())
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def verify_remote(api,repo,revision,folder,files):
    remote={x.path:x for x in api.list_repo_tree(repo,repo_type='dataset',revision=revision,recursive=True) if hasattr(x,'blob_id')}
    if set(remote)!=set(files):raise ValueError('Remote file inventory differs: '+repo)
    for name in files:
        item=remote[name];p=folder/name
        if item.size!=p.stat().st_size:raise ValueError('Remote size differs: '+name)
        if item.lfs:
            if item.lfs.sha256!=file_hash(p):raise ValueError('Remote LFS hash differs: '+name)
        elif item.blob_id!=git_hash(p):raise ValueError('Remote Git hash differs: '+name)
    downloaded=hf_hub_download(repo,'manifest.json',repo_type='dataset',revision=revision)
    if file_hash(downloaded)!=file_hash(folder/'manifest.json'):raise ValueError('Downloaded manifest differs')


def publish(job):
    root,language=Path(job[0]),job[1];group=root/'groups'/language;integration=load(group/'integration.json');export=load(group/'export.json')
    if integration['status']!='complete_train_only' or integration['export']!=pin(group/'export.json'):raise ValueError('Incomplete train integration')
    folder=Path(export['package']);manifest=load(folder/'manifest.json');repo=manifest['repo_id'];checksum=file_hash(folder/'manifest.json')
    if repo!='schneiderkamplab/dfm14-dala-v2-'+language+'-compact':raise ValueError('Unexpected HF destination')
    if export['validation']['status']!='passed' or export['package_manifest']['sha256']!=checksum:raise ValueError('Package not validated/pinned')
    files={**manifest['files'],'manifest.json':dict(sha256=checksum,bytes=(folder/'manifest.json').stat().st_size)}
    if {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file()}!=set(files):raise ValueError('Local inventory differs')
    for name,item in files.items():
        path=folder/name
        if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()) or path.stat().st_size!=item['bytes'] or file_hash(path)!=item['sha256']:raise ValueError('Package artifact changed: '+name)
    DatasetCard.load(folder/'README.md').validate()
    api=HfApi();receipt=group/'upload.json';saved=load(receipt) if receipt.exists() else None
    if saved and saved['manifest_sha256']!=checksum:raise ValueError('Publication content drift')
    try:info=api.dataset_info(repo)
    except RepositoryNotFoundError:info=None
    if info and not (saved and saved.get('repository_created_by_this_run')):
        p=hf_hub_download(repo,'manifest.json',repo_type='dataset',revision=info.sha)
        if file_hash(p)!=checksum:raise ValueError('Existing unowned repository differs')
        revision=info.sha
    elif saved and saved.get('revision'):
        revision=saved['revision']
    else:
        state=dict(repo_id=repo,manifest_sha256=checksum,authorized='User: export, integrate and upload to HF',public=True,at=time.time(),status='uploading',repository_created_by_this_run=bool(saved and saved.get('repository_created_by_this_run')))
        write_json(receipt,state)
        if not info:
            api.create_repo(repo,repo_type='dataset',private=False,exist_ok=False);state['repository_created_by_this_run']=True;write_json(receipt,state)
        commit=api.create_commit(repo,repo_type='dataset',operations=[CommitOperationAdd(path_in_repo=name,path_or_fileobj=str(folder/name)) for name in sorted(files)],commit_message='Publish DFM14 audit-passed DaLA v2 language with both tasks and preserved heldouts',parent_commit=info.sha if info else None,num_threads=8)
        revision=commit.oid;state.update(revision=revision,commit_url=commit.commit_url,status='uploaded_verifying');write_json(receipt,state)
    verify_remote(api,repo,revision,folder,files)
    import datasets
    loader={}
    for task in TASKS:
        data=datasets.load_dataset(repo,name=task,revision=revision,streaming=True,cache_dir=str(root/'hf-loader-cache'))
        expected={'train' if s=='train_representative' else s for s in SCOPES}
        if set(data)!=expected:raise ValueError('Remote dataset configurations/splits differ')
        loader[task]={}
        for scope in sorted(data):
            row=next(iter(data[scope]));source=json.loads(row['provenance_json']);evidence=json.loads(row['audit_json']);kind='clean_control' if row['variant']=='clean' else 'pair';record=canonical(source,language,kind)
            if not accepted(record,evidence['decision'],'done') or row!=publication_row(task_row(source,record,task,export['prompts'],evidence)):raise ValueError('Remote loader/native chat mismatch')
            loader[task][scope]=dict(sample_id=row['id'],verified=True)
    result=dict(status='verified',repo_id=repo,revision=revision,url='https://huggingface.co/datasets/'+repo,manifest_sha256=checksum,files=len(files),bytes=sum(x['bytes'] for x in files.values()),counts=manifest['counts'],verification='Exact remote file set, sizes, Git/LFS hashes, downloaded manifest, both native task configurations and all five split/view streaming samples',loader=loader,completed=time.time(),human_validation=False,producer_v2_audit_equivalent=False,repository_created_by_this_run=bool(load(receipt).get('repository_created_by_this_run')) if receipt.exists() else False)
    write_json(receipt,result);print('HF_VERIFIED',language,revision,flush=True);return result


def run(root,workers):
    import psutil
    root=Path(root).resolve();done={};active={};submitted=set()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while len(done)<len(LANGUAGES):
            for lang in LANGUAGES:
                if lang in submitted:continue
                if not (root/f'groups/{lang}/integration.json').exists():continue
                active[pool.submit(publish,(str(root),lang))]=lang;submitted.add(lang)
            for future in list(active):
                if future.done():
                    lang=active.pop(future);done[lang]=future.result();write_json(root/'upload-progress.json',dict(verified=len(done),total=len(LANGUAGES),receipts=done,at=time.time()))
            if len(done)==len(LANGUAGES):break
            launch=load(root/'launch.json')
            if not psutil.pid_exists(launch['pid']) and not (root/'complete.json').exists() and len(submitted)<len(LANGUAGES):raise RuntimeError('Release pipeline stopped before all integrations completed')
            time.sleep(10)
    while not (root/'complete.json').exists():time.sleep(2)
    complete=load(root/'complete.json')
    if not complete['success'] or complete['registry']!=pin(root/'registry.json'):raise ValueError('Final integration incomplete')
    registry=load(root/'registry.json');components=[]
    for component in registry['additions']:
        remote=done[component['language']];components.append(dict(component,uploaded=True,hf_revision=remote['revision'],hf_repo_id=remote['repo_id'],remote_verification=pin(root/'groups'/component['language']/'upload.json')))
    published=dict(registry,additions=components,source_registry=pin(root/'registry.json'),publication_verified=True)
    write_json(root/'published-registry.json',published)
    hrm=Path(__file__).resolve().parents[1];write_json(hrm/'data/dfm14/local-audited-dala-additions.json',dict(published,registry=pin(root/'published-registry.json')))
    result=dict(complete=True,datasets=done,registry=pin(root/'published-registry.json'),train_rows=sum(c['rows'] for c in components),train_tokens=sum(c['tokens'] for c in components),components=len(components),at=time.time())
    write_json(root/'publication-complete.json',result)
    print('ALL_PUBLISHED',len(done),result['train_rows'],result['train_tokens'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    with lock(a.root/'.upload.lock'):run(a.root,a.workers)
