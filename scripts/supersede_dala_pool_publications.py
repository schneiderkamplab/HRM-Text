"""Retain old package evidence while disabling pool-separated publication queues."""
from pathlib import Path
from dfm12.io import load, lock, write_json


def main():
    root=Path('exports_dfm13_dala_compact')
    policy=dict(status='superseded_do_not_upload',local_package_ready=False,
                reason='User requires one deduplicated HF dataset per language, combining baseline and recovery',
                successor='exports_dfm13_dala_languages/queue.json',expected_language_repositories=34)
    with lock(root/'.policy.lock'):
        write_json(root/'PUBLICATION_DISABLED.json',policy)
        for path in root.glob('*/ready.json'):
            original=path.with_name('ready-before-language-policy.json')
            if not original.exists():write_json(original,load(path))
            result=load(path);result.update(policy);write_json(path,result)
        path=root/'inventory.json'
        if path.exists():
            original=root/'inventory-before-language-policy.json'
            if not original.exists():write_json(original,load(path))
            result=load(path);result.update(policy,complete=False)
            for item in result.get('packages',[]):item.update(policy)
            write_json(path,result)
    old=Path('data/dfm13/dala-v2-upload-nine-20261004-v1/queue.json')
    with lock(old.parent/'.language-policy.lock'):
        archive=old.with_name('queue-before-language-policy.json')
        if not archive.exists():write_json(archive,load(old))
        value=load(old);value.update(policy)
        for item in value['items']:
            item.update(status='superseded_do_not_upload',successor_repo_id=
                        'schneiderkamplab/dfm13-dala-v2-'+item['language']+'-compact')
        write_json(old,value)


if __name__=='__main__':main()
