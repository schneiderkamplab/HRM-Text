"""Record shared-server work and throughput every two minutes; never kill workloads."""
import json
from contextlib import closing
from pathlib import Path
import re
import subprocess
import sqlite3
import sys
import time
import urllib.request

import psutil

from dfm12.io import lock, write_json

ROOT = Path('logs/dfm13/wave4/monitor')


def ensure_wave4_booster(last_start):
    """Replace drained Baltic demand without interrupting either campaign."""
    if time.monotonic() - last_start < 180:
        return last_start
    baltic = Path('data/dfm13/baltic/audit/jobs.sqlite').resolve()
    wave4 = Path('data/dfm13/wave4/audit/jobs.sqlite').resolve()
    output = 'logs/dfm13/wave4/audit-booster'
    if not baltic.exists() or not wave4.exists():
        return last_start
    with closing(sqlite3.connect(baltic.as_uri() + '?mode=ro', uri=True, timeout=10)) as db:
        if db.execute("SELECT 1 FROM jobs WHERE status IN ('pending','running') LIMIT 1").fetchone():
            return last_start
    for proc in psutil.process_iter(['cmdline']):
        args = proc.info['cmdline'] or []
        if 'dfm12.european_stage' in args and output in args:
            return last_start
    with closing(sqlite3.connect(wave4.as_uri() + '?mode=ro', uri=True, timeout=10)) as db:
        if not db.execute("SELECT 1 FROM jobs WHERE stage='audit' AND status='pending' LIMIT 1").fetchone():
            return last_start
    args = [sys.executable, '-u', '-m', 'dfm12.european_stage', '--database', str(wave4),
        '--stage', 'audit', '--output', output, '--concurrency', '320', '--max-concurrency', '320']
    for port in range(8800, 8808):
        args.extend(['--endpoint', f'http://127.0.0.1:{port}/v1'])
    with Path(output + '.log').open('a') as out:
        proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=out,
            stderr=subprocess.STDOUT, start_new_session=True)
    print('Baltic audit drained; added wave4 audit demand', proc.pid, flush=True)
    return time.monotonic()


def ensure_wave4_client(last_start, kind='audit', stage='audit', concurrency=64, wave='wave4'):
    if wave not in ('baltic', 'wave4'):
        raise ValueError('Unsupported wave')
    database = Path(f'data/dfm13/{wave}/{kind}/jobs.sqlite').resolve()
    if not database.exists() or time.monotonic()-last_start < 180:
        return last_start
    for proc in psutil.process_iter(['cmdline']):
        args = proc.info['cmdline'] or []
        if 'dfm12.european_stage' in args and '--database' in args:
            if (Path(args[args.index('--database')+1]).resolve() == database
                    and '--stage' in args and args[args.index('--stage')+1] == stage):
                return last_start
    with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True,timeout=10)) as db:
        if not db.execute("SELECT 1 FROM jobs WHERE stage=? AND status='pending' LIMIT 1", (stage,)).fetchone():
            return last_start
    args = [sys.executable,'-u','-m','dfm12.european_stage','--database',str(database),
        '--stage',stage,'--output',f'logs/dfm13/{wave}/{kind}-{stage}-client',
        '--concurrency',str(concurrency),'--max-concurrency',str(concurrency)]
    for port in range(8800,8808):
        args.extend(['--endpoint',f'http://127.0.0.1:{port}/v1'])
    with Path(f'logs/dfm13/{wave}/{kind}-{stage}-client.log').open('a') as out:
        proc = subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=out,
            stderr=subprocess.STDOUT,start_new_session=True)
    print('Restarted drained/exited client',wave,kind,stage,proc.pid,flush=True)
    return time.monotonic()


def sample():
    result = dict(time=time.time(),servers={})
    result['gpu'] = subprocess.check_output(['nvidia-smi',
        '--query-gpu=index,utilization.gpu,memory.used','--format=csv,noheader,nounits'],text=True,timeout=15)
    for port in range(8800,8808):
        try:
            raw = urllib.request.urlopen(f'http://127.0.0.1:{port}/metrics',timeout=10).read().decode()
            values = {}
            for metric in ('num_requests_running','num_requests_waiting','kv_cache_usage_perc',
                           'request_success_total','generation_tokens_total','prompt_tokens_total'):
                values[metric] = sum(float(line.rsplit(' ',1)[1]) for line in raw.splitlines()
                    if re.match(r'^vllm:'+metric+r'(?:\{| )',line))
            result['servers'][str(port)] = values
        except Exception as exc:
            result['servers'][str(port)] = dict(error=str(exc))
    return result


def main():
    with lock(ROOT/'monitor.lock'):
        previous = None
        starts = {}
        while True:
            try:
                starts['booster'] = ensure_wave4_booster(starts.get('booster', 0))
                for kind, stage, concurrency in [('audit', 'audit', 64),
                                                  ('repair', 'generate', 32),
                                                  ('repair', 'audit', 32)]:
                    key = (kind, stage)
                    starts[key] = ensure_wave4_client(starts.get(key, 0), kind, stage, concurrency)
                for stage in ('generate', 'audit'):
                    key = ('baltic', stage)
                    starts[key] = ensure_wave4_client(starts.get(key, 0), 'repair', stage, 32, wave='baltic')
            except (OSError,sqlite3.Error,psutil.Error) as exc:
                print('Client check failed; no process changed:',str(exc),flush=True)
            current = sample()
            if previous:
                elapsed = current['time']-previous['time']
                for port,values in current['servers'].items():
                    old = previous['servers'].get(port,{})
                    if 'error' not in values and 'request_success_total' in old:
                        values['requests_per_minute'] = max(0,values['request_success_total']-old['request_success_total'])*60/elapsed
                        values['output_tokens_per_second'] = max(0,values['generation_tokens_total']-old['generation_tokens_total'])/elapsed
            write_json(ROOT/'latest.json',current)
            with (ROOT/'history.jsonl').open('a') as out:
                out.write(json.dumps(current)+'\n')
            print(json.dumps(current),flush=True)
            previous=current
            time.sleep(120)


if __name__ == '__main__':
    main()
