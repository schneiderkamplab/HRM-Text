"""Post-terminal Arena repairs. Candidate outputs only; never exports/admission."""
import argparse
import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import time

P = Path(__file__).with_name('dfm13_arena_bulk_reasonfirst.py')
spec = importlib.util.spec_from_file_location('_repair_strong', P)
strong = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strong)
base = strong.base


def transport(payload):
    result = copy.deepcopy(payload)
    def strip(value):
        if isinstance(value, dict):
            if value.get('type') == 'string':
                value.pop('minLength', None)
                value.pop('maxLength', None)
            for child in value.values():
                strip(child)
        elif isinstance(value, list):
            for child in value:
                strip(child)
    strip(result['response_format'])
    return result


def corrected(row, content):
    if not isinstance(content, str) or not content.strip():
        raise ValueError('Empty correction')
    result = copy.deepcopy(row)
    result['messages'][result['target_message_index']]['content'] = content
    return result


def correction_request(row, reason):
    payload = strong.request(row)
    schema = base.obj(dict(reason={'type': 'string', 'maxLength': 2400},
        status={'type': 'string', 'enum': ['corrected', 'needs_review']},
        content={'type': 'string'}))
    payload['messages'] = [dict(role='system', content=(
        'Correct only the designated assistant target for substantive correctness, instruction '
        'following and completeness. Preserve language, intent, history and existing tool metadata. '
        'Do not invent facts, external verification, actions or hidden capabilities. If correction '
        'requires unavailable evidence, changing tool calls, or cannot be completed safely, return '
        'needs_review. Return JSON reason, status, content. Content is the complete replacement, '
        'not a patch. The supplied audit reason is fallible; independently check it.')),
        dict(role='user', content=json.dumps(dict(**base.visible(row), audit_reason=reason), ensure_ascii=False))]
    payload['response_format']['json_schema']['schema'] = schema
    return payload


def destination(verdict):
    return {'keep': 'accepted', 'reject': 'rejected'}.get(verdict, 'needs_review')


def readonly(path):
    return sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True)


def terminal(db, total):
    counts = dict(db.execute('SELECT status,count(*) FROM jobs GROUP BY status'))
    return sum(counts.values()) == total and not any(counts.get(k, 0) for k in ('pending', 'inflight'))


def verify(root):
    plan = base.load(root/'plan.json')
    if base.file_hash(root/'plan.json') != base.load(root/'seal.json')['sha256']:
        raise ValueError('Plan seal drift')
    for path, digest in plan['pins'].items():
        if base.file_hash(path) != digest:
            raise ValueError('Pinned input drift: ' + path)
    return plan


def prepare(root, source):
    root.mkdir(parents=True, exist_ok=True)
    with base.lock(root/'controller.lock'):
        if (root/'plan.json').exists():
            raise ValueError('Already prepared')
        manifest = base.load(source/'manifest.json')
        pins = dict(manifest['pins'])
        for path in (source/'manifest.json', source/'seal.json', Path(__file__).resolve(),
                     base.ROOT/'tests/test_dfm13_arena_repairs.py'):
            pins[str(path)] = base.file_hash(path)
        plan = dict(source=str(source), manifest=manifest, pins=pins, own_per_server=128,
                    shared_cap=512, reserve=16, max_kv=.90, max_attempts=3,
                    timeout=600, no_admission=True, no_upload=True,
                    fresh_context_same_model=True, created=time.time())
        base.write_json(root/'plan.json', plan)
        base.write_json(root/'seal.json', dict(sha256=base.file_hash(root/'plan.json')))
        verify(root)


def snapshot(root, plan):
    source = Path(plan['source'])
    if (root/'input.sqlite').exists():
        if base.file_hash(root/'input.sqlite') != base.load(root/'snapshot.json')['sha256']:
            raise ValueError('Snapshot drift')
        return True
    try:
        with base.lock(source/'controller.lock'):
            with readonly(source/'ledger.sqlite') as db:
                if not terminal(db, plan['manifest']['total']):
                    return False
                with sqlite3.connect(root/'input.tmp.sqlite') as target:
                    db.backup(target)
            (root/'input.tmp.sqlite').replace(root/'input.sqlite')
            base.write_json(root/'snapshot.json', dict(sha256=base.file_hash(root/'input.sqlite'), time=time.time()))
        return True
    except BlockingIOError:
        return False


async def run(root, plan):
    import aiohttp
    import jsonschema
    manifest = plan['manifest']
    asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=8))
    for source in manifest['sources']:
        if base.file_hash(source['path']) != source['sha256']:
            raise ValueError('Source bytes changed')
    db = sqlite3.connect(root/'ledger.sqlite')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS attempts(seq INTEGER,stage TEXT,n INTEGER,status TEXT,hash TEXT,record TEXT,PRIMARY KEY(seq,stage,n))')
    for table in ('accepted', 'rejected', 'needs_review'):
        db.execute(f'CREATE TABLE IF NOT EXISTS {table}(seq INTEGER PRIMARY KEY,record TEXT)')
    db.execute("UPDATE attempts SET status='interrupted_unknown' WHERE status='inflight'")
    db.commit()
    tok = strong.bulk.engine.tokenizer(manifest['tokenizer_dir'])
    queues = [asyncio.Queue() for _ in manifest['endpoints']]
    active = [0]*len(queues)
    metrics = [None]*len(queues)
    writers = [base.RawResponseWriter(root/'raw'/str(i)) for i in range(len(queues))]
    finished = set()
    for table in ('accepted', 'rejected', 'needs_review'):
        finished.update(r[0] for r in db.execute(f'SELECT seq FROM {table}'))
    source_db = readonly(root/'input.sqlite')
    for record in source_db.execute('SELECT seq,source,line,offset,length,source_id,status,result FROM jobs ORDER BY seq'):
        if record[0] not in finished:
            queues[record[0] % len(queues)].put_nowait(record)
    source_db.close()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=plan['timeout']),
            connector=aiohttp.TCPConnector(force_close=True, limit=plan['own_per_server']*len(queues))) as session:
        limits = []
        for endpoint in manifest['endpoints']:
            async with session.get(endpoint+'/models', timeout=aiohttp.ClientTimeout(total=10)) as response:
                response.raise_for_status()
                limits.append(base.health_limit(await response.json()))
        limit = min(manifest['context_limit'], *limits)

        async def poll():
            while True:
                for i, endpoint in enumerate(manifest['endpoints']):
                    try:
                        async with session.get(endpoint.removesuffix('/v1')+'/metrics', timeout=aiohttp.ClientTimeout(total=5)) as response:
                            response.raise_for_status()
                            values = {}
                            for line in (await response.text()).splitlines():
                                if line and not line.startswith('#'):
                                    name = line.split('{')[0].split()[0]
                                    if name in ('vllm:num_requests_running','vllm:num_requests_waiting','vllm:kv_cache_usage_perc'):
                                        values[name] = values.get(name, 0) + float(line.rsplit(' ', 1)[1])
                            metrics[i] = (time.monotonic(), values)
                    except Exception:
                        metrics[i] = None
                base.write_json(root/'progress.json', dict(time=time.time(), pid=os.getpid(),
                    status='running', active=active, queued=[q.qsize() for q in queues],
                    counts={t: db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ('accepted','rejected','needs_review')}))
                await asyncio.sleep(3)

        async def gate(i):
            while True:
                entry = metrics[i]
                if entry and time.monotonic()-entry[0] < 15:
                    m = entry[1]
                    kv = m.get('vllm:kv_cache_usage_perc', 1)
                    total = m.get('vllm:num_requests_running', 512)+m.get('vllm:num_requests_waiting', 512)
                    if kv < plan['max_kv'] and total+active[i] < plan['shared_cap']-plan['reserve']:
                        active[i] += 1
                        return
                await asyncio.sleep(1)

        async def stage(seq, name, payload, i):
            wire = transport(payload)
            digest = base.digest(wire)
            prior = db.execute('SELECT n,status,hash,record FROM attempts WHERE seq=? AND stage=? ORDER BY n', (seq,name)).fetchall()
            for _, status, old_hash, record in prior:
                if old_hash != digest:
                    raise ValueError('Resume request drift')
                if status == 'complete':
                    return json.loads(record)['result']
            # Tokenize once per stage, never truncate. Preflight failures are not retried.
            budget = await asyncio.to_thread(strong.bulk.engine.measure, tok, payload, limit)
            for n in range(len(prior)+1, plan['max_attempts']+1):
                await gate(i)
                db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?)', (seq,name,n,'inflight',digest,'{}'))
                db.commit()
                out = dict(seq=seq, stage=name, attempt=n, budget=budget, request_sha256=digest)
                try:
                    raw = await base.raw_query(session, manifest['endpoints'][i], wire, writers[i], out)
                    out.update(raw)
                    if raw['finish_reason'] != 'stop':
                        raise ValueError('Incomplete output: '+str(raw['finish_reason']))
                    value = base.strict_json(raw['content'])
                    jsonschema.validate(value, payload['response_format']['json_schema']['schema'])
                    if not value['reason'].strip():
                        raise ValueError('Empty reason')
                    out.update(status='complete', result=value)
                except Exception as exc:
                    out.update(status=base.classify_error(exc), error=repr(exc))
                finally:
                    active[i] -= 1
                db.execute('UPDATE attempts SET status=?,record=? WHERE seq=? AND stage=? AND n=?',
                           (out['status'],json.dumps(out),seq,name,n))
                db.commit()
                if out['status'] == 'complete':
                    return out['result']
                await asyncio.sleep(min(n*2, 6))
            raise ValueError('Technical stage exhausted three attempts: '+name)

        async def worker(i):
            while not queues[i].empty():
                record = queues[i].get_nowait()
                seq, source, line, offset, length, sid, status, result = record
                out = dict(seq=seq, source={k: manifest['sources'][source][k] for k in ('path','sha256')}, source_line=line,
                           source_id=sid, original_audit=json.loads(result) if result else None,
                           no_admission=True)
                table = 'needs_review'
                try:
                    with open(manifest['sources'][source]['path'], 'rb') as stream:
                        stream.seek(offset)
                        row = base.strict_json(stream.read(length).decode())
                    if row['id'] != sid:
                        raise ValueError('Source identity drift')
                    out['original_row_sha256'] = base.digest(row)
                    decision = out['original_audit']['result'] if status == 'complete' else await stage(seq,'retry_audit',strong.request(row),i)
                    out['decision'] = decision
                    if decision['verdict'] == 'repair':
                        repair = await stage(seq,'correction',correction_request(row,decision['reason']),i)
                        out['correction'] = repair
                        if repair['status'] == 'corrected':
                            candidate = corrected(row, repair['content'])
                            out['candidate'] = candidate
                            out['candidate_sha256'] = base.digest(candidate)
                            review = await stage(seq,'fresh_reaudit',strong.request(candidate),i)
                            out['fresh_reaudit'] = review
                            table = destination(review['verdict'])
                    else:
                        table = destination(decision['verdict'])
                except Exception as exc:
                    out['error'] = repr(exc)
                db.execute(f'INSERT INTO {table} VALUES(?,?)', (seq,json.dumps(out,ensure_ascii=False)))
                db.commit()
                queues[i].task_done()

        poller = asyncio.create_task(poll())
        try:
            await asyncio.gather(*(worker(i) for i in range(len(queues)) for _ in range(plan['own_per_server'])))
        finally:
            poller.cancel()
            await asyncio.gather(poller, return_exceptions=True)
    base.write_json(root/'complete.json', dict(time=time.time(), counts={t: db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ('accepted','rejected','needs_review')}))
    db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare','watch'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == 'prepare':
        prepare(root, args.source.resolve())
        return
    with base.lock(root/'controller.lock'):
        plan = verify(root)
        while not snapshot(root, plan):
            base.write_json(root/'progress.json', dict(status='waiting_for_bulk_terminal_and_lock',pid=os.getpid(),time=time.time()))
            time.sleep(30)
        verify(root)
        asyncio.run(run(root, plan))


if __name__ == '__main__':
    main()
