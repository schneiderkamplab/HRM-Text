"""Publish hash-bound wave4 notices without modifying sealed training exports."""
import argparse
import os
from pathlib import Path
from dfm12.io import load, file_hash, lock, write_json
from scripts.upload_dfm13_ready150 import publish


def checked(path, sha):
    path = Path(path)
    if file_hash(path) != sha:
        raise ValueError('Handoff pin changed: ' + str(path))
    return path


def freeze(root, handoff):
    if (root/'queue.json').exists():
        checked(root/'queue.json', load(root/'seal.json')['sha256'])
        return load(root/'queue.json')
    h = load(handoff)
    if h['status'] != '66_of_66_ready_for_owner_upload' or h['packages'] != 66:
        raise ValueError('Wrong authorized scope')
    registry = load(checked(h['source_registry'], h['source_registry_sha256']))
    supplement = Path(h['supplement_root'])
    complete = load(checked(supplement/'complete.json', h['supplement_complete_sha256']))
    evidence_path = checked(supplement/'evidence/manifest.json', complete['evidence_manifest_sha256'])
    evidence = {'evidence/manifest.json': (evidence_path, complete['evidence_manifest_sha256'])}
    for item in load(evidence_path)['documents']:
        p = Path(item['path'])
        if p.parent.resolve() != (supplement/'evidence').resolve():
            raise ValueError('Evidence path outside supplement')
        evidence['evidence/'+p.name] = (checked(p, item['sha256']), item['sha256'])
    entries = {e['name']: e for e in registry['additions']}
    if len(complete['packages']) != 66 or len({p['name'] for p in complete['packages']}) != 66:
        raise ValueError('Duplicate or missing package')
    packages = []
    for item in complete['packages']:
        e = entries[item['name']]
        repo = e['hf_repo_id']
        if not repo.startswith('schneiderkamplab/') or len(repo.split('/')) != 2:
            raise ValueError('Noncanonical repository')
        if e['output_sha256'] != item['source_export_sha256'] or e['rows'] != item['rows']:
            raise ValueError('Export linkage mismatch')
        files = dict(evidence)
        files['data/train.jsonl'] = (Path(e['output']), item['source_export_sha256'])
        for name, sha in item['pins'].items():
            p = Path(name)
            if p.parent.resolve() != (supplement/item['name']).resolve():
                raise ValueError('Notice path outside package')
            files[p.name] = (p, sha)
        if not {'README.md','NOTICE.md','SOURCE_INVENTORY.json','ATTRIBUTION.jsonl'} <= files.keys():
            raise ValueError('Missing notice')
        folder = root/'packages'/repo.split('/')[-1]
        pins = {}
        for relative, (source, sha) in files.items():
            checked(source, sha)
            target = folder/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                os.link(source, target)
            checked(target, sha)
            pins[relative] = sha
        packages.append(dict(repo=repo,kind='wave4',folder=str(folder.resolve()),files=pins,
                             readiness=str(handoff),readiness_sha256=file_hash(handoff)))
        print('FROZEN',len(packages),repo,flush=True)
    if len({p['repo'] for p in packages}) != 66:
        raise ValueError('Repository collision')
    queue = dict(expected=66,packages=packages,authorization=h['authorization'],
                 source_payloads_modified=False,registry_modified=False)
    write_json(root/'queue.json',queue)
    write_json(root/'seal.json',dict(sha256=file_hash(root/'queue.json')))
    return queue


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--handoff',type=Path,default=Path('data/dfm13/wave4-publication-notices-20261004-v4/upload-authorized-handoff.json'))
    a=p.parse_args()
    with lock(a.root/'.controller.lock'):
        freeze(a.root,a.handoff)
        publish(a.root)
