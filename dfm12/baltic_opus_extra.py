"""Reviewed institutional English/Baltic additions, isolated from live discovery."""
from concurrent.futures import ProcessPoolExecutor
import urllib.request
import yaml

from . import opus
from .baltic_opus import configuration
from .baltic_sources_cpu import ROOT, renderer
from .io import load, lock, write_json
from .opus_review import json_metadata

REVISION = '42d4fbe382245487a68e853ca53bea832a41a02a'
SOURCES = {
    'ELRC-2717-EMEA': ('en-lt','cc-by-4.0'),
    'ELRC-2729-EMEA': ('en-lv','cc-by-4.0'),
    'ELRC-405-President_Lithuania': ('en-lt','cc-by-sa-4.0'),
    'ELRC-402-MFA_Latvia': ('en-lv','cc-by-sa-4.0'),
    'ELRC-425-Lithuanian_legislati': ('en-lt','cc-by-4.0'),
    'ELRC-433-State_Latvian': ('en-lv','cc-by-sa-4.0'),
}


def prepare(pair):
    root = ROOT/'institutional-translations'
    path = root/'candidates'/('opus-'+pair)/'receipt.json'
    if path.exists():
        return load(path)
    result=opus.prepare_pair(root,pair,configuration(),renderer())
    print(pair,result['counts'],flush=True)
    return result


def main():
    root=ROOT/'institutional-translations'
    with lock(root/'.campaign.lock'):
        entries=load(ROOT/'translations/opus/inventory.json')['pairs']
        inventory={'pairs':{'en-lt':{'corpora':[]},'en-lv':{'corpora':[]}}}
        for corpus,(pair,license) in SOURCES.items():
            evidence={}
            for suffix in ('info.yaml','v1/info.yaml'):
                url=f'https://raw.githubusercontent.com/Helsinki-NLP/OPUS/{REVISION}/corpus/{corpus}/{suffix}'
                raw=urllib.request.urlopen(url,timeout=60).read().decode()
                evidence[suffix]=dict(url=url,raw=raw,metadata=json_metadata(yaml.safe_load(raw)))
            parent=str(evidence['info.yaml']['metadata'].get('license','')).lower()
            release=str(evidence['v1/info.yaml']['metadata'].get('license','')).lower()
            slug=license.removeprefix('cc-').rsplit('-',1)[0]
            if not (license in parent or f'/licenses/{slug}/4.0' in parent) or release!=license:
                raise ValueError('Conflicting or missing license: '+corpus)
            write_json(root/'evidence'/f'{corpus}.json',evidence)
            entry=next(dict(e) for e in entries[pair]['corpora'] if e['corpus']==corpus and e['version']=='v1')
            entry.update(status='approved',license=license,license_evidence=evidence['v1/info.yaml']['url'],
                quality_review='Named institutional parallel corpus; independent alignment and language audit mandatory')
            inventory['pairs'][pair]['corpora'].append(entry)
        write_json(root/'opus/inventory.json',inventory)
        with ProcessPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(prepare,['en-lt','en-lv']))
        write_json(root/'manifest.json',dict(sources=results,audit='pending',policy='shares pair token budget with other routes'))


if __name__=='__main__':
    main()
