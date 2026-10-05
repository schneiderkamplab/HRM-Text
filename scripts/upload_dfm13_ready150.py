"""Freeze and publish exactly the user-authorized 145+4+1 existing packages."""
import argparse
from collections import Counter
import os
from pathlib import Path
import time
from dfm12.io import load, lock, write_json, file_hash


def freeze(root):
    if (root/'queue.json').exists():
        queue=load(root/'queue.json')
        if file_hash(root/'queue.json')!=load(root/'seal.json')['sha256']:raise ValueError('Queue seal drift')
        return queue
    reference=load('data/dfm13/authoritative-additions.json')
    assembly=load(Path(reference['root'])/'assembly.json')
    if file_hash(Path(reference['root'])/'assembly.json')!=reference['assembly_sha256']:raise ValueError('Assembly drift')
    entries=load(Path(reference['root'])/'registry.snapshot.json')['additions']
    ready={x['name'] for x in assembly['ready_additions']}; selected=[]
    for e in entries:
        if e.get('publication_contract')=='accepted-local-wave-translation-v1':
            if e['name'] not in ready or e.get('uploaded') is not False:raise ValueError('OPUS not ready')
            folder=Path(e['output']).parent.parent
            files=['README.md','manifest.json','data/train.jsonl',*e['attribution_files'].values()]
            selected.append(dict(kind='opus',repo=e['hf_repo_id'],folder=str(folder),files=files,
                payload_sha256=e['output_sha256'],proof=e['selection_receipt'],proof_sha256=e['selection_receipt_sha256']))
    baltic=Path('data/dfm13/baltic-finished-release-20261004-v1')
    registry={e['name']:e for e in load(baltic/'registry.json')['additions']}
    for item in load(baltic/'upload-readiness.json')['packages']:
        if item['upload_ready']:
            e=registry[item['name']]
            allowed={f'dfm13_baltic_synthetic_{lang}_{family}' for lang in ('lt','lv')
                     for family in ('math_code','tool_dialogue')}
            if e['name'] not in allowed:raise ValueError('Baltic scope')
            folder=Path(e['output']).parent.parent
            if file_hash(folder/'README.md')!=item['readme_sha256']:raise ValueError('Card drift')
            selected.append(dict(kind='baltic',repo=item['hf_repo_id'],folder=str(folder),
                files=['README.md','SOURCE_INVENTORY.json','manifest.json','data/train.jsonl'],
                payload_sha256=e['output_sha256'],proof=str(baltic/'upload-readiness.json'),
                proof_sha256=file_hash(baltic/'upload-readiness.json')))
    folder=Path('exports_dfm13/dfm13-hendrycks-math-worked');proof=folder.with_suffix('.ready.json');m=load(proof)
    if not m['valid'] or not m['upload_ready'] or m['uploaded']:raise ValueError('MATH not ready')
    selected.append(dict(kind='math',repo=m['hf_repo_id'],folder=str(folder),
        files=[str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file()],
        payload_sha256='06d35dcb70367fe4608994bbe861e3afff9e4714cc0198e1cc9cca62e2f37076',
        proof=str(proof),proof_sha256=file_hash(proof)))
    if Counter(x['kind'] for x in selected)!=dict(opus=145,baltic=4,math=1) or len({x['repo'] for x in selected})!=150:
        raise ValueError('Exact150 scope mismatch')
    packages=[]
    for item in selected:
        folder=Path(item.pop('folder')); names=item.pop('files'); frozen=root/'packages'/item['repo'].split('/')[-1]
        pins={}
        if file_hash(item['proof'])!=item['proof_sha256']:raise ValueError('Readiness drift')
        for relative in names:
            source=(folder/relative).resolve(strict=True)
            if not source.is_relative_to(folder.resolve()):raise ValueError('Package path escape')
            target=frozen/relative;target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():os.link(source,target)
            pins[relative]=file_hash(target)
        if pins['data/train.jsonl']!=item['payload_sha256']:raise ValueError('Accepted payload drift')
        packages.append(dict(item,folder=str(frozen.resolve()),files=pins))
        write_json(root/'progress.json',dict(phase='freezing',frozen=len(packages),expected=150))
        print('FROZEN',len(packages),item['repo'],flush=True)
    queue=dict(authorization='Explicit user upload exactly145 OPUS +4 Baltic math/tool +1 MATH',
        expected=150,packages=packages,source_payloads_modified=False,registry_modified=False)
    write_json(root/'queue.json',queue);write_json(root/'seal.json',dict(sha256=file_hash(root/'queue.json')))
    return queue


def verify_remote(api, item, revision):
    from huggingface_hub import hf_hub_download
    actual=set(api.list_repo_files(item['repo'],repo_type='dataset',revision=revision))
    if actual-set(item['files'])- {'.gitattributes'} or not set(item['files'])<=actual:
        raise ValueError('Remote file inventory differs')
    for name,sha in item['files'].items():
        path=hf_hub_download(item['repo'],name,repo_type='dataset',revision=revision)
        if file_hash(path)!=sha:raise ValueError('Remote file digest differs')


def publish(root):
    from huggingface_hub import HfApi
    from huggingface_hub.errors import RepositoryNotFoundError
    with lock(root/'.uploader.lock'):
        api=HfApi();api.whoami();print('AUTHENTICATED',flush=True)
        queue=freeze(root)
        expected=queue['expected']
        receipt_path=root/'publication-receipts.json'
        receipts=load(receipt_path) if receipt_path.exists() else {}
        for item in queue['packages']:
            repo=item['repo'];saved=receipts.get(repo,{})
            if saved.get('status')=='verified':continue
            try:
                for name,sha in item['files'].items():
                    if file_hash(Path(item['folder'])/name)!=sha:raise ValueError('Frozen package changed')
                try:info=api.repo_info(repo,repo_type='dataset')
                except RepositoryNotFoundError:info=None
                if saved.get('revision'):
                    revision=saved['revision']
                elif info and set(api.list_repo_files(repo,repo_type='dataset',revision=info.sha))- {'.gitattributes'}:
                    # Existing data may be a completed earlier attempt; never overwrite conflicting contents.
                    revision=info.sha;verify_remote(api,item,revision)
                else:
                    receipts[repo]=dict(status='publishing',started=time.time(),files=item['files'])
                    write_json(receipt_path,receipts)
                    if info is None:api.create_repo(repo,repo_type='dataset',private=False,exist_ok=False)
                    head=api.repo_info(repo,repo_type='dataset').sha
                    commit=api.upload_folder(repo_id=repo,repo_type='dataset',folder_path=item['folder'],
                        allow_patterns=list(item['files']),parent_commit=head,
                        commit_message='Publish explicitly authorized accepted-only DFM13 package')
                    revision=commit.oid
                    receipts[repo].update(status='uploaded_verification_pending',revision=revision)
                    write_json(receipt_path,receipts)
                verify_remote(api,item,revision)
                receipts[repo]=dict(status='verified',revision=revision,files=item['files'],
                    completed=time.time(),kind=item['kind'],remote_payloads_sha256_verified=True)
                write_json(receipt_path,receipts)
                print('VERIFIED',repo,revision,flush=True)
            except Exception as exc:
                response=getattr(exc,'response',None);status=getattr(response,'status_code',None)
                # Do not serialize exception strings, request headers or credentials.
                receipts.setdefault(repo,{}).update(status='blocked',error_type=type(exc).__name__,http_status=status,time=time.time())
                write_json(receipt_path,receipts)
                print('BLOCKED',repo,type(exc).__name__,status,flush=True)
                if status in (401,403,429):
                    write_json(root/'blocked.json',dict(repo=repo,http_status=status,error_type=type(exc).__name__,
                        no_quota_bypass=True,queue_preserved=True));return
            write_json(root/'progress.json',dict(phase='publishing',verified=sum(x.get('status')=='verified' for x in receipts.values()),expected=expected))
        n=sum(x.get('status')=='verified' for x in receipts.values())
        write_json(root/'completion.json',dict(complete=n==expected,verified=n,expected=expected,
            queue_sha256=file_hash(root/'queue.json'),receipts_sha256=file_hash(receipt_path),registry_modified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('data/dfm13/upload-ready150-20261004-v1'))
    a=p.parse_args();publish(a.root)
