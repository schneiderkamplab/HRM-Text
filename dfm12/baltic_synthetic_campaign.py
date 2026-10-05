"""Prepare and run Baltic 70K/language through the existing audited controller."""
import argparse
import asyncio
from pathlib import Path
import sqlite3

import yaml

from . import european_synthetic_campaign as european
from . import baltic_synthetic_specs as provider
from . import wave_synthetic_runtime as runtime
from .io import file_hash, load, lock, write_json
from .multilingual_targets import targets

VERSION = 'dfm13-baltic-synthetic-v2'
CONFIG = Path(__file__).resolve().parents[1]/'config/dfm13_baltic_synthetic.yaml'


def quotas(config, milestone='tenth', divisor=None):
    from .multilingual_tasks import MODEL
    if (set(config['languages']) != set(provider.LANGUAGES)
            or set(config['families']) != european.FAMILIES
            or config['generator'] != MODEL or config['auditor'] != MODEL
            or config['audit_every_candidate'] is not True
            or config['max_rendered_example_tokens'] != 4096
            or config['repeat'] != 1 or milestone != 'tenth'
            or config['milestone_divisors']['tenth'] != 10):
        raise ValueError('Unexpected Baltic policy')
    result = targets(config, milestone)
    for row in result:
        row['repo_id'] = f"schneiderkamplab/dfm13-multilingual-{row['family']}-{row['language']}"
    for language in provider.LANGUAGES:
        if sum(r['accepted_target'] for r in result if r['language'] == language) != 70000:
            raise ValueError('Exactly 70K accepted conversations per language required')
    return result


def controller():
    # Never patch imported/live European or original-seven modules.
    v6 = european._private_module('multilingual_calibration_v6')
    v6.LANGUAGES = dict(provider.LANGUAGES)
    v6.audit_record = provider.audit_record
    v6.generation_request = runtime.generation_request
    v6.review_request = runtime.review_request
    v6.compact_request = runtime.compact_request
    v6.Budget = runtime.Budget
    v6.endpoint_limit = runtime.endpoint_limit
    v6.validate_endpoints = runtime.validate_endpoints
    pilot = european._private_module('multilingual_pilot_v6')
    pilot.v6 = v6
    result = european._private_module('multilingual_quarter')
    result.v6, result.pilot = v6, pilot
    result.VERSION = VERSION
    result.PROVIDER = 'dfm12.baltic_synthetic_specs'
    result.POLICY = dict(european.POLICY)
    result.milestone_targets = quotas
    result.verify = lambda root: verify(root, result)
    return result


def dependencies(c):
    return sorted(set([Path(__file__).resolve(), Path(runtime.__file__).resolve(), Path(provider.__file__).resolve(),
        Path(provider._path).resolve(), *european._dependencies(c, provider)]))


def prepare(root, seeds_root, tokenizer_dir, config_path=CONFIG):
    root, seeds_root = Path(root).resolve(), Path(seeds_root).resolve()
    config = yaml.safe_load(Path(config_path).read_text())
    q = quotas(config)
    receipt = load(seeds_root/'receipt.json')
    if not receipt['ready'] or file_hash(seeds_root/'seeds.sqlite') != receipt['sha256']:
        raise ValueError('Seed database not ready or changed')
    c = controller()
    root.mkdir(parents=True, exist_ok=False)
    with lock(root/'controller.lock'):
        ledger = c.Ledger(root/'jobs.sqlite')
        try:
            ledger.initialize(q)
            write_json(root/'config.json', config)
            manifest = dict(version=VERSION, campaign=config['campaign'],
                seeds_root=str(seeds_root), tokenizer_dir=str(Path(tokenizer_dir).resolve()),
                target=140000, groups=12, languages=provider.LANGUAGES,
                candidate_multiplier=6, milestone='tenth', milestone_divisor=10,
                provider=c.PROVIDER, policy=c.POLICY,
                implementation_pins={str(p):file_hash(p) for p in dependencies(c)},
                external_pins={str(p):file_hash(p) for p in european._asset_paths(tokenizer_dir)},
                input_pins={'config.json':file_hash(root/'config.json')},
                default_concurrency_per_server=32, max_concurrency_per_server=64,
                max_kv_cache_utilization=.90, calibration_required_before_bulk=True,
                initial_state=dict(accepted=0,candidates=0,imported=0,fingerprints=0))
            write_json(root/'manifest.json', manifest)
            seal = file_hash(root/'manifest.json')
            write_json(root/'seal.json',dict(manifest_sha256=seal))
            ledger.db.execute('INSERT INTO metadata VALUES(?,?)',('manifest_sha256',seal))
            ledger.report(root,'prepared')
        finally:
            ledger.close()
    return verify(root)


def verify(root, c=None):
    root = Path(root).resolve()
    c = c or controller()
    m = load(root/'manifest.json')
    seal = file_hash(root/'manifest.json')
    if seal != load(root/'seal.json')['manifest_sha256']:
        raise ValueError('Manifest changed')
    if (m['version'] != VERSION or m['groups'] != 12 or m['target'] != 140000
            or m['languages'] != provider.LANGUAGES or m['provider'] != c.PROVIDER
            or m['policy'] != c.POLICY):
        raise ValueError('Campaign policy drift')
    c.v6.verify_pins(root,m)
    config = load(root/'config.json')
    quotas(config)
    with sqlite3.connect((root/'jobs.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        c.verify_ledger(db,m,config)
        if db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()[0] != seal:
            raise ValueError('Ledger seal mismatch')
    return m


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','verify','run'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--seeds-root',type=Path)
    p.add_argument('--tokenizer-dir',type=Path,default=european.TOKENIZER_DIR)
    p.add_argument('--endpoints',nargs='+')
    p.add_argument('--concurrency-per-server',type=int,default=32)
    args = p.parse_args()
    if args.command == 'prepare':
        if not args.seeds_root:
            p.error('--seeds-root required')
        print(prepare(args.root,args.seeds_root,args.tokenizer_dir))
    elif args.command == 'verify':
        print(verify(args.root))
    else:
        if not args.endpoints or not 1 <= args.concurrency_per_server <= 64:
            p.error('Explicit shared endpoints and concurrency 1..64 required')
        # A calibration receipt is deliberately not fabricated by preparation.
        groups = runtime.approved_groups(args.root)
        c = controller()
        asyncio.run(c.execute(args.root,endpoints=args.endpoints,
            concurrency=args.concurrency_per_server,timeout=600,max_kv_cache_utilization=.90,
            allowed_groups=groups))


if __name__ == '__main__':
    main()
