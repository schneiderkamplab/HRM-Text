"""Serialize finished Baltic admission after the DaLA13 successor."""
import argparse
from contextlib import ExitStack
from pathlib import Path
import time
from dfm12.io import load,lock,write_json,file_hash
from scripts.assemble_dfm13_additions import verify_assembly,unready_reason
from scripts.assemble_dfm13_successor import assemble


def run(release,output):
    control=output.with_name(output.name+'-control');control.mkdir(parents=True,exist_ok=True)
    reference=Path('data/dfm13/authoritative-additions.json')
    with lock(control/'.lock'):
        while True:
            prior=load(reference)
            ready=(release/'complete.json').exists()
            predecessor=Path(prior['root']).name=='verified-finished-additions-dala13-20261004-v1'
            write_json(control/'progress.json',dict(phase='waiting',release_ready=ready,predecessor_ready=predecessor))
            if ready and predecessor:break
            time.sleep(30)
        before=file_hash(reference);completion=load(release/'complete.json')
        if not completion['success']:raise ValueError('Baltic release failed')
        base=Path(prior['root']);config=load(base/'registry.snapshot.json')
        names={e['name'] for e in config['additions']}
        for e in load('config/dfm13_sources.json')['additions']:
            if e['name'] not in names and unready_reason(e) is None:
                config['additions'].append(e);names.add(e['name'])
        for e in load(release/'registry.json')['additions']:
            if e['name'] in names:raise ValueError('Duplicate Baltic component')
            config['additions'].append(e);names.add(e['name'])
        registry=control/'registry.json';write_json(registry,config)
        with ExitStack() as fences:
            for e in sorted(config['additions'],key=lambda e:e['name']):
                if e.get('selection_receipt'):fences.enter_context(lock(Path(e['selection_receipt']).parent/'.lock'))
            write_json(control/'progress.json',dict(phase='assembling',entries=len(config['additions'])))
            result=assemble(registry,Path('data/sampled_dfm12'),output)
            if any(e['reason']!='quality_hold_source_fidelity' for e in result['unready_additions']):
                write_json(control/'failure.json',result['unready_additions']);raise ValueError('Unexpected exclusions')
            verify_assembly(output)
            report=dict(status='verified',root=str(output.resolve()),totals=result['totals'],
                missing=result['unready_additions'],assembly_sha256=file_hash(output/'assembly.json'),
                baltic_conversations=completion['conversations'],publication_pending=True,sampling_performed=False)
            write_json(control/'completion-report.json',report)
            with lock(Path('data/dfm13/authoritative-additions.lock')):
                if file_hash(reference)!=before:raise ValueError('Authoritative reference changed; preserve successor without promotion')
                write_json(reference,report)
            print('VERIFIED',report,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--release',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.release,a.output)
