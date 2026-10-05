"""Observe CPU completion; recover one exact, terminal Slovak lock timeout."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil

from dfm12.diagnostic_server import identity
from dfm12.io import file_hash, load, lock, write_json


def alive(pin):
    try:
        process=psutil.Process(pin['pid'])
        if process.status()==psutil.STATUS_ZOMBIE:return False
        current=identity(pin['pid'])
        if any(current[k]!=pin[k] for k in ('start_ticks','session_id','cmdline')):
            raise ValueError('Pinned CPU PID was reused; refuse automatic recovery')
        return True
    except (psutil.NoSuchProcess,FileNotFoundError,ProcessLookupError):return False


def timeout_exit(log):
    with Path(log).open('rb') as stream:
        stream.seek(0,2);length=stream.tell();stream.seek(max(0,length-16384))
        tail=stream.read().decode('utf-8',errors='replace').strip()
    return tail.endswith('TimeoutError: Audit enqueue lock remained busy')


def snapshot(base,root):
    main=base/'parallel-preparation.json'
    coverage=base/'audit/component-job-coverage.json'
    selection=base/'audit/translation-manifest.json'
    additive=root/'enqueue-complete.json'
    main_ready=main.exists() and load(main).get('status')=='direct_and_pivot_preparation_finished'
    covered=coverage.exists() and load(coverage).get('exact_payload_coverage') is True
    selected=selection.exists() and main_ready and load(selection).get('preparation_sha256')==file_hash(main)
    additive_ready=additive.exists() and load(additive).get('cpu_preparation_complete') is True
    return dict(main_preparation_complete=main_ready,exact_coverage=covered,
        selection_activated=selected,slovak_enqueue_complete=additive_ready,
        both_cpu_complete=main_ready and covered and selected and additive_ready,
        audits_complete=False,global_ready=False)


def run(contract_path):
    contract=load(contract_path);base=Path(contract['base']);root=Path(contract['root'])
    status=root/'cpu-completion-watch.json';resume=root/'timeout-resume.json'
    with lock(root/'cpu-completion-watch.lock'):
        while True:
            pin=load(resume)['process'] if resume.exists() else contract['process']
            live=alive(pin);state=snapshot(base,root)
            state.update(time=time.time(),watcher_pid=os.getpid(),observed_pid=pin['pid'],observed_alive=live)
            write_json(status,state)
            print(state,flush=True)
            if state['both_cpu_complete']:return
            if not live and not state['slovak_enqueue_complete']:
                if resume.exists():raise RuntimeError('Successor exited before enqueue completion; no retry loop')
                if not timeout_exit(contract['log']):raise RuntimeError('CPU exit was not the approved lock timeout')
                for path,sha in contract['implementation_pins'].items():
                    if file_hash(path)!=sha:raise ValueError('Recovery implementation changed')
                # The predecessor is terminal. Probe its ownership lock; the new
                # process also acquires it, so concurrent operators fail closed.
                with lock(root/'advance.lock'):pass
                command=[sys.executable,'-u','-m','scripts.advance_wave4_slovak_additive',
                    '--root',str(root),'--base',str(base),'--enqueue-wait-seconds','43200']
                log=Path(contract['resume_log']);log.parent.mkdir(parents=True,exist_ok=True)
                with log.open('xb') as output:
                    child=subprocess.Popen(command,stdout=output,stderr=subprocess.STDOUT,
                        start_new_session=True,env={**os.environ,'CUDA_VISIBLE_DEVICES':''})
                write_json(resume,dict(time=time.time(),previous_process=pin,
                    reason='terminal enqueue lock timeout only',process=identity(child.pid),
                    command=command,log=str(log),preserve_jobs=True))
            time.sleep(30)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract',type=Path,required=True)
    run(parser.parse_args().contract)
