"""Explicitly authorized candidate-only recovery; never admission or full rerun."""
import argparse
import asyncio
from collections import Counter
from copy import deepcopy
import fcntl
import json
from pathlib import Path
import signal
import time

from scripts import dfm13_repochat_qualifier_controls as q

r = q.base.old
b = r.b
ROOT = Path('data/dfm13/repochat-candidate-recovery-20261001-v1')


def prepare(root):
    path = root / 'plan.json'
    if path.exists():
        plan = b.load(path)
        for pin in plan['pins']:
            r.checked_hash(pin)
        return plan
    source = r.ROOT / 'plan.json'
    original = b.load(source)
    for pin in original['pins']:
        r.checked_hash(pin)
    plan = deepcopy(original)
    plan['jobs'] = [j for j in original['jobs'] if j['kind'] in ('finalize', 'audit', 'audit_retry')]
    plan['pins'].extend(r.pin(p) for p in [source, Path(__file__), Path(q.__file__), Path(q.prior.__file__), Path(q.base.__file__), Path(q.prior.previous.__file__)])
    plan.update(authorization='User explicitly orders scoped bulk candidate recovery now despite imperfect controls; no admission.',
                admission=False, calibration_gate_superseded_for_candidate_production_only=True,
                source_plan_sha256=b.file_sha(source))
    root.mkdir(parents=True, exist_ok=True)
    b.save(path, plan)
    return plan


async def review(client, package, out):
    common = dict(model=client.args.model, temperature=0,
                  chat_template_kwargs={'enable_thinking': False})
    payload = dict(common, max_tokens=3072, messages=[
        {'role': 'system', 'content': q.base.CLAIM_SYSTEM + q.prior.previous.ATOMIC_RULES + q.RULES},
        {'role': 'user', 'content': json.dumps(package, ensure_ascii=False)}],
        response_format={'type': 'json_schema', 'json_schema': {'name': 'checks', 'strict': True, 'schema': q.base.CLAIM_SCHEMA}})
    raw = await q.ORIGINAL_REQUEST(client, payload, out / 'claim-checks.json')
    checks = q.prior.previous.checked_document(raw, q.base.CLAIM_SCHEMA)
    if not checks['checks'] or any(not c['claim'].strip() or not c['source_fact'].strip() for c in checks['checks']):
        raise ValueError('empty claim checks')
    payload.update(max_tokens=2048, messages=[
        {'role': 'system', 'content': q.prior.SYSTEM + q.RULES},
        {'role': 'user', 'content': json.dumps(package, ensure_ascii=False)}],
        response_format={'type': 'json_schema', 'json_schema': {'name': 'review', 'strict': True, 'schema': r.full.reviewer.r.SCHEMA}})
    raw = await q.ORIGINAL_REQUEST(client, payload, out / 'verdict.json')
    verdict = q.prior.previous.checked_document(raw, r.full.reviewer.r.SCHEMA)
    passed = r.full.reviewer.r.validate(verdict)
    flags = [c for c in checks['checks'] if c['material'] and c['assessment'] in ('unsupported', 'contradicted')]
    return dict(status='reviewed', quality_pass=passed and not flags, verdict_pass=passed,
                checker_verdict_conflict=bool(passed and flags), checks=checks, review=verdict, admission=False)


async def run(args, plan):
    import aiohttp
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    student = r.full.calibrated.old.Student()
    queue = asyncio.Queue()
    for job in plan['jobs']:
        queue.put_nowait(job)
    active = {}
    finished = asyncio.Event()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=1200), connector=aiohttp.TCPConnector(force_close=True)) as session:
        client = r.Client(session, args, stop)
        async with session.get(args.endpoint + '/models') as response:
            response.raise_for_status()
            if args.model not in [m['id'] for m in (await response.json())['data']]:
                raise ValueError('model mismatch')
        async def worker():
            while not stop.is_set():
                try:
                    job = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                out = args.root / 'jobs' / job['id']
                if (out / 'outcome.json').exists():
                    queue.task_done()
                    continue
                active[job['id']] = 'evidence'
                try:
                    r.checked(job['parent_outcome'])
                    data = r.checked(job['input'])
                    messages = deepcopy(data['messages'])
                    source = r.checked(job['source']) if job['kind'] == 'finalize' else data['source']
                    evidence = await asyncio.to_thread(r.verify_evidence, messages, source)
                    if not evidence['successful_evidence_results']:
                        raise ValueError('no substantive source evidence')
                    if job['kind'] == 'finalize':
                        active[job['id']] = 'finalization'
                        raw = await q.ORIGINAL_REQUEST(client, r.final_payload(messages, args.model), out / 'finalization.json')
                        choice = raw['choices'][0]
                        message = choice['message']
                        if choice['finish_reason'] != 'stop' or not message.get('content') or message.get('tool_calls'):
                            raise ValueError('answer-only finalization incomplete')
                        messages.append({'role': 'assistant', 'content': message['content']})
                    await asyncio.to_thread(b.save, out / 'trajectory.json', dict(messages=messages, tools=r.full.TOOLS, source=source, admission=False))
                    contract = await asyncio.to_thread(r.target_contract, messages, student)
                    await asyncio.to_thread(b.save, out / 'student-contract.json', contract)
                    active[job['id']] = 'review'
                    package = r.full.reviewer.package(messages)
                    result = await review(client, package, out)
                    answer_hash = b.sha(package['final_answer'].encode())
                    result.update(answer_sha256=answer_hash, evidence=evidence, student_eligible=contract['eligible'],
                                  holds=[h for h in plan['preserved_holds'] if h['answer_sha256'] == answer_hash])
                except Exception as exc:
                    result = dict(status='deferred' if stop.is_set() else 'technical_failure',
                                  exception_type=type(exc).__name__, error=str(exc), stage=active[job['id']])
                result.update(id=job['id'], kind=job['kind'], admission=False, parent_outcome=job['parent_outcome'])
                await asyncio.to_thread(b.save, out / ('deferred.json' if stop.is_set() else 'outcome.json'), result)
                print(json.dumps({k:v for k,v in result.items() if k not in ('checks','review')}), flush=True)
                active.pop(job['id'])
                queue.task_done()
        async def report():
            while True:
                rows = [b.load(p) for p in (args.root / 'jobs').glob('*/outcome.json')]
                b.save(args.root / 'progress.json', dict(total=len(plan['jobs']), completed=len(rows), active=dict(active),
                    counts=dict(Counter(x['status'] for x in rows)), admission=False, time=time.time()))
                if finished.is_set():
                    return
                await asyncio.sleep(5)
        reporter = asyncio.create_task(report())
        await asyncio.gather(*(worker() for _ in range(args.concurrency)))
        finished.set()
        await reporter
        b.save(args.root / 'completion.json', dict(remaining=queue.qsize(), drained=stop.is_set(), admission=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--endpoint', default='http://127.0.0.1:8810/v1')
    parser.add_argument('--model', default='dfm13-gemma4')
    parser.add_argument('--concurrency', type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 3:
        parser.error('reserved capacity is at most three cases')
    args.max_kv = .70
    args.root.mkdir(parents=True, exist_ok=True)
    with (args.root / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(run(args, prepare(args.root)))


if __name__ == '__main__':
    main()
