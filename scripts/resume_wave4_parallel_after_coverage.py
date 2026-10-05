"""Authorized CPU-only continuation; never controls audit clients or servers."""
import argparse
from contextlib import closing
import os
from pathlib import Path
import signal
import sqlite3
import time
import psutil

from dfm12.diagnostic_server import identity, pidfd_open, pidfd_signal
from dfm12.io import file_hash, load, lock, write_json


def alive(expected):
    try:
        actual=identity(expected['pid'])
        state=Path(f"/proc/{expected['pid']}/stat").read_text().rsplit(')',1)[1].split()[0]
        return state!='Z' and all(actual[k]==expected[k] for k in ('start_ticks','session_id','cmdline'))
    except (OSError,ProcessLookupError,psutil.NoSuchProcess):return False


def validate_inputs(root):
    requested={'-'.join(p) for p in load(root/'translations/config.json')['requested_pairs']}
    with closing(sqlite3.connect((root/'audit/jobs.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as db:
        registered=dict(db.execute('SELECT name,sha FROM components'))
    pins={};counts={}
    for family,prefix in [('translations','direct-'),('institutional-translations','institutional-')]:
        inventory=root/family/'opus/inventory.json'
        pins[str(inventory)]=file_hash(inventory)
        approved=0
        for pair,item in load(inventory)['pairs'].items():
            if not any(e.get('status')=='approved' for e in item['corpora']):continue
            receipt=root/family/'candidates'/('opus-'+pair)/'receipt.json'
            data=receipt.parent/'candidates.jsonl';state=load(receipt)
            if file_hash(data)!=state['sha256']:raise ValueError('Extraction hash mismatch: '+pair)
            pins[str(receipt)]=file_hash(receipt);pins[str(data)]=state['sha256']
            if pair in requested:
                component=prefix+pair;seal=root/'audit-ready'/component/'receipt.json';sealed=load(seal)
                if (registered.get(component)!=sealed['sha256']
                        or sealed['input_sha256']!=state['sha256']
                        or file_hash(sealed['path'])!=sealed['sha256']):
                    raise ValueError('Registration/sealed source mismatch: '+component)
                pins[str(seal)]=file_hash(seal)
            approved+=1
            print('VERIFIED',family,pair,flush=True)
        counts[family]=approved
    if not all(counts.values()):raise ValueError('Empty approved extraction inventory')
    return dict(counts=counts,pins=pins)


def stop_child(child,parent):
    if not alive(child) or not alive(parent):raise ValueError('Owned CPU identity changed')
    if str(parent['pid'])!=Path(f"/proc/{child['pid']}/stat").read_text().rsplit(')',1)[1].split()[1]:
        raise ValueError('CPU parent changed')
    if child['cmdline'][child['cmdline'].index('-m')+1:] != [
            'dfm12.wave4_cpu','institutional','--root','data/dfm13/wave4','--workers','8']:
        raise ValueError('Not the approved CPU child')
    if parent['cmdline'][parent['cmdline'].index('-m')+1:]!=['scripts.advance_wave4_parallel']:
        raise ValueError('Not the approved parent')
    fd=pidfd_open(child['pid'])
    try:
        if not alive(child):raise ValueError('CPU child changed before signal')
        pidfd_signal(fd,signal.SIGTERM)
    finally:os.close(fd)
    deadline=time.monotonic()+600
    while alive(child) or alive(parent):
        if time.monotonic()>deadline:raise TimeoutError('CPU chain has not exited; no escalation or duplicate')
        time.sleep(1)


def continue_work(root,progress):
    from dfm12.baltic_pivots import main as build_pivots
    from dfm12.wave4_cpu import enqueue
    from dfm12.wave_job_coverage import reconcile
    progress('pivot_build')
    build_pivots(root)
    queued=[]
    progress('pivot_enqueue')
    for receipt in sorted((root/'pivots/candidates').glob('opus-*/receipt.json')):
        state=load(receipt)
        if state['state']!='pivot_candidates_ready':continue
        path=receipt.parent/'candidates.jsonl'
        if file_hash(path)!=state['sha256']:raise ValueError('Pivot output changed')
        component='pivot-'+state['pair'];enqueue(root,component,path);queued.append(component)
    progress('exact_coverage')
    coverage=reconcile(root)
    if coverage.get('exact_payload_coverage') is not True:raise ValueError('Coverage incomplete')
    write_json(root/'parallel-preparation.json',dict(status='direct_and_pivot_preparation_finished',
        queued_pivots=queued,coverage_report=str(root/'pivots/manifest.json'),
        remaining=['audit','accepted-only combined token budgets','export/upload/integration']))
    progress('complete')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('data/dfm13/wave4'))
    p.add_argument('--authorization',type=Path,required=True)
    a=p.parse_args();root=a.root;authorization=load(a.authorization)
    if authorization.get('cpu_continuation_authorized') is not True:raise ValueError('Authorization required')
    if authorization['implementation_sha256']!=file_hash(__file__):raise ValueError('Continuation code changed')
    def progress(phase):
        write_json(root/'coverage-continuation-status.json',dict(time=time.time(),pid=os.getpid(),
            phase=phase,gpu_actions=False,authorization_sha256=file_hash(a.authorization)))
        print('PHASE',phase,flush=True)
    with lock(root/'coverage-continuation.lock'):
        progress('verify_extractions')
        evidence=validate_inputs(root)
        write_json(root/'coverage-continuation-inputs.json',evidence)
        progress('stop_exact_cpu_child')
        if authorization.get('already_stopped'):
            if alive(authorization['child']) or alive(authorization['parent']):
                raise ValueError('Prior CPU chain is still alive; no signal on resume')
        else:
            stop_child(authorization['child'],authorization['parent'])
        with lock(root/'advance-parallel.lock'):
            # Probe old stage locks without holding them across nested enqueue.
            with lock(root/'institutional.lock'),lock(root/'audit/.enqueue.lock'):pass
            continue_work(root,progress)


if __name__=='__main__':main()
