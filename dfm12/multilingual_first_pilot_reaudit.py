"""Review-only migration of the first multilingual pilot; never rewrite targets.

Importer API: verify(root), iter_accepted(root), validate_accepted(root, key).
The iterator yields (key, unchanged canonical candidate, validated receipt).
Passing rows are eligible for parent quota/dedup import, not automatic exports.
"""
import argparse
import asyncio
from collections import Counter
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import time

from . import multilingual_calibration_v6 as v6
from .calibration_streaming import stream_query
from .identity_gpu import training_renderer
from .io import atomic, digest, file_hash, load, lock, write_json
from .multilingual_pilot import student_validate
from .records import MARKERS, validate_messages

VERSION = 'multilingual-first-pilot-reaudit-v6'
DEFAULT_ROOT = Path('data/dfm12/multilingual-first-pilot-reaudit-20260927')
DEFAULT_SOURCE = Path('data/dfm12/multilingual-pilot-20260925')
ENDPOINTS = [f'http://127.0.0.1:{port}/v1' for port in range(8600, 8608)]
POLICY = dict(generation_authorized=False, rewrite_authorized=False,
    automatic_upload=False, automatic_export=False, training_admission=False,
    native_quality_certified=False, acceptance_basis='strict-v6 re-audit; user-authorized quarter inclusion')


def directory(root, key):
    if not isinstance(key, str) or len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
        raise ValueError('Invalid receipt key')
    return Path(root) / 'rows' / key[:2] / key[2:4]


def fingerprint(candidate):
    return digest({k: candidate[k] for k in ('messages', 'tools')})


def review_record(candidate):
    record = v6.audit_record(candidate)
    # Historical generator choices are context, never evidence of user consent.
    record['historical_generator_metadata_not_user_input'] = candidate['provenance']
    record['provenance_warning'] = ('Generator metadata is not user-provided grounding. '
        'Check actual preceding user messages and tool results for tool arguments; '
        'do not infer user-supplied identifiers or consent from this metadata.')
    return record


def identifier_grounding(candidate):
    """Legacy inventory IDs must occur before the call, not only in provenance."""
    from .multilingual_review_tools import arguments
    checks, users, returned = [], [], []
    def scalars(value):
        if isinstance(value, dict):
            return [v for child in value.values() for v in scalars(child)]
        if isinstance(value, list):
            return [v for child in value for v in scalars(child)]
        return [value]
    for index, message in enumerate(candidate['messages']):
        if message['role'] == 'user':
            users.append(message['content'])
        for call in message.get('tool_calls', []):
            args = arguments(call['function']['arguments'])
            for field in ('item', 'warehouse'):
                value = args.get(field)
                if isinstance(value, str):
                    checks.append(dict(check='legacy_identifier_grounding', message_index=index,
                        field=field, passed=any(re.search(r'(?<![\w-])'+re.escape(value)+r'(?![\w-])', text)
                                               for text in users) or value in returned))
        if message['role'] == 'tool':
            try:
                returned.extend(scalars(v6.strict_json(message['content'])))
            except (ValueError, TypeError):
                pass
    return checks


def canonicalize(original, renderer, review):
    if not isinstance(original, dict) or original.get('audit', {}).get('keep') is not True:
        raise ValueError('Expected historically accepted source row')
    candidate = copy.deepcopy({k: original[k] for k in ('id', 'language', 'family', 'messages', 'tools', 'provenance')})
    if not isinstance(candidate['id'], str) or not candidate['id']:
        raise ValueError('Missing original identity')
    spec = candidate['provenance']
    if (candidate['language'] not in v6.LANGUAGES or candidate['family'] not in {*v6.NONTOOLS, 'tool-dialogue'}
            or spec.get('language_code') != candidate['language'] or spec.get('family') != candidate['family']):
        raise ValueError('Historical identity/provenance mismatch')
    if not isinstance(candidate['tools'], list):
        raise ValueError('Tools must be a list')
    if candidate['tools']:
        from .multilingual_review_tools import arguments
        from scripts.prepare_dfm11_tool_replacements import validate_trajectory
        validation_view = copy.deepcopy(candidate)
        messages = validation_view['messages']
        if not isinstance(messages, list) or len(messages) < 2 or messages[0].get('role') != 'user' or messages[-1].get('role') != 'assistant':
            raise ValueError('Invalid native tool conversation boundaries')
        for message in messages:
            content = message.get('content')
            if (message.get('role') not in ('user', 'assistant', 'tool') or not isinstance(content, str)
                    or (not content.strip() and not message.get('tool_calls')) or any(m in content for m in MARKERS)):
                raise ValueError('Invalid native tool message')
            for call in message.get('tool_calls', []):
                # Decode only the validation copy; original training representation is unchanged.
                call['function']['arguments'] = arguments(call['function']['arguments'])
        error = validate_trajectory(validation_view, allow_terminal_calls=False)
        if error:
            raise ValueError(error)
    else:
        validate_messages(candidate['messages'])
    before = fingerprint(candidate)
    student_validate(renderer, candidate)
    if fingerprint(candidate) != before:
        raise ValueError('Student validation changed conversation')
    checks = review.deterministic_checks(review_record(candidate)) + identifier_grounding(candidate)
    candidate.update(admission_authorized=False, native_speaker_review='not_certified')
    return candidate, checks


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.db = sqlite3.connect(self.root / 'reaudit.sqlite')
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, original_id TEXT UNIQUE, language TEXT, family TEXT,
            status TEXT NOT NULL, candidate_sha256 TEXT, fingerprint TEXT,
            source_json TEXT NOT NULL, receipt_json TEXT);
          CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status);
          CREATE TABLE IF NOT EXISTS fingerprints (fingerprint TEXT PRIMARY KEY, owner TEXT);
          CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY,value TEXT);
        ''')

    def claim(self):
        with self.db:
            row = self.db.execute("SELECT * FROM jobs WHERE status='pending' ORDER BY rowid LIMIT 1").fetchone()
            if row:
                self.db.execute("UPDATE jobs SET status='running' WHERE id=? AND status='pending'", (row['id'],))
            return row

    def finish(self, key, receipt):
        with self.db:
            self.db.execute('UPDATE jobs SET status=?,receipt_json=? WHERE id=?',
                (receipt['status'], json.dumps(receipt, ensure_ascii=False), key))

    def recover(self):
        for row in self.db.execute("SELECT * FROM jobs WHERE status='running'").fetchall():
            receipt = base_receipt(row)
            receipt.update(status='abort_status_unknown', error='Interrupted review; no automatic replay', terminal=True)
            # Never trust an unfinished DB transition as proof of admission.
            path = directory(self.root, row['id']) / 'accepted' / f"{row['id']}.json"
            if path.exists():
                receipt['orphan_accepted_candidate'] = str(path)
            save_receipt(self.root, row['id'], receipt)
            self.finish(row['id'], receipt)

    def report(self, phase):
        groups = [dict(row) for row in self.db.execute('SELECT language,family,status,count(*) AS count FROM jobs GROUP BY language,family,status')]
        counts = Counter()
        for group in groups:
            counts[group['status']] += group['count']
        report = dict(version=VERSION, phase=phase, pid=os.getpid(), time=time.time(),
                      total=sum(counts.values()), statuses=dict(counts), groups=groups, **POLICY)
        report['remaining'] = counts['pending'] + counts['running']
        write_json(self.root / 'progress.json', report)
        return report

    def close(self):
        self.db.close()


def base_receipt(row):
    source = json.loads(row['source_json'])
    return dict(version=VERSION, id=row['id'], original_id=row['original_id'], language=row['language'],
        family=row['family'], source=source, candidate_sha256=row['candidate_sha256'],
        fingerprint=row['fingerprint'], eligible_for_quarter_import=False, **POLICY)


def save_receipt(root, key, receipt):
    write_json(directory(root, key) / 'outcomes' / f'{key}.json', receipt)


def inventory_entry(row):
    fields = {k: row[k] for k in ('id', 'original_id', 'language', 'family',
                                 'candidate_sha256', 'fingerprint', 'source_json')}
    return {'id': row['id'], 'sha256': digest(fields)}


def implementation_paths():
    # Explicitly include rendering and structural gates, in addition to review dependencies.
    base = Path(__file__).resolve().parents[1]
    return list(dict.fromkeys([Path(__file__).resolve(), *[p.resolve() for p in v6.implementation_paths()],
        *[base / 'dfm12' / name for name in ('identity_gpu.py', 'prepare.py', 'records.py', 'multilingual_pilot.py')],
        base / 'scripts/tokenize_chat_template.py', base / 'scripts/prepare_dfm11_tool_replacements.py']))


def prepare(root=DEFAULT_ROOT, source=DEFAULT_SOURCE, quarter_root=None, expected=33305):
    if quarter_root is None:
        raise ValueError('Quarter root required for current tokenizer and implementation pins')
    root, source, quarter_root = (Path(p).resolve() for p in (root, source, quarter_root))
    quarter = load(quarter_root / 'manifest.json')
    if quarter.get('version') != 'multilingual-quarter-v6' or file_hash(quarter_root / 'manifest.json') != load(quarter_root / 'seal.json')['manifest_sha256']:
        raise ValueError('Quarter manifest or seal mismatch')
    v6.verify_pins(quarter_root, quarter)
    tokenizer_dir = Path(quarter['tokenizer_dir']).resolve()
    if root.exists():
        raise ValueError('Prepare requires a new root; no historical files are modified')
    files = sorted((source / 'accepted').glob('*.jsonl'))
    if len(files) != 42:
        raise ValueError('Expected all 42 historical exports')
    source_pins = {str(p): file_hash(p) for p in files}
    root.mkdir(parents=True)
    with lock(root / 'reaudit.lock'):
        store = Store(root)
        try:
            write_json(root / 'quarter-context.json', dict(manifest=quarter,
                manifest_sha256=file_hash(quarter_root / 'manifest.json'), source=str(quarter_root)))
            renderer = training_renderer(root)
            review = importlib.import_module(v6.REVIEW_MODULE)
            count = 0
            for path in files:
                with path.open('rb') as handle:
                    for number, raw in enumerate(handle, 1):
                        if not raw.strip():
                            continue
                        original = v6.strict_json(raw.decode('utf-8'))
                        original_id = original.get('id')
                        key = digest(['multilingual-first-pilot-20260925', path.name, number, original_id])
                        source_info = dict(path=str(path), line=number, file_sha256=source_pins[str(path)],
                            line_sha256=hashlib.sha256(raw).hexdigest(), record_sha256=digest(original),
                            historical_audit=original.get('audit'), original_id=original_id)
                        original_path = directory(root, key) / 'original' / f'{key}.json'
                        write_json(original_path, original)
                        source_info['original_snapshot_sha256'] = file_hash(original_path)
                        row = dict(id=key, original_id=original_id, language=original.get('language'), family=original.get('family'),
                                   source_json=json.dumps(source_info, ensure_ascii=False), candidate_sha256=None, fingerprint=None)
                        receipt = base_receipt(row)
                        try:
                            candidate, checks = canonicalize(original, renderer, review)
                            target = directory(root, key) / 'candidates' / f'{key}.json'
                            write_json(target, candidate)
                            row.update(candidate_sha256=file_hash(target), fingerprint=fingerprint(candidate))
                            receipt.update(candidate_sha256=row['candidate_sha256'], fingerprint=row['fingerprint'],
                                student_rendered_tokens=candidate['rendered_training_tokens'], deterministic_checks=checks,
                                deterministic_pass=all(c['passed'] for c in checks))
                            if not receipt['deterministic_pass']:
                                status = 'rejected_cpu'
                            elif store.db.execute('SELECT 1 FROM fingerprints WHERE fingerprint=?', (row['fingerprint'],)).fetchone():
                                status = 'duplicate'
                            else:
                                store.db.execute('INSERT INTO fingerprints VALUES(?,?)', (row['fingerprint'], key))
                                status = 'pending'
                        except (ValueError, TypeError, KeyError) as exc:
                            status = 'invalid_cpu'
                            receipt['error'] = repr(exc)
                        receipt.update(status=status, terminal=status != 'pending')
                        with store.db:
                            store.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',
                                (key, original_id, row['language'], row['family'], status, row['candidate_sha256'],
                                 row['fingerprint'], row['source_json'], json.dumps(receipt, ensure_ascii=False)))
                        save_receipt(root, key, receipt)
                        count += 1
                        if count % 1000 == 0:
                            print(f'CPU prepared {count}/{expected} historical rows', flush=True)
                            store.report('preparing')
            if count != expected:
                raise ValueError(f'Expected {expected} historical rows, found {count}')
            with atomic(root / 'inventory.jsonl') as handle:
                for row in store.db.execute('SELECT * FROM jobs ORDER BY id'):
                    handle.write(json.dumps(inventory_entry(row))+'\n')
            for path, expected_hash in source_pins.items():
                if file_hash(path) != expected_hash:
                    raise ValueError('Historical export changed during preparation')
            student = load(root / 'training-template.json')
            external = dict(source_pins)
            for path in [Path('data/sampled_dfm11/metadata.json').resolve(),
                         Path(student['tokenizer_info']['tokenizer_path']), Path(student['tokenizer_info']['chat_template_path']),
                         *(tokenizer_dir / n for n in ('tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja'))]:
                external[str(path.resolve())] = file_hash(path)
            dependencies = implementation_paths()
            manifest = dict(version=VERSION, source=str(source), target=count, tokenizer_dir=str(tokenizer_dir),
                external_pins=external, implementation_pins={str(p.resolve()): file_hash(p) for p in dependencies},
                input_pins={name: file_hash(root / name) for name in ('training-template.json', 'quarter-context.json', 'inventory.jsonl')}, policy=POLICY)
            write_json(root / 'manifest.json', manifest)
            seal = file_hash(root / 'manifest.json')
            write_json(root / 'seal.json', {'manifest_sha256': seal})
            with store.db:
                store.db.execute('INSERT INTO metadata VALUES(?,?)', ('manifest_sha256', seal))
            store.report('prepared')
        finally:
            store.close()


def verify(root):
    root = Path(root).resolve()
    manifest = load(root / 'manifest.json')
    if manifest.get('version') != VERSION or manifest.get('policy') != POLICY:
        raise ValueError('Reaudit policy drift')
    if file_hash(root / 'manifest.json') != load(root / 'seal.json')['manifest_sha256']:
        raise ValueError('Reaudit seal drift')
    if str(Path(__file__).resolve()) not in manifest['implementation_pins']:
        raise ValueError('Missing reaudit implementation pin')
    if any(str(p) not in manifest['implementation_pins'] for p in implementation_paths()):
        raise ValueError('Missing rendering/review dependency pins')
    v6.verify_pins(root, manifest)
    with sqlite3.connect((root / 'reaudit.sqlite').as_uri()+'?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()
        if not row or row[0] != file_hash(root / 'manifest.json'):
            raise ValueError('Reaudit database seal mismatch')
        if db.execute('SELECT count(*) FROM jobs').fetchone()[0] != manifest['target']:
            raise ValueError('Reaudit inventory changed')
        cursor = iter(db.execute('SELECT * FROM jobs ORDER BY id'))
        with (root / 'inventory.jsonl').open() as handle:
            for line in handle:
                row = next(cursor, None)
                if row is None or inventory_entry(row) != v6.strict_json(line):
                    raise ValueError('Prepared source/candidate inventory drift')
        if next(cursor, None) is not None:
            raise ValueError('Unpinned prepared rows')
    return manifest


async def process(root, row, client, endpoint, limit, review, renderer):
    key = row['id']
    folder = directory(root, key)
    receipt = base_receipt(row)
    try:
        path = folder / 'candidates' / f'{key}.json'
        if file_hash(path) != row['candidate_sha256']:
            raise ValueError('Prepared candidate drift')
        candidate = load(path)
        student_validate(renderer, candidate)
        record = review_record(candidate)
        checks = review.deterministic_checks(record) + identifier_grounding(candidate)
        receipt.update(deterministic_checks=checks, deterministic_pass=all(c['passed'] for c in checks),
                       student_rendered_tokens=candidate['rendered_training_tokens'])
        if not receipt['deterministic_pass']:
            receipt['status'] = 'rejected_cpu'
            return receipt
        payload = v6.review_request(record, review)
        payload.update(temperature=0, frequency_penalty=.5)
        payload, schema = v6.compact_request(payload)
        state = await client.call(key, 'review', payload, schema, endpoint, limit)
        receipt['review_status'] = state['status']
        if state['status'] != 'complete':
            receipt.update(status='review_' + state['status'], error=state.get('error'))
        else:
            result = v6.review_result(state['output'], record, review)
            keep = result['effective_keep'] is True
            receipt.update(result, status='accepted' if keep else 'rejected',
                           review=state['output'], eligible_for_quarter_import=keep)
            receipt['deterministic_checks'] = checks
            for kind, name in [('requests', f'{key}-review.json'), ('stages', f'{key}-review.json')]:
                p = folder / kind / name
                receipt[kind + '_sha256'] = file_hash(p)
            if keep:
                accepted = folder / 'accepted' / f'{key}.json'
                write_json(accepted, candidate)
                receipt['accepted_sha256'] = file_hash(accepted)
    except asyncio.CancelledError:
        receipt.update(status='abort_status_unknown', error='Interrupted review; no automatic replay', eligible_for_quarter_import=False)
        raise
    except Exception as exc:
        receipt.update(status='invalid_review', error=repr(exc), eligible_for_quarter_import=False)
    finally:
        receipt.update(terminal=True, completed=time.time())
        save_receipt(root, key, receipt)
    return receipt


async def execute(root=DEFAULT_ROOT, endpoints=ENDPOINTS, concurrency=32, timeout=600):
    import aiohttp
    root = Path(root).resolve()
    v6.validate_endpoints(endpoints)
    if type(concurrency) is not int or not 1 <= concurrency <= 32 or not 1 <= timeout <= 600:
        raise ValueError('Require <=32 requests/server and <=600s timeout')
    with lock(root / 'reaudit.lock'):
        manifest = verify(root)
        store = Store(root)
        stop, failures = asyncio.Event(), Counter()
        loop, phase = asyncio.get_running_loop(), 'preflight'
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        try:
            store.recover()
            renderer = training_renderer(root)
            review = importlib.import_module(v6.REVIEW_MODULE)
            budget = v6.Budget(manifest['tokenizer_dir'])
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout),
                    connector=aiohttp.TCPConnector(limit=8*concurrency, limit_per_host=concurrency)) as session:
                async def healthcheck(endpoint):
                    async with session.get(endpoint + '/models') as response:
                        response.raise_for_status()
                        document = await response.json()
                        return endpoint, dict(document=document, context=v6.endpoint_limit(document))
                health = dict(await asyncio.gather(*(healthcheck(e) for e in endpoints)))
                write_json(root / f'health-{time.time_ns()}.json', health)
                v6.verify_pins(root, manifest)
                write_json(root / 'runtime.json', dict(pid=os.getpid(), started=time.time(), endpoints=endpoints,
                    concurrency_per_server=concurrency, timeout=timeout, **POLICY))
                phase = 'running'
                async def worker(endpoint):
                    while not stop.is_set() and failures[endpoint] < 3:
                        row = store.claim()
                        if row is None:
                            return
                        folder = directory(root, row['id'])
                        stages = v6.Stages(folder, budget, v6.RawResponseWriter(folder / 'raw'), session, query=stream_query)
                        stages.failures = failures
                        receipt = await process(root, row, stages, endpoint, health[endpoint]['context'], review, renderer)
                        store.finish(row['id'], receipt)
                async def reporter():
                    while True:
                        store.report(phase)
                        await asyncio.sleep(15)
                tasks = [asyncio.create_task(worker(e)) for e in endpoints for _ in range(concurrency)]
                reporting = asyncio.create_task(reporter())
                try:
                    await asyncio.gather(*tasks)
                finally:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    reporting.cancel()
                    await asyncio.gather(reporting, return_exceptions=True)
                phase = 'drained' if stop.is_set() else 'complete' if not store.report(phase)['remaining'] else 'blocked_infrastructure'
        except BaseException:
            phase = 'interrupted_or_failed'
            raise
        finally:
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.remove_signal_handler(sig)
            try:
                store.recover()
                store.report(phase)
            finally:
                store.close()


def validate_accepted(root, key, *, renderer=None, review=None):
    """Call verify(root) once before batch use; independently recheck each keep."""
    import jsonschema
    root = Path(root).resolve()
    folder = directory(root, key)
    with sqlite3.connect((root / 'reaudit.sqlite').as_uri()+'?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT * FROM jobs WHERE id=?', (key,)).fetchone()
        if row is None or row['status'] != 'accepted':
            raise ValueError('Not a terminal accepted re-audit')
    receipt = load(folder / 'outcomes' / f'{key}.json')
    if receipt != json.loads(row['receipt_json']) or receipt.get('terminal') is not True or receipt.get('eligible_for_quarter_import') is not True:
        raise ValueError('Accepted receipt mismatch')
    paths = dict(candidate=folder / 'candidates' / f'{key}.json', accepted=folder / 'accepted' / f'{key}.json',
                 requests=folder / 'requests' / f'{key}-review.json', stages=folder / 'stages' / f'{key}-review.json')
    for kind, path in paths.items():
        if file_hash(path) != receipt[kind + '_sha256']:
            raise ValueError('Accepted evidence drift: ' + kind)
    candidate = load(paths['accepted'])
    if candidate != load(paths['candidate']) or fingerprint(candidate) != row['fingerprint'] or candidate['id'] != row['original_id']:
        raise ValueError('Candidate identity/content mismatch')
    source = json.loads(row['source_json'])
    original_path = folder / 'original' / f'{key}.json'
    if receipt['source'] != source or file_hash(original_path) != source['original_snapshot_sha256']:
        raise ValueError('Original source receipt mismatch')
    original = load(original_path)
    if digest(original) != source['record_sha256'] or any(candidate[k] != original[k] for k in
            ('id', 'language', 'family', 'messages', 'tools', 'provenance')):
        raise ValueError('Reaudit changed original conversation or provenance')
    request, state = load(paths['requests']), load(paths['stages'])
    if state.get('status') != 'complete' or state.get('raw', {}).get('finish_reason') != 'stop':
        raise ValueError('Incomplete re-audit stage')
    if v6.strict_json(state['raw']['content']) != state['output'] or state['request_sha256'] != digest(request['request']):
        raise ValueError('Raw review or request mismatch')
    renderer = renderer or training_renderer(root)
    review = review or importlib.import_module(v6.REVIEW_MODULE)
    student_validate(renderer, candidate)
    record = review_record(candidate)
    if request['schema'] != review.schema(record):
        raise ValueError('Strict review schema mismatch')
    jsonschema.validate(state['output'], request['schema'])
    checks = review.deterministic_checks(record) + identifier_grounding(candidate)
    if not all(c['passed'] for c in checks) or not v6.review_result(state['output'], record, review)['effective_keep']:
        raise ValueError('Re-audit no longer passes CPU gates')
    return candidate, receipt


def iter_accepted(root):
    root = Path(root).resolve()
    verify(root)
    renderer, review = training_renderer(root), importlib.import_module(v6.REVIEW_MODULE)
    with sqlite3.connect((root / 'reaudit.sqlite').as_uri()+'?mode=ro', uri=True) as db:
        for (key,) in db.execute("SELECT id FROM jobs WHERE status='accepted' ORDER BY id"):
            candidate, receipt = validate_accepted(root, key, renderer=renderer, review=review)
            yield key, candidate, receipt


def verify_completed(root):
    manifest = verify(root)
    root = Path(root).resolve()
    counts = Counter()
    with sqlite3.connect((root / 'reaudit.sqlite').as_uri()+'?mode=ro', uri=True) as db:
        for key, status, encoded in db.execute('SELECT id,status,receipt_json FROM jobs'):
            receipt = json.loads(encoded)
            if status in ('pending', 'running') or receipt.get('terminal') is not True or receipt.get('status') != status:
                raise ValueError('Reaudit has nonterminal rows')
            if load(directory(root, key) / 'outcomes' / f'{key}.json') != receipt:
                raise ValueError('Terminal receipt drift')
            counts[status] += 1
    return dict(target=manifest['target'], terminal=sum(counts.values()), statuses=dict(counts), **POLICY)


def iter_verified_keeps(root):
    """Compatibility completion API; same (key, candidate, receipt) tuples."""
    verify_completed(root)
    yield from iter_accepted(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'verify', 'run'])
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--quarter-root', type=Path)
    parser.add_argument('--concurrency-per-server', type=int, default=32)
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    if args.command == 'prepare':
        if args.quarter_root is None:
            parser.error('prepare requires --quarter-root')
        prepare(args.root, args.source, args.quarter_root)
    elif args.command == 'verify':
        print(verify(args.root)['target'])
    else:
        asyncio.run(execute(args.root, concurrency=args.concurrency_per_server, timeout=args.timeout))


if __name__ == '__main__':
    main()
