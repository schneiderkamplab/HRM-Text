"""Upload only the two cleared OpenHermes packages from the Baltic handoff."""
import argparse
import os
from pathlib import Path
from dfm12.io import load, lock, write_json, file_hash
from scripts.upload_dfm13_wave4_ready import checked
from scripts.upload_dfm13_ready150 import publish


def freeze(root, handoff, scoped_six=False):
    if (root/'queue.json').exists():
        checked(root/'queue.json', load(root/'seal.json')['sha256'])
        return
    h=load(handoff)
    selected=[p for p in h['packages'] if p['upload_ready']]
    expected={'schneiderkamplab/dfm13-multilingual-openhermes-'+l for l in ('lt','lv')}
    if scoped_six:
        expected={'schneiderkamplab/dfm13-multilingual-'+f+'-'+l
                  for l in ('lt','lv') for f in ('grounded-instruct','multiturn','summary-rewrite')}
        if not h.get('sealed_release_unchanged') or sum(p['rows'] for p in selected)!=90000:
            raise ValueError('Scoped successor incomplete')
        for path,sha in h['evidence_pins'].items():checked(path,sha)
    if len(selected)!=len(expected) or {p['hf_repo_id'] for p in selected}!=expected:
        raise ValueError('Unexpected cleared Baltic scope')
    packages=[]
    for item in selected:
        source=Path(item['path'])
        manifest=checked(source/'publication-manifest.json',item['manifest_sha256'])
        m=load(manifest)
        if not m['upload_ready'] or m['unresolved_europarl_rows'] or m['hf_repo_id']!=item['hf_repo_id']:
            raise ValueError('Uncleared package')
        if scoped_six and (not m.get('source_specific_terms_retained') or m.get('decision') not in m['files']):
            raise ValueError('Missing scoped reuse decision')
        pins=dict(m['files'], **{'publication-manifest.json':item['manifest_sha256']})
        if pins['data/train.jsonl']!=m['original_output_sha256']:
            raise ValueError('Payload linkage changed')
        target=root/'packages'/item['hf_repo_id'].split('/')[-1]
        for name,sha in pins.items():
            original=(source/name).resolve(strict=True)
            if not original.is_relative_to(source.resolve()) or Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('Path escape')
            checked(original,sha)
            p=target/name;p.parent.mkdir(parents=True,exist_ok=True)
            if not p.exists():os.link(original,p)
            checked(p,sha)
        packages.append(dict(repo=item['hf_repo_id'],kind='baltic_scoped' if scoped_six else 'baltic_openhermes',folder=str(target.resolve()),files=pins))
        print('FROZEN',len(packages),item['hf_repo_id'],flush=True)
    write_json(root/'queue.json',dict(expected=len(expected),packages=packages,authorization='User authorizes all cleared ready packages',
        handoff=str(handoff),handoff_sha256=file_hash(handoff),source_payloads_modified=False))
    write_json(root/'seal.json',dict(sha256=file_hash(root/'queue.json')))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--handoff',type=Path,default=Path('exports_dfm13/baltic-source-attribution-20261004-v1/handoff.json'))
    p.add_argument('--scoped-six',action='store_true')
    a=p.parse_args()
    with lock(a.root/'.controller.lock'):
        freeze(a.root,a.handoff,a.scoped_six)
        publish(a.root)
