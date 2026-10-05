"""After the first pass, normalize frozen HF card language tags only and resume150."""
import os
from pathlib import Path
import time
import yaml
from dfm12.io import load, lock, write_json, file_hash, atomic
from scripts.upload_dfm13_ready150 import publish


def main():
    old=Path('data/dfm13/upload-ready150-20261004-v1')
    root=Path('data/dfm13/upload-ready150-20261004-v2')
    while not (old/'completion.json').exists():
        if (old/'blocked.json').exists():
            write_json(root/'blocked.json',dict(reason='upstream_auth_or_quota_block',upstream=load(old/'blocked.json')))
            return
        time.sleep(10)
    with lock(root/'.prepare.lock'):
        if not (root/'queue.json').exists():
            old_sha=file_hash(old/'queue.json')
            if old_sha!=load(old/'seal.json')['sha256']:raise ValueError('Original queue changed')
            queue=load(old/'queue.json');receipts=load(old/'publication-receipts.json');changes=[]
            for item in queue['packages']:
                source=Path(item['folder']);folder=root/'packages'/source.name
                for relative,sha in item['files'].items():
                    original=source/relative
                    if file_hash(original)!=sha:raise ValueError('Original frozen file changed')
                    target=folder/relative;target.parent.mkdir(parents=True,exist_ok=True)
                    if not target.exists():os.link(original,target)
                card=folder/'README.md';text=card.read_text();pieces=text.split('---',2)
                metadata=yaml.safe_load(pieces[1]);languages=metadata.get('language',[])
                if isinstance(languages,str):languages=[languages]
                normalized=['pt' if lang in ('pt_pt','pt-PT') else lang for lang in languages]
                if languages!=normalized:
                    metadata['language']=normalized
                    # Atomic replacement breaks the hard link; original cards stay immutable.
                    with atomic(card) as out:
                        out.write('---\n'+yaml.safe_dump(metadata,sort_keys=False,allow_unicode=True)+'---'+pieces[2]+
                                  '\nPortuguese rows retain the European Portuguese (pt-PT) variant in their source provenance; '
                                  'the HF language metadata uses the ISO code pt.\n')
                    changes.append(dict(repo=item['repo'],old_sha256=item['files']['README.md'],
                                        new_sha256=file_hash(card),old_languages=languages,new_languages=normalized))
                    item['files']['README.md']=file_hash(card)
                    if receipts.get(item['repo'],{}).get('status')=='verified':
                        raise ValueError('Do not revise an already verified repository')
                    receipts.pop(item['repo'],None)
                item['folder']=str(folder.resolve())
            queue['predecessor_queue_sha256']=old_sha
            queue['metadata_only_corrections']=changes
            write_json(root/'queue.json',queue);write_json(root/'seal.json',dict(sha256=file_hash(root/'queue.json')))
            write_json(root/'publication-receipts.json',receipts)
            write_json(root/'metadata-corrections.json',dict(changes=changes,source_files_modified=False,
                payloads_modified=False,scope_unchanged=150,predecessor_queue_sha256=old_sha))
    publish(root)


if __name__=='__main__':main()
