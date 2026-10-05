"""One CPU successor for all finished additions; no sampling or training actions."""
from contextlib import ExitStack
from pathlib import Path
import time
from dfm12.io import load, lock, write_json, file_hash
from scripts.prepare_dfm13_dala_parallel import prepare
from scripts.assemble_dfm13_additions import unready_reason, verify_assembly
from scripts.assemble_dfm13_successor import assemble

ROOT = Path('data/dfm13/verified-all-finished-additions-20261005-v1')
CONTROL = ROOT.with_name(ROOT.name+'-control')


def merge(config, entries):
    old = {e['name']: e for e in config['additions']}
    for entry in entries:
        if entry['name'] in old:
            if old[entry['name']] != entry:
                raise ValueError('Conflicting source: '+entry['name'])
        else:
            config['additions'].append(entry)
            old[entry['name']] = entry


def run():
    ref = Path('data/dfm13/authoritative-additions.json')
    with lock(CONTROL/'.lock'):
        previous = load(ref); before = file_hash(ref)
        base = Path(previous['root'])
        if base.name != 'verified-finished-additions-dala9-20261004-v1':
            raise ValueError('Unexpected predecessor; do not overwrite a newer assembly')
        config = load(base/'registry.snapshot.json')
        saved = load('data/dfm13/verified-finished-additions-dala13-20261004-v1-control/registry.json')
        merge(config, saved['additions'])
        for name in ('dala-remaining21-finalized-20261004-v1', 'dala-baseline-delta-finalized-20261004-v1'):
            finalized = Path('data/dfm13')/name
            cache = CONTROL/(name+'-prepared.json')
            done = finalized/'complete.json'
            if cache.exists():
                prepared = load(cache)
                if prepared['completion_sha256'] != file_hash(done):
                    raise ValueError('Finalization changed')
                entries = prepared['entries']
            else:
                write_json(CONTROL/'progress.json',dict(phase='preparing_local_views',source=name,time=time.time()))
                print('PREPARING',name,flush=True)
                entries = prepare(finalized, CONTROL/'local-views'/name)
                write_json(cache,dict(completion_sha256=file_hash(done),entries=entries))
            merge(config, entries)
        # Preserve existing sealed entries; add only newly eligible central sources.
        names = {e['name'] for e in config['additions']}
        merge(config, [e for e in load('config/dfm13_sources.json')['additions']
                       if e['name'] not in names and unready_reason(e) is None])
        for name in ('baltic-finished-release-20261004-v1','wave4-finished-release-20261004-v1'):
            release = Path('data/dfm13')/name
            if not load(release/'complete.json')['success']:
                raise ValueError('Incomplete release '+name)
            merge(config,load(release/'registry.json')['additions'])
        registry = CONTROL/'registry.json';write_json(registry,config)
        with ExitStack() as fences:
            for e in sorted(config['additions'],key=lambda e:e['name']):
                if e.get('selection_receipt'):
                    fences.enter_context(lock(Path(e['selection_receipt']).parent/'.lock'))
            write_json(CONTROL/'progress.json',dict(phase='verifying_all_sources',entries=len(config['additions']),time=time.time()))
            print('ASSEMBLING',len(config['additions']),flush=True)
            result = assemble(registry,Path('data/sampled_dfm12'),ROOT)
            if any(e['reason'] != 'quality_hold_source_fidelity' for e in result['unready_additions']):
                write_json(CONTROL/'failure.json',result['unready_additions'])
                raise ValueError('Unexpected exclusions; no promotion')
            verify_assembly(ROOT)
            report = dict(status='verified',root=str(ROOT.resolve()),totals=result['totals'],
                          missing=result['unready_additions'],assembly_sha256=file_hash(ROOT/'assembly.json'),
                          sampling_performed=False,time=time.time())
            with lock(Path('data/dfm13/authoritative-additions.lock')):
                if file_hash(ref)!=before:
                    raise ValueError('Authoritative predecessor changed')
                write_json(ref,report)
            write_json(CONTROL/'completion.json',report)
            print('VERIFIED',report,flush=True)


if __name__=='__main__':
    run()
