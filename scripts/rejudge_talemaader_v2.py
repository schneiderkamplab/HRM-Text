"""Rejudge saved Talemaader answers without touching model generations or old scores."""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import time
import zipfile

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / 'dfm-evals/dfm_evals/tasks/talemaader/prompts.py'
spec = importlib.util.spec_from_file_location('talemaader_judgment_prompts', PROMPTS)
prompts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prompts)
PREFIX = 'dfm_eval/generative-talemaader/model_graded_fact_v2'
JUDGE = 'gemma-4-e4b-judge'


def atomic(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w') as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    temp.replace(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def load_samples(point):
    records = {}
    for filename in point['inputs']:
        with zipfile.ZipFile(filename) as archive:
            for name in archive.namelist():
                if not name.startswith('samples/') or not name.endswith('.json'):
                    continue
                sample = json.loads(archive.read(name))
                target = sample['target']
                if isinstance(target, list):
                    target = '\n'.join(target)
                item = dict(id=str(sample['id']),
                            talemaade_udtryk=sample['metadata']['talemaade_udtryk'],
                            criterion=target, answer=sample['output']['completion'])
                if not all(isinstance(item[k], str) for k in item):
                    raise ValueError(f'Unexpected sample schema: {filename}:{name}')
                if item['id'] in records and records[item['id']] != item:
                    raise ValueError(f'Conflicting duplicate sample: {point["id"]}:{item["id"]}')
                records[item['id']] = item
    if len(records) != point['expected_n']:
        raise ValueError(f'{point["id"]}: expected {point["expected_n"]}, got {len(records)}')
    return list(records.values())


def query(item):
    return prompts.build_judge_prompt(**{k: item[k] for k in ('talemaade_udtryk', 'criterion', 'answer')})


def cache_key(item):
    return digest({'model': JUDGE, 'prompt': query(item), 'max_tokens': 64, 'temperature': 0})


def load_cache(path):
    results = {}
    if path.exists():
        with path.open() as f:
            for line in f:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue  # An interrupted final write is retried, never counted.
                if row.get('value') in (0, 0.5, 1) and not row.get('error'):
                    results[row['key']] = row
    return results


def aggregate(point, items, results):
    values = [results[cache_key(item)]['value'] for item in items]
    n = len(values)
    if not n:
        raise ValueError('Empty evaluation')
    mean = sum(values) / n
    se = (sum((v - mean)**2 for v in values) / (n - 1) / n)**0.5 if n > 1 else 0.0
    row = {'dfm_eval/epoch': point['epoch'], f'{PREFIX}/accuracy': mean,
           f'{PREFIX}/accuracy_stderr': se, f'{PREFIX}/n': n}
    if point.get('train_step') is not None:
        row['dfm_eval/train_step'] = point['train_step']
    return row


async def judge(session, url, item):
    prompt = query(item)
    calls = []
    for attempt in range(2):
        payload = {'model': JUDGE, 'messages': [{'role': 'user', 'content': prompt}],
                   'temperature': 0, 'max_tokens': 64}
        for retry in range(3):
            try:
                async with session.post(url + '/v1/chat/completions', json=payload) as response:
                    response.raise_for_status()
                    result = await response.json()
                break
            except (aiohttp.ClientError, asyncio.TimeoutError):
                if retry == 2:
                    raise
                await asyncio.sleep(retry + 1)
        calls.append(result)
        choice = result['choices'][0]
        try:
            if choice.get('finish_reason') != 'stop':
                raise prompts.InvalidJudgmentError('Truncated judgment')
            value = prompts.parse_judgment(choice['message']['content'])
            return dict(key=cache_key(item), value=value, calls=calls, endpoint=url, time=time.time())
        except prompts.InvalidJudgmentError:
            prompt += '\nSvar kun med en af: GRADE: C, GRADE: P, GRADE: I.'
    return dict(key=cache_key(item), error='invalid_judgment', calls=calls, endpoint=url, time=time.time())


async def run(args):
    out = args.output
    started = time.time()
    results = load_cache(out / 'judgments.jsonl')
    timeout = aiohttp.ClientTimeout(total=180)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for url in args.urls:
            deadline = time.time() + 900
            while True:
                try:
                    async with session.get(url + '/health') as response:
                        response.raise_for_status()
                    break
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    if time.time() >= deadline:
                        raise RuntimeError(f'Judge unavailable: {url}')
                    await asyncio.sleep(5)
        while True:
            manifest = json.loads(args.manifest.read_text())
            points = [p for p in manifest['points'] if p.get('status', 'ready') == 'ready']
            items_by_point = {p['id']: load_samples(p) for p in points}
            work = {}
            for items in items_by_point.values():
                for item in items:
                    key = cache_key(item)
                    if key not in results:
                        work[key] = item
            queue = asyncio.Queue()
            for item in work.values():
                queue.put_nowait(item)
            completed = 0
            failures = []
            last_progress = 0
            # One event loop owns this append-only ledger; workers never race writes.
            ledger_path = out / 'judgments.jsonl'
            if ledger_path.exists() and ledger_path.stat().st_size:
                with ledger_path.open('rb+') as repair:
                    repair.seek(-1, os.SEEK_END)
                    if repair.read(1) != b'\n':
                        repair.write(b'\n')
            with (out / 'judgments.jsonl').open('a') as ledger:
                async def worker(url):
                    nonlocal completed, last_progress
                    while not queue.empty():
                        item = queue.get_nowait()
                        try:
                            result = await judge(session, url, item)
                        except Exception as exc:
                            result = dict(key=cache_key(item), error=f'{type(exc).__name__}: {exc}',
                                          endpoint=url, time=time.time())
                        ledger.write(json.dumps(result, ensure_ascii=False) + '\n')
                        ledger.flush()
                        if 'error' in result:
                            failures.append(result)
                        else:
                            results[result['key']] = result
                        completed += 1
                        if time.time() - last_progress >= 10:
                            os.fsync(ledger.fileno())
                            status = dict(unique_queries=len(work), completed=completed, failed=len(failures),
                                          cached=len(results), remaining=queue.qsize(), points=len(points),
                                          elapsed_s=time.time()-started, time=time.time())
                            atomic(out / 'progress.json', status)
                            print(json.dumps(status), flush=True)
                            last_progress = time.time()
                        queue.task_done()
                await asyncio.gather(*(worker(url) for url in args.urls))
                os.fsync(ledger.fileno())
            rows = []
            for point in points:
                items = items_by_point[point['id']]
                if not all(cache_key(item) in results for item in items):
                    continue
                row = aggregate(point, items, results)
                atomic(out / f'{point["id"]}.json', dict(point=point, row=row,
                       prompt_sha256=digest(prompts.JUDGE_INSTRUCTIONS_V2)))
                rows.append(row)
            rows.sort(key=lambda r: r['dfm_eval/epoch'])
            atomic(out / 'rows.json', rows)
            if failures:
                raise RuntimeError(f'{len(failures)} judgments failed; see ledger, resume retries failures only')
            if manifest.get('partial'):
                print('Available points finished; waiting for complete inventory', flush=True)
                await asyncio.sleep(30)
                continue
            if len(rows) != len(manifest['points']):
                raise RuntimeError('Inventory contains unavailable points; refusing partial sync')
            atomic(out / 'completed.json', dict(run_path=manifest['run_path'], points=len(rows),
                   manifest_sha256=digest(manifest), rows_sha256=digest(rows), finished=time.time()))
            return


def stop_owned_servers(out):
    for receipt in out.glob('judge-gpu*.json'):
        data = json.loads(receipt.read_text())
        pid = data['pid']
        try:
            command = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
            if b'scripts/transformers_openai_server.py' not in command or str(data['port']).encode() not in command:
                continue
            os.kill(pid, signal.SIGTERM)
        except (FileNotFoundError, ProcessLookupError):
            pass


def sync(args):
    while not (args.output / 'completed.json').exists():
        if (args.output / 'failed.json').exists():
            raise RuntimeError('Rejudging failed; inspect failed.json before retrying sync')
        receipt = args.output/'runner.json'
        if receipt.exists() and not Path(f'/proc/{json.loads(receipt.read_text())["pid"]}').exists():
            raise RuntimeError('Rejudge client exited without a completion receipt')
        if not args.wait:
            raise RuntimeError('Rejudging is incomplete')
        time.sleep(30)
    complete = json.loads((args.output / 'completed.json').read_text())
    rows = json.loads((args.output / 'rows.json').read_text())
    if digest(rows) != complete['rows_sha256'] or len(rows) != complete['points']:
        raise ValueError('Completed rows changed')
    synced = args.output / 'synced.json'
    if synced.exists():
        if json.loads(synced.read_text())['rows_sha256'] != complete['rows_sha256']:
            raise ValueError('This output directory was already synced with a different point set')
        return
    for command in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            argv = command.read_bytes().split(b'\0')
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if any(arg == b'pretrain.py' or arg.endswith(b'/pretrain.py') for arg in argv):
            raise RuntimeError('Refusing a competing W&B history writer while training is active')
    manifest = json.loads((args.output/'manifest.json').read_text())
    for point in manifest['points']:
        report = json.loads((args.output/f'{point["id"]}.json').read_text())
        if not point.get('merged_metrics'):
            continue
        path = Path(point['merged_metrics']).with_name('merged_metrics_v2.json')
        artifact = dict(epoch=point['epoch'], step=point.get('train_step'),
                        num_samples=point['expected_n'], inputs=point['inputs'],
                        metrics={k: v for k, v in report['row'].items() if k.startswith(PREFIX + '/')})
        if path.exists() and json.loads(path.read_text()) != artifact:
            raise ValueError(f'Existing versioned artifact differs: {path}')
        atomic(path, artifact)
    import wandb
    entity, project, run_id = complete['run_path'].split('/')
    run = wandb.init(entity=entity, project=project, id=run_id, resume='must')
    try:
        run.define_metric('dfm_eval/epoch')
        for key in sorted(set().union(*(set(row) for row in rows)) - {'dfm_eval/epoch'}):
            run.define_metric(key, step_metric='dfm_eval/epoch', summary='last')
        for row in rows:
            run.log(row, commit=True)
        for row in rows:
            label = str(row['dfm_eval/epoch']).replace('.', 'p')
            for key, value in row.items():
                if key.startswith(PREFIX + '/'):
                    run.summary[f'{key}/epoch_{label}'] = value
    finally:
        run.finish()
    atomic(args.output / 'synced.json', dict(**complete, synced=time.time()))


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('action', choices=('run', 'sync'))
    parser.add_argument('--output', type=Path, default=ROOT/'logs/rejudge_talemaader_v2')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--urls', nargs='+', default=[f'http://127.0.0.1:{38600+i}' for i in range(8)])
    parser.add_argument('--wait', action='store_true')
    parser.add_argument('--stop-owned-servers', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    args.manifest = args.manifest or args.output/'manifest.json'
    with (args.output/f'{args.action}.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'sync':
            sync(args)
        else:
            (args.output / 'failed.json').unlink(missing_ok=True)
            (args.output / 'completed.json').unlink(missing_ok=True)
            try:
                asyncio.run(run(args))
            except Exception as exc:
                atomic(args.output / 'failed.json', dict(error=f'{type(exc).__name__}: {exc}', time=time.time()))
                raise
            finally:
                if args.stop_owned_servers:
                    stop_owned_servers(args.output)


if __name__ == '__main__':
    main()
