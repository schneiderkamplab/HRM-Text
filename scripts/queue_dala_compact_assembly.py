"""Wait for terminal DaLA CPU finalization, then build a verified additions successor."""
import argparse
from contextlib import ExitStack
from pathlib import Path
import time

from dfm12.io import load, lock, write_json, file_hash
from dfm12.dala_compact_assembly import prepare
from scripts.assemble_dfm13_additions import verify_assembly
from scripts.assemble_dfm13_successor import assemble


def run(finalized, output):
    control = output.with_name(output.name+'-control');control.mkdir(parents=True, exist_ok=True)
    reference = Path('data/dfm13/authoritative-additions.json')
    with lock(control/'.lock'):
        while not (finalized/'complete.json').exists() or not reference.exists():
            write_json(control/'progress.json', dict(phase='waiting', finalization_ready=(finalized/'complete.json').exists(),
                predecessor_ready=reference.exists(), time=time.time()))
            time.sleep(20)
        previous = load(reference);previous_sha = file_hash(reference)
        root = Path(previous['root'])
        if file_hash(root/'assembly.json') != previous['assembly_sha256']: raise ValueError('Predecessor reference drift')
        config = load(root/'registry.snapshot.json')
        added = prepare(finalized, control/'local-views')
        names = {e['name'] for e in config['additions']}
        if any(e['name'] in names for e in added): raise ValueError('DaLA duplicate component')
        config['additions'].extend(added)
        registry = control/'registry.json';write_json(registry, config)
        with ExitStack() as fences:
            for e in sorted(config['additions'], key=lambda e:e['name']):
                if e.get('selection_receipt'):
                    fences.enter_context(lock(Path(e['selection_receipt']).parent/'.lock'))
            write_json(control/'progress.json', dict(phase='assembling', added_components=len(added)))
            result = assemble(registry, Path('data/sampled_dfm12'), output)
            if any(e['reason'] != 'quality_hold_source_fidelity' for e in result['unready_additions']):
                write_json(control/'failure.json', result['unready_additions'])
                raise ValueError('Unexpected assembly exclusions; no promotion')
            verify_assembly(output)
            report = dict(status='verified', root=str(output.resolve()), totals=result['totals'],
                missing=result['unready_additions'], assembly_sha256=file_hash(output/'assembly.json'),
                dala_components=len(added), dala_rows=sum(e['rows'] for e in added),
                dala_tokens=sum(e['tokens'] for e in added),
                dala_waiting=load(finalized/'complete.json')['waiting'],
                publication_pending=True, sampling_performed=False, time=time.time())
            write_json(control/'completion-report.json', report)
            with lock(Path('data/dfm13/authoritative-additions.lock')):
                if file_hash(reference) != previous_sha: raise ValueError('Another authoritative successor won; do not overwrite')
                write_json(reference, report)
            print('VERIFIED', report, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--finalized', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a=p.parse_args()
    run(a.finalized,a.output)
