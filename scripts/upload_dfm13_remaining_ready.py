"""Freeze new ready language-level DaLA packages, excluding prior publications."""
import argparse
import os
from pathlib import Path
import time
import yaml
from dfm12.io import file_hash, load, lock, write_json
from scripts.upload_dfm13_ready150 import publish


def candidates():
    found={}
    inherited=Path('exports_dfm13_inherited_dala/inventory.json')
    if inherited.exists():
        inventory=load(inherited)
        for item in inventory['packages']:
            if not item.get('local_package_ready'):continue
            folder=inherited.parent/item['hf_repo_id'].split('/')[-1]
            found[item['hf_repo_id']]=dict(item,folder=str(folder),kind='inherited_dala',
                readiness=str(folder/'manifest.json'))
    for path in sorted(Path('exports_dfm13_dala_languages').glob('*/ready.json')):
        item=load(path)
        if not item.get('local_package_ready') or not item.get('one_dataset_per_language'):continue
        expected={'baseline','recovery'} if item['language'] in ('nl','fa') else {'baseline'}
        if set(item['pools'])!=expected:raise ValueError('Uncombined language publication')
        if item['hf_repo_id']!='schneiderkamplab/dfm13-dala-v2-'+item['language']+'-compact':raise ValueError('Wrong language repo')
        for pin in item['integration_pins'].values():
            if file_hash(pin['path'])!=pin['sha256']:raise ValueError('Integration proof changed')
        found[item['hf_repo_id']]=dict(item,folder=str(path.parent),kind='dala_v2_language',readiness=str(path))
    return found


def freeze_batch(root, items):
    packages=[]
    for repo,item in sorted(items.items()):
        source=Path(item['folder']); target=root/'packages'/repo.split('/')[-1]
        pins={}
        names=set(item['files'])|{'README.md'}
        names|={p.name for p in source.iterdir() if p.name in ('source-receipts.json','dedup-provenance.jsonl','manifest.json')}
        metadata=yaml.safe_load((source/'README.md').read_text().split('---',2)[1])
        if {c['config_name'] for c in metadata['configs']}!={'acceptability','correction'}:raise ValueError('Task configs missing')
        for name in sorted(names):
            original=(source/name).resolve(strict=True)
            if not original.is_relative_to(source.resolve()):raise ValueError('Package path escape')
            sha=file_hash(original)
            if name in item['files'] and sha!=item['files'][name]:raise ValueError('Ready payload changed')
            frozen=target/name;frozen.parent.mkdir(parents=True,exist_ok=True)
            if not frozen.exists():os.link(original,frozen)
            if file_hash(frozen)!=sha:raise ValueError('Freeze drift')
            pins[name]=sha
        packages.append(dict(repo=repo,kind=item['kind'],folder=str(target.resolve()),files=pins,
            readiness=item['readiness'],readiness_sha256=file_hash(item['readiness'])))
        print('FROZEN',len(packages),repo,flush=True)
    queue=dict(expected=len(packages),packages=packages,authorization='User authorized all remaining upload-ready packages',
               combined_language_policy=True,already_published_excluded=True,source_files_modified=False)
    write_json(root/'queue.json',queue);write_json(root/'seal.json',dict(sha256=file_hash(root/'queue.json')))


def run(root,watch):
    with lock(root/'.controller.lock'):
        while True:
            published={repo for repo,r in load('data/dfm13/upload-ready150-20261004-v2/publication-receipts.json').items()
                       if r['status']=='verified'}
            receipts={};seen=set();batches=sorted((root/'batches').glob('batch-*'))
            for batch in batches:
                if not (batch/'queue.json').exists():raise ValueError('Interrupted freeze requires recovery')
                seen.update(p['repo'] for p in load(batch/'queue.json')['packages'])
                if not (batch/'completion.json').exists():publish(batch)
                if (batch/'blocked.json').exists():
                    write_json(root/'blocked.json',load(batch/'blocked.json'));return
                if (batch/'publication-receipts.json').exists():receipts.update(load(batch/'publication-receipts.json'))
            write_json(root/'publication-receipts.json',receipts)
            available={repo:item for repo,item in candidates().items() if repo not in published and repo not in seen}
            write_json(root/'progress.json',dict(verified=sum(r['status']=='verified' for r in receipts.values()),
                newly_ready=len(available),frozen_repositories=len(seen),phase='freezing' if available else 'waiting_ready',
                expected_dala_repositories=46,no_split_pool_repositories=True))
            if available:
                batch=root/'batches'/f'batch-{len(batches)+1:04d}'
                freeze_batch(batch,available);publish(batch)
                if (batch/'blocked.json').exists():
                    write_json(root/'blocked.json',load(batch/'blocked.json'));return
                continue
            if not watch:break
            if len(receipts)==46 and all(r['status']=='verified' for r in receipts.values()):
                write_json(root/'completion.json',dict(complete=True,verified=46,scope='12 inherited +34 combined DaLA languages'))
                break
            time.sleep(30)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('data/dfm13/upload-remaining-ready-20261004-v1'))
    p.add_argument('--watch',action='store_true');a=p.parse_args();run(a.root,a.watch)
