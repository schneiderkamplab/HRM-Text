"""Durable four-model multiview run; credentials stay in memory, no server takeover."""
import asyncio
import getpass
import os
from pathlib import Path
import subprocess
import sys
import time
from collections import Counter

from audit_pipeline.runtime import EndpointUnavailable
from dfm12.io import load, lock, write_json
from scripts.dfm16_judge_ensemble_study import judge
from scripts.prepare_dfm16_atomic_judges import ROOT as ATOMIC
from scripts.prepare_dfm16_multiview_judges import ROOT
from scripts.queue_dfm16_stories_qwen import audited_records


def summarize():
    totals = {}
    for name in ('odin', 'qwen27b', 'flash', 'mimir'):
        stage = ROOT/name/('probe' if name == 'mimir' else '')
        counts = Counter()
        for source, result in audited_records(stage):
            counts[f'{source["view"]}/{source["aspect"]}/'+result.get('review', {}).get('decision', result['status'])] += 1
        totals[name] = dict(counts)
    write_json(ROOT/'summary.json', totals)


def work(key):
    with lock(ROOT/'.campaign.lock'):
        processes = {}
        for name in ('qwen27b', 'flash', 'mimir'):
            if name == 'mimir':
                command = [sys.executable, '-m', 'scripts.run_dfm16_mimir_judge_comparison',
                           '--prepared-probe', '--root', str(ROOT/name)]
            else:
                command = [sys.executable, '-m', 'scripts.dfm16_judge_ensemble_study', name,
                           '--root', str(ROOT)]
            with (ROOT/(name+'.log')).open('a') as log:
                processes[name] = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL)
        write_json(ROOT/'campaign.json', dict(phase='running', pid=os.getpid(),
            clients={name:p.pid for name,p in processes.items()}, production_authorized=False))
        # One API client at a time: do not multiply the account request quota.
        prior = ATOMIC/'odin/audit/pipeline/state.json'
        while prior.exists() and load(prior)['phase'] == 'running':
            time.sleep(10)
        odin_error = None
        for attempt in range(6):
            try:
                asyncio.run(judge(ROOT, 'odin', key))
                break
            except EndpointUnavailable:
                if attempt == 5:
                    odin_error = 'EndpointUnavailable'
            except Exception as exc:
                odin_error = type(exc).__name__
                break
        codes = {name: process.wait() for name,process in processes.items()}
        summarize()
        from scripts.report_dfm16_multiview_judges import main as report
        report()
        write_json(ROOT/'campaign.json', dict(phase='complete' if not odin_error and not any(codes.values()) else 'failed',
            exit_codes=codes, odin_error=odin_error, production_authorized=False))


def main():
    if '--worker' in sys.argv:
        work(sys.stdin.readline().rstrip('\n'))
        return
    key = os.environ.get('ODIN_API_KEY') or getpass.getpass('API key: ')
    if '--detach' in sys.argv:
        with (ROOT/'campaign.log').open('a') as log:
            process = subprocess.Popen([sys.executable, '-m', 'scripts.run_dfm16_multiview_judges', '--worker'],
                stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, text=True)
            process.stdin.write(key+'\n')
            process.stdin.close()
        print(f'Campaign PID {process.pid}; log {ROOT}/campaign.log', flush=True)
    else:
        work(key)


if __name__ == '__main__':
    main()
