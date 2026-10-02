"""Single-writer resumable 35K generation/audit pilot on shared model endpoints."""
import asyncio
import json
import random
from pathlib import Path
import signal
import sqlite3
import time

from .identity_gpu import training_renderer
from .io import atomic, digest, load, lock, write_json
from .jobs import response_json, validate_audit
from .multilingual_seeds import LANGUAGES
from .multilingual_tasks import AUDIT, MODEL, QUOTAS, assemble, audit_schema, request, spec_for
from .multilingual_review import calibration_cases, review_keeps, review_request


class Store:
    def __init__(self, root):
        self.root = root
        self.config = load(root / 'pilot-config.json') if (root / 'pilot-config.json').exists() else {}
        self.quotas = self.config.get('quotas', QUOTAS)
        self.db = sqlite3.connect(root / 'pilot.sqlite')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS slots (
          language TEXT, family TEXT, slot INTEGER, attempts INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'pending', candidate TEXT, audit TEXT, error TEXT,
          PRIMARY KEY(language,family,slot));
        CREATE TABLE IF NOT EXISTS events (
          time REAL, language TEXT, family TEXT, slot INTEGER, attempt INTEGER,
          state TEXT, detail TEXT);
        CREATE TABLE IF NOT EXISTS accepted_hashes(hash TEXT PRIMARY KEY, identity TEXT);
        CREATE TABLE IF NOT EXISTS configuration (key TEXT PRIMARY KEY, value TEXT);
        ''')
        signature = digest(self.config)
        previous = self.db.execute("SELECT value FROM configuration WHERE key='config_hash'").fetchone()
        if previous and previous[0] != signature:
            self.db.close()
            raise ValueError('Pilot configuration changed; use a new cohort directory')
        self.db.execute("INSERT OR IGNORE INTO configuration VALUES('config_hash',?)", (signature,))
        if self.config and not previous:
            for fingerprint in load(root / 'previous-hashes.json'):
                self.db.execute('INSERT OR IGNORE INTO accepted_hashes VALUES (?,?)',
                                (fingerprint, 'previous-pilot'))
        for slot in range(max(self.quotas.values())):
            for language in LANGUAGES:
                for family, count in self.quotas.items():
                    if slot < count:
                        self.db.execute('INSERT OR IGNORE INTO slots(language,family,slot) VALUES(?,?,?)',
                                        (language,family,slot))
        self.db.commit()

    def pending(self):
        return list(self.db.execute("SELECT language,family,slot,attempts,candidate FROM slots WHERE status='pending' ORDER BY rowid"))

    def save(self, key, **fields):
        assignments = ','.join(k + '=?' for k in fields)
        self.db.execute('UPDATE slots SET ' + assignments + ' WHERE language=? AND family=? AND slot=?',
                        (*fields.values(), *key))
        self.db.commit()

    def event(self, key, attempt, state, detail):
        self.db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?)',
                        (time.time(), *key, attempt, state, json.dumps(detail, ensure_ascii=False)))
        self.db.commit()

    def counts(self):
        return [dict(language=l,family=f,status=s,count=n) for l,f,s,n in self.db.execute(
            'SELECT language,family,status,count(*) FROM slots GROUP BY 1,2,3')]

    def export(self):
        review_rows = []
        for language in LANGUAGES:
            for family in self.quotas:
                reservoir = []
                rng = random.Random(f'pilot-review/{language}/{family}')
                seen = 0
                path = self.root / 'accepted' / f'{family}-{language}.jsonl'
                with atomic(path) as handle:
                    for candidate, audit in self.db.execute(
                        "SELECT candidate,audit FROM slots WHERE language=? AND family=? AND status='accepted' ORDER BY slot",
                        (language,family)):
                        row = json.loads(candidate)
                        row['audit'] = json.loads(audit)
                        handle.write(json.dumps(row, ensure_ascii=False) + '\n')
                        seen += 1
                        if len(reservoir) < 17:
                            reservoir.append(row)
                        else:
                            index = rng.randrange(seen)
                            if index < 17:
                                reservoir[index] = row
                review_rows.extend(reservoir)
        with atomic(self.root / 'native-review-sample.jsonl') as handle:
            for row in review_rows:
                handle.write(json.dumps(row, ensure_ascii=False) + '\n')
        write_json(self.root / 'quality-summary.json', {
            'counts': self.counts(), 'review_sample_rows': len(review_rows),
            'accepted_rendered_tokens': self.db.execute(
                "SELECT sum(json_extract(candidate,'$.rendered_training_tokens')) FROM slots WHERE status='accepted'").fetchone()[0],
            'event_counts': dict(self.db.execute('SELECT state,count(*) FROM events GROUP BY state')),
            'native_review': 'pending', 'bulk_approved': False})
        if self.config.get('calibration_policy'):
            from .multilingual_trial import outcomes
            outcomes(self)

    def repair_contract_v1(self):
        """One explicit migration; keep accepted data and every old failure event."""
        if self.db.execute('PRAGMA user_version').fetchone()[0] >= 2:
            return 0
        fixable = ("ValueError('Invalid audit decision schema')", "ValueError('Invalid tool dialogue text')",
                   "ValueError('Student encoding failed')", "ValueError('Wrong turn count')",
                   "ValueError('missing_conversation')", "KeyError('assistant')", "KeyError('explanation')")
        keys = self.db.execute("SELECT DISTINCT s.language,s.family,s.slot,s.attempts FROM slots s JOIN events e "
            "ON s.language=e.language AND s.family=e.family AND s.slot=e.slot "
            "WHERE s.status IN ('pending','exhausted') AND s.attempts>0 AND json_extract(e.detail,'$.error') IN ("
            + ','.join('?' for _ in fixable) + ')',fixable).fetchall()
        for language,family,slot,attempts in keys:
            self.event((language,family,slot),attempts,'contract_v2_retry',{'old_attempts':attempts})
            self.save((language,family,slot),status='pending',attempts=0,candidate=None,error=None)
        self.db.execute('PRAGMA user_version=2')
        self.db.commit()
        return len(keys)


def student_validate(renderer, row):
    from scripts.tokenize_chat_template import examples_from_messages, render, tokenize_example
    count = 0
    for example in examples_from_messages(row['messages'], row['tools']):
        full = render(renderer.template, example.prompt_messages + [example.assistant_message],
                      example.tools, False, False)
        if len(renderer.tokenizer.encode(full, add_special_tokens=False).ids) > 4096:
            raise ValueError('Full untrimmed student target exceeds 4096 tokens')
        encoded = tokenize_example(renderer.tokenizer, renderer.template, example, False)
        if encoded is None or sum(map(len, encoded)) > 4096:
            raise ValueError('Student encoding failed')
        count += sum(map(len, encoded))
    if not count:
        raise ValueError('No student targets')
    row['rendered_training_tokens'] = count
    return row


async def execute(root, endpoints, concurrency=64):
    import aiohttp
    if (root / 'calibration').exists() or (root / 'cpu-preflight-passed.json').exists():
        from .multilingual_trial import verify_inputs
        verify_inputs(root)
    if (root / 'pilot-config.json').exists() and load(root / 'pilot-config.json').get('calibration_measurement_only'):
        raise ValueError('Calibration measurement-only root cannot generate pilot rows')
    store = Store(root)
    from .multilingual_diagnose import configured_review_request, configured_review_keeps
    review_payload = lambda record: configured_review_request(record, store.config)
    raw_writer = prompt_budget = None
    if store.config.get('review_options') is not None and not store.config.get('raw_response_logging'):
        raise ValueError('Diagnostic review options require measured-budget raw-response logging')
    if store.config.get('raw_response_logging'):
        if store.config.get('diagnostic_followup') is not True:
            raise ValueError('Raw-response opt-in requires a new diagnostic-followup root')
        from .multilingual_diagnose import RawResponseWriter, PromptBudget
        raw_writer, prompt_budget = RawResponseWriter(root / 'raw-responses'), PromptBudget()
    renderer = training_renderer(root)
    seeds = {lang:load(root / f'seeds-{lang}.json') for lang in LANGUAGES}
    seeds['openhermes'] = load(root / 'seeds-openhermes.json')
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    work = asyncio.Queue()
    for row in store.pending():
        work.put_nowait(row)
    active = {}
    start = time.time()
    async def query(session, endpoint, payload):
        for retry in range(4):
            try:
                if raw_writer is not None:
                    from .multilingual_diagnose import captured_query
                    count = prompt_budget.measure(payload)
                    return await captured_query(session, endpoint, payload, raw_writer,
                                                {'retry': retry, 'prompt_tokens': count})
                async with session.post(endpoint + '/chat/completions', json=payload) as response:
                    if response.status != 200:
                        raise RuntimeError(f'HTTP {response.status}: {(await response.text())[:500]}')
                    body = await response.json()
                choice = body['choices'][0]
                if choice['finish_reason'] != 'stop':
                    raise ValueError('Incomplete output: ' + str(choice['finish_reason']))
                return response_json(choice['message']['content'])
            except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError):
                if retry == 3:
                    raise
                await asyncio.sleep(2 ** retry)

    async def worker(session, endpoint, worker_id):
        while not stop.is_set():
            try:
                language,family,slot,attempts,cached = work.get_nowait()
            except asyncio.QueueEmpty:
                return
            key = (language,family,slot)
            active[worker_id] = {'language':language,'family':family,'slot':slot,'stage':'generate'}
            try:
                candidate = json.loads(cached) if cached else None
                for attempt in range(attempts, 6):
                    if stop.is_set():
                        break
                    result = None
                    try:
                        spec = spec_for(language,family,slot,attempt,seeds,store.config)
                        if candidate is None:
                            active[worker_id]['stage'] = 'generate'
                            result = await query(session, endpoint, request(spec))
                            candidate = await asyncio.to_thread(lambda: student_validate(renderer, assemble(spec,result)))
                            store.save(key, candidate=json.dumps(candidate,ensure_ascii=False), attempts=attempt)
                        spec = candidate['provenance']
                        active[worker_id]['stage'] = 'audit'
                        audit_record = {k:candidate[k] for k in ('language','family','messages','tools')}
                        audit_record['language_name'] = LANGUAGES[language]
                        audit_record['requested_subtype'] = spec['subtype']
                        if family == 'openhermes':
                            audit_record['source_messages'] = spec['source']['messages']
                        if 'reference' in spec:
                            audit_record['reference'] = spec['reference']
                        if 'scenario' in spec:
                            audit_record['scenario'] = spec['scenario']
                        audit = await query(session, endpoint, {'model':MODEL,'temperature':0,'max_tokens':512,
                            'chat_template_kwargs':{'enable_thinking':False},'response_format':audit_schema(),
                            'messages':[{'role':'system','content':AUDIT},
                                        {'role':'user','content':json.dumps(audit_record,ensure_ascii=False)}]})
                        validate_audit(audit)
                        if audit['keep'] and store.config.get('second_review'):
                            active[worker_id]['stage'] = 'language_meaning_review'
                            # A separate prompt/context/replica, not an independent model.
                            review_endpoint = endpoints[(endpoints.index(endpoint) + 1) % len(endpoints)]
                            review = await query(session, review_endpoint, review_payload(audit_record))
                            audit['second_review'] = review
                            if not configured_review_keeps(review, audit_record, store.config):
                                audit['keep'] = False
                                audit['reason'] = 'Separate language/meaning review rejected: ' + '; '.join(review['issues'])
                        fingerprint = digest({'messages':candidate['messages'],'tools':candidate['tools']})
                        duplicate = store.db.execute('SELECT 1 FROM accepted_hashes WHERE hash=?',(fingerprint,)).fetchone()
                        if audit['keep'] and not duplicate:
                            store.db.execute('INSERT INTO accepted_hashes VALUES (?,?)',(fingerprint,json.dumps(key)))
                            store.save(key,status='accepted',audit=json.dumps(audit),attempts=attempt+1,error=None)
                            store.event(key,attempt,'accepted',{'audit':audit,'id':candidate['id']})
                            break
                        store.event(key,attempt,'rejected',{'audit':audit,'duplicate':bool(duplicate),'candidate':candidate})
                    except Exception as exc:
                        store.event(key,attempt,'failed_attempt',{'error':repr(exc),'candidate':candidate,
                                                                 'generator_output':result})
                    candidate = None
                    store.save(key,candidate=None,attempts=attempt+1)
                else:
                    store.save(key,status='exhausted',error='Six bounded candidate attempts exhausted')
            finally:
                active.pop(worker_id,None)
                work.task_done()
    async def monitor():
        while True:
            report = {'time':time.time(),'elapsed_seconds':time.time()-start,'counts':store.counts(),
                      'active':list(active.values()),'queued_slots':work.qsize(),'concurrency_per_endpoint':concurrency}
            write_json(root/'runtime.json',report)
            print(json.dumps({k:v for k,v in report.items() if k != 'active'}),flush=True)
            await asyncio.sleep(30)
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),
            connector=aiohttp.TCPConnector(limit=len(endpoints)*concurrency)) as session:
            if store.config.get('calibration_policy'):
                from .multilingual_trial import gate
                try:
                    await gate(root, session, endpoints, query)
                except Exception:
                    store.export()
                    raise
            elif store.config.get('second_review'):
                checks = []
                for i, case in enumerate(calibration_cases()):
                    review = await query(session, endpoints[i % len(endpoints)], review_payload(case['record']))
                    checks.append(dict(name=case['name'], expected_keep=case['expected_keep'],
                                       actual_keep=review_keeps(review), review=review))
                write_json(root / 'review-calibration.json', {'checks': checks})
                if any(c['expected_keep'] != c['actual_keep'] for c in checks):
                    raise RuntimeError('Language review calibration failed; do not launch generation')
            monitoring = asyncio.create_task(monitor())
            try:
                await asyncio.gather(*(worker(session,e,f'{i}/{j}') for i,e in enumerate(endpoints) for j in range(concurrency)))
            finally:
                monitoring.cancel()
                await asyncio.gather(monitoring,return_exceptions=True)
        store.export()
        write_json(root/'completion.json',{'time':time.time(),'counts':store.counts(),
            'interrupted':stop.is_set(),'bulk_approved':False,'native_review':'pending'})
    finally:
        store.db.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--endpoints',nargs='+',required=True)
    parser.add_argument('--concurrency',type=int,default=64)
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 128:
        parser.error('Concurrency must be 1..128')
    with lock(args.root / '.pilot.lock'):
        previous = args.root/'completion.json'
        if previous.exists():
            previous.rename(args.root/f'completion.before-resume-{time.time_ns()}.json')
        asyncio.run(execute(args.root,args.endpoints,args.concurrency))


if __name__ == '__main__':
    main()
