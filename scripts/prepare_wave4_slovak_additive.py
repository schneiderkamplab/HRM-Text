"""Isolated licensed Slovak bridge/direct/pivot candidates; no live queue writes."""
import argparse
from copy import deepcopy
from pathlib import Path
import time
import urllib.request
import yaml

from dfm12.io import load,write_json,file_hash,digest,lock

APPROVALS={'ELRC-487-Culture_Slovak':'public-domain',
           'ELRC-488-Justice_Slovak':'public-domain','ELRC-2721-EMEA':'cc-by-4.0'}
REVISION='42d4fbe382245487a68e853ca53bea832a41a02a'


def check_license(name,release,parent):
    expected=APPROVALS[name]
    observed=str(release.get('license','')).lower().replace('publicdomain','public-domain')
    upper=str(parent.get('license','')).lower().replace('publicdomain','public-domain')
    if (observed!=expected or expected not in upper or release.get('release')!='v1'
            or release.get('name')!=name or 'en-sk' not in release.get('language pairs',[])):
        raise ValueError('Named license/version/language evidence mismatch')
    return expected


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();root=args.root;base=Path('data/dfm13/wave4')
    if root.resolve()==base.resolve():raise ValueError('Additive root required')
    root.mkdir(parents=True,exist_ok=True)
    def status(stage,**details):
        write_json(root/'progress.json',dict(time=time.time(),stage=stage,admission_authorized=False,**details))
        print(stage,details,flush=True)
    with lock(root/'preparation.lock'):
        status('license_evidence')
        inventory=load(base/'institutional-translations/opus/inventory.json')
        source=inventory['pairs']['en-sk'];entries=[]
        for name in APPROVALS:
            documents=[]
            for suffix in ('v1/info.yaml','info.yaml'):
                url=f'https://raw.githubusercontent.com/Helsinki-NLP/OPUS/{REVISION}/corpus/{name}/{suffix}'
                path=root/'evidence'/name/('release.json' if suffix.startswith('v1') else 'parent.json')
                if path.exists():evidence=load(path)
                else:
                    with urllib.request.urlopen(url,timeout=30) as response:raw=response.read().decode()
                    evidence=dict(url=url,revision=REVISION,raw=raw,metadata=yaml.safe_load(raw))
                    write_json(path,evidence)
                documents.append(evidence['metadata'])
            license=check_license(name,*documents)
            entry=deepcopy(next(e for e in source['corpora'] if e['corpus']==name and e['version']=='v1'))
            entry.update(status='approved',license=license,
                license_evidence=f'https://raw.githubusercontent.com/Helsinki-NLP/OPUS/{REVISION}/corpus/{name}/v1/info.yaml',
                quality_review='Candidate-only named institutional release; PDF artifacts, both directions and source alignment require audit')
            entries.append(entry)
        cfg=load(base/'translations/config.json')
        cfg['requested_pairs']=[pair for pair in cfg['requested_pairs'] if 'sk' in pair]
        write_json(root/'translations/config.json',cfg)
        write_json(root/'translations/opus/inventory.json',dict(pairs={'en-sk':dict(corpora=entries)}))
        reused=[]
        for entry in entries:
            filename=digest(entry['url'])+'.zip';dest=root/'translations/opus/downloads'/filename
            if dest.exists():continue
            for directory in [base/'translations/opus/downloads',base/'institutional-translations/opus/downloads',Path('data/dfm12/opus/downloads')]:
                cached=directory/filename
                if cached.exists():
                    dest.parent.mkdir(parents=True,exist_ok=True);dest.symlink_to(cached.resolve());reused.append(str(cached));break
        status('prepare_en_sk',cached_archives=reused)
        from dfm12.opus import prepare_pair
        from dfm12.prepare import Renderer
        folder=root/'translations/candidates/opus-en-sk';receipt=folder/'receipt.json'
        if receipt.exists():
            if file_hash(folder/'candidates.jsonl')!=load(receipt)['sha256']:raise ValueError('Additive candidates changed')
        else:prepare_pair(root/'translations','en-sk',cfg,Renderer(load('data/sampled_dfm11/metadata.json')['tokenizer_info'],4096))
        # Borrow only immutable existing English legs. No existing inventory,
        # receipt, pivot input or candidate file is rewritten.
        for family in ('translations','institutional-translations'):
            for old in sorted((base/family/'candidates').glob('opus-*/receipt.json')):
                if 'en' not in old.parent.name[5:].split('-') or old.parent.name=='opus-en-sk':continue
                dest=root/family/'candidates'/old.parent.name
                dest.parent.mkdir(parents=True,exist_ok=True)
                if not dest.exists():dest.symlink_to(old.parent.resolve(),target_is_directory=True)
        status('build_sk_pivots',direct_pairs=load(receipt)['counts']['candidate_pairs'])
        from dfm12.baltic_pivots import main as pivots
        pivots(root)
        manifest=load(root/'pivots/manifest.json')
        components=[dict(component='sk-additive-v1-direct-en-sk',path=str(folder/'candidates.jsonl'),
            sha256=load(receipt)['sha256'],rows=load(receipt)['counts']['candidate_pairs'])]
        for item in manifest['pairs']:
            if item['state']=='pivot_candidates_ready':
                path=root/'pivots/candidates'/('opus-'+item['pair'])/'candidates.jsonl'
                components.append(dict(component='sk-additive-v1-pivot-'+item['pair'],path=str(path),sha256=item['sha256'],rows=item['counts']['candidate_pairs']))
        write_json(root/'integration.json',dict(components=components,requested_pairs=cfg['requested_pairs'],
            no_supply_pairs=[p['pair'] for p in manifest['pairs'] if p['state']=='no_unambiguous_pivot_supply'],
            approval_scope='license-eligible candidate preparation only',audit_required=True,
            native_audit_preflight_required=True,admission_authorized=False,live_queue_modified=False,
            evidence_pins={str(p):file_hash(p) for p in (root/'evidence').glob('*/*.json')},
            borrowed_inputs=manifest['inputs']))
        status('candidates_complete',components=len(components),candidate_pairs=sum(c['rows'] for c in components))


if __name__=='__main__':main()
