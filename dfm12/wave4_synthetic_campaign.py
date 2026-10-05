"""Sealed wave-four production campaign, gated on explicit calibration approval."""
import argparse
import asyncio
from pathlib import Path
import sqlite3

import yaml

from . import european_synthetic_campaign as european
from . import wave4_synthetic_specs as provider
from .io import file_hash, load, lock, write_json
from .multilingual_targets import targets
from .wave4_cpu import LANGUAGES
from . import wave_synthetic_runtime as runtime

VERSION='dfm13-wave4-synthetic-v2'
CONFIG=Path('config/dfm13_wave4_synthetic.yaml')


def quotas(config,milestone='tenth',divisor=None):
    from .multilingual_tasks import MODEL
    if (set(config['languages'])!=set(LANGUAGES) or set(config['families'])!=european.FAMILIES
            or config['generator']!=MODEL or config['auditor']!=MODEL
            or config['audit_every_candidate'] is not True or config['repeat']!=1
            or config['max_rendered_example_tokens']!=4096 or milestone!='tenth'
            or config['milestone_divisors']['tenth']!=10):
        raise ValueError('Wave-four policy mismatch')
    result=targets(config,milestone)
    for row in result:
        row['repo_id']=f"schneiderkamplab/dfm13-multilingual-{row['family']}-{row['language']}"
    for language in LANGUAGES:
        if sum(r['accepted_target'] for r in result if r['language']==language)!=70000:
            raise ValueError('Expected 70K accepted per language')
    return result


def controller():
    v6=european._private_module('multilingual_calibration_v6')
    v6.LANGUAGES=dict(LANGUAGES)
    v6.audit_record=provider.audit_record
    v6.generation_request=runtime.generation_request
    v6.review_request=runtime.review_request
    v6.compact_request=runtime.compact_request
    v6.Budget=runtime.Budget
    v6.endpoint_limit=runtime.endpoint_limit
    v6.validate_endpoints=runtime.validate_endpoints
    pilot=european._private_module('multilingual_pilot_v6')
    pilot.v6=v6
    result=european._private_module('multilingual_quarter')
    result.v6,result.pilot=v6,pilot
    result.VERSION=VERSION
    result.PROVIDER='dfm12.wave4_synthetic_specs'
    result.POLICY=dict(european.POLICY)
    result.milestone_targets=quotas
    result.verify=lambda root:verify(root,result)
    return result


def verify(root,c=None):
    root=Path(root).resolve();c=c or controller()
    m=load(root/'manifest.json');seal=file_hash(root/'manifest.json')
    if seal!=load(root/'seal.json')['manifest_sha256']:
        raise ValueError('Manifest seal mismatch')
    if (m['version']!=VERSION or m['groups']!=66 or m['target']!=770000
            or m['languages']!=LANGUAGES or m['provider']!=c.PROVIDER or m['policy']!=c.POLICY):
        raise ValueError('Production policy drift')
    c.v6.verify_pins(root,m)
    config=load(root/'config.json');quotas(config)
    with sqlite3.connect((root/'jobs.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        c.verify_ledger(db,m,config)
        if db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()[0]!=seal:
            raise ValueError('Ledger seal mismatch')
    return m


def prepare(root,seeds,tokenizer):
    root,seeds,tokenizer=map(lambda p:Path(p).resolve(),(root,seeds,tokenizer))
    config=yaml.safe_load(CONFIG.read_text());q=quotas(config)
    receipt=load(seeds/'receipt.json')
    if not receipt['ready'] or file_hash(seeds/'seeds.sqlite')!=receipt['sha256']:
        raise ValueError('Seeds changed or incomplete')
    c=controller();root.mkdir(parents=True,exist_ok=False)
    with lock(root/'controller.lock'):
        ledger=c.Ledger(root/'jobs.sqlite')
        try:
            ledger.initialize(q);write_json(root/'config.json',config)
            dependencies=set([Path(__file__).resolve(),Path(runtime.__file__).resolve(),Path(provider.__file__).resolve(),
                Path(provider._path).resolve(),*european._dependencies(c,provider)])
            manifest=dict(version=VERSION,campaign=config['campaign'],seeds_root=str(seeds),
                tokenizer_dir=str(tokenizer),target=770000,groups=66,languages=LANGUAGES,
                candidate_multiplier=6,milestone='tenth',milestone_divisor=10,
                provider=c.PROVIDER,policy=c.POLICY,
                implementation_pins={str(p):file_hash(p) for p in sorted(dependencies)},
                external_pins={str(p):file_hash(p) for p in european._asset_paths(tokenizer)},
                input_pins={'config.json':file_hash(root/'config.json')},
                default_concurrency_per_server=32,max_concurrency_per_server=64,
                max_kv_cache_utilization=.90,calibration_required_before_bulk=True,
                initial_state=dict(accepted=0,candidates=0,imported=0,fingerprints=0))
            write_json(root/'manifest.json',manifest);seal=file_hash(root/'manifest.json')
            write_json(root/'seal.json',dict(manifest_sha256=seal))
            ledger.db.execute('INSERT INTO metadata VALUES(?,?)',('manifest_sha256',seal))
            ledger.report(root,'prepared')
        finally:
            ledger.close()
    return verify(root)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','verify','run'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--seeds-root',type=Path,default=Path('data/dfm13/wave4/seeds'))
    p.add_argument('--tokenizer-dir',type=Path,default=european.TOKENIZER_DIR)
    p.add_argument('--endpoints',nargs='+')
    p.add_argument('--concurrency-per-server',type=int,default=32)
    a=p.parse_args()
    if a.command=='prepare':
        print(prepare(a.root,a.seeds_root,a.tokenizer_dir))
    elif a.command=='verify':
        print(verify(a.root))
    else:
        if not a.endpoints or not 1<=a.concurrency_per_server<=64:
            p.error('Explicit endpoints and concurrency 1..64 required')
        verify(a.root)
        groups=runtime.approved_groups(a.root)
        asyncio.run(controller().execute(a.root,endpoints=a.endpoints,
            concurrency=a.concurrency_per_server,timeout=600,max_kv_cache_utilization=.90,
            allowed_groups=groups))
