"""Wait for the running final verifier, then add the separately prepared FO source."""
from pathlib import Path
import time
from dfm12.io import load, lock, write_json, file_hash

ROOT=Path('data/dfm13/verified-all-finished-additions-fo-instruct-20261005-v1')
PREDECESSOR=Path('data/dfm13/verified-all-finished-additions-20261005-v1')
CONTROL=ROOT.with_name(ROOT.name+'-control')


def source_entry(config):
    entries=[e for e in config['additions'] if any(e.get(k)=='Setur/fo-instruct'
             for k in ('repo_id','hf_repo_id','source_repo','source_repo_id'))]
    if not entries:return None
    if len(entries)!=1:raise ValueError('Duplicate Setur/fo-instruct registrations')
    e=entries[0]
    if type(e.get('repeat')) is not int or e['repeat']!=10:
        raise ValueError('Setur/fo-instruct must retain repeat10')
    if not e.get('output') or not e.get('tokenized_path'):return None
    return e


def require_included(root):
    registry=load(root/'registry.snapshot.json')
    entry=source_entry(registry)
    if entry is None:raise ValueError('Setur/fo-instruct missing from sampled assembly')
    matches=[e for e in load(root/'assembly.json')['ready_additions'] if e['name']==entry['name']]
    if len(matches)!=1 or matches[0]['repeat']!=10:
        raise ValueError('Setur/fo-instruct not verified at repeat10')
    return entry


def include_source(config, entry):
    existing = [e for e in config['additions'] if e['name'] == entry['name']]
    if existing:
        if existing != [entry]:
            raise ValueError('FO source already present with a conflicting registration')
    else:
        config['additions'].append(entry)


def run():
    ref=Path('data/dfm13/authoritative-additions.json')
    with lock(CONTROL/'.lock'):
        while True:
            prior=load(ref)
            e=source_entry(load('config/dfm13_sources.json'))
            ready=Path(prior['root']).resolve()==PREDECESSOR.resolve()
            write_json(CONTROL/'progress.json',dict(phase='waiting_verified_predecessor_and_fo_source',
                       predecessor_ready=ready,source_registered=e is not None,required_repo='Setur/fo-instruct',
                       required_repeat=10,time=time.time()))
            if ready and e is not None:break
            time.sleep(20)
        # Import after source readiness so the parent's registered adapter is loaded.
        from scripts.assemble_dfm13_successor import assemble
        from scripts.assemble_dfm13_additions import verify_assembly
        before=file_hash(ref)
        config=load(PREDECESSOR/'registry.snapshot.json')
        include_source(config, e)
        registry=CONTROL/'registry.json';write_json(registry,config)
        write_json(CONTROL/'progress.json',dict(phase='verifying_fo_successor',source=e['name'],time=time.time()))
        result=assemble(registry,Path('data/sampled_dfm12'),ROOT)
        if any(x['reason']!='quality_hold_source_fidelity' for x in result['unready_additions']):
            write_json(CONTROL/'failure.json',result['unready_additions'])
            raise ValueError('Unexpected source exclusion; no promotion')
        verify_assembly(ROOT);require_included(ROOT)
        report=dict(status='verified',root=str(ROOT.resolve()),totals=result['totals'],
                    missing=result['unready_additions'],assembly_sha256=file_hash(ROOT/'assembly.json'),
                    required_repo='Setur/fo-instruct',required_repeat=10,sampling_performed=False,time=time.time())
        with lock(Path('data/dfm13/authoritative-additions.lock')):
            if file_hash(ref)!=before:raise ValueError('Predecessor changed; no promotion')
            write_json(ref,report)
        write_json(CONTROL/'completion.json',report)
        print('VERIFIED_FO_SUCCESSOR',report,flush=True)


if __name__=='__main__':
    try:run()
    except Exception as exc:
        write_json(CONTROL/'failure.json',dict(error_type=type(exc).__name__,message=str(exc),time=time.time()))
        raise
