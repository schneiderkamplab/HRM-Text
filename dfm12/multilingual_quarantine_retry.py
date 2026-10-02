"""Additive, stage-aware infrastructure retries; all results remain quarantined."""
import argparse
import asyncio
import copy
import json
import os
from pathlib import Path
import re
import shutil
import time

import aiohttp
import jsonschema

from . import multilingual_quarantine_pilot as pilot
from .io import digest, file_hash, load, lock, write_json

POLICY = 'quarantine-infrastructure-retry-v1'
STAGES = ('generate', 'primary_audit', 'review')


class CircuitOpen(RuntimeError):
    pass


def infrastructure(error):
    text = repr(error) if isinstance(error, BaseException) else str(error)
    return bool(re.match(r'^(?:ClientConnectorError|ClientOSError|ServerDisconnectedError|'
                         r'ServerTimeoutError|ConnectionTimeoutError|SocketTimeoutError|'
                         r'TimeoutError|ConnectionResetError|ConnectionRefusedError|'
                         r'ClientPayloadError)\(', text)
                or re.match(r"^RuntimeError\(['\"]HTTP (?:429|502|503|504); raw response ", text))


def selection(outcome):
    errors = outcome.get('errors', {})
    stages = []
    if infrastructure(errors.get('generate_or_validate', '')):
        stages.append('generate')
    if 'candidate' in outcome:
        for stage in ('primary_audit', 'review'):
            valid_key = 'primary_audit_valid' if stage == 'primary_audit' else 'review_valid'
            if not outcome.get(valid_key, False) and infrastructure(errors.get(stage, '')):
                stages.append(stage)
    return stages


def immutable(path, value):
    if path.exists():
        raise FileExistsError(path)
    write_json(path, value)


def prepare(source, root, tests):
    import xml.etree.ElementTree as ET
    suites = list(ET.parse(tests).getroot().iter('testsuite'))
    if not suites or any(int(s.get(k, 0)) for s in suites for k in ('failures', 'errors', 'skipped')):
        raise ValueError('Passing unskipped test receipt required')
    source, root = source.resolve(), root.resolve()
    if root.exists() or root.is_relative_to(source) or source.is_relative_to(root):
        raise ValueError('Fresh disjoint retry root required')
    summary = load(source / 'completion.json')
    if not summary.get('completed') or summary.get('recorded_slots') != 700 or summary.get('active_slots'):
        raise ValueError('Require completed 700-slot source')
    manifest = load(source / 'manifest.json')
    for name, sha in manifest['implementation_pins'].items():
        if file_hash(Path(__file__).with_name(name)) != sha:
            raise ValueError('Frozen implementation drift: ' + name)
    for name, sha in manifest['input_pins'].items():
        if file_hash(source / name) != sha:
            raise ValueError('Frozen source input drift: ' + name)
    pins = {str(p.relative_to(source)): file_hash(p) for p in source.rglob('*') if p.is_file()}
    root.mkdir(parents=True)
    shutil.copytree(source, root / 'frozen_source')
    for name in ('outcomes',):
        shutil.copytree(source / name, root / name)
    for name in ('pilot-config.json', 'specifications.json', 'training-template.json',
                 'previous-hashes.json', 'generation-preflight.json', 'calibration-evidence.json'):
        shutil.copy2(source / name, root / name)
    eligible = {p.stem: selection(load(p)) for p in sorted((source / 'outcomes').glob('*.json'))}
    eligible = {key: stages for key, stages in eligible.items() if stages}
    if len(list((source / 'outcomes').glob('*.json'))) != 700:
        raise ValueError('Missing source outcomes')
    implementations = dict(manifest['implementation_pins'])
    for name in ('multilingual_quarantine_retry.py', 'multilingual_retry_servers.py', 'diagnostic_server.py'):
        implementations[name] = file_hash(Path(__file__).with_name(name))
    immutable(root / 'retry-manifest.json', dict(policy=POLICY, source=str(source), source_pins=pins,
        implementation_pins=implementations, selected=eligible, max_attempts_per_stage=3,
        admission_authorized=False, bulk_authorized=False, tests=str(tests.resolve()), tests_sha256=file_hash(tests),
        input_pins={name: file_hash(root / name) for name in ('pilot-config.json', 'specifications.json',
            'training-template.json', 'previous-hashes.json', 'generation-preflight.json', 'calibration-evidence.json')}))
    verify(root)
    write_json(root / 'preflight.json', {'selected_slots': len(eligible), 'source_slots': 700,
        'source_preserved': True, 'stage_counts': {s: sum(s in stages for stages in eligible.values()) for s in STAGES},
        'admission_authorized': False, 'bulk_authorized': False})
    return load(root / 'preflight.json')


def verify(root):
    manifest = load(root / 'retry-manifest.json')
    if manifest['policy'] != POLICY or manifest['admission_authorized'] or manifest['bulk_authorized']:
        raise ValueError('Invalid retry quarantine policy')
    for relative, sha in manifest['source_pins'].items():
        for base in (Path(manifest['source']), root / 'frozen_source'):
            if file_hash(base / relative) != sha:
                raise ValueError('Source/snapshot drift: ' + str(base / relative))
    for name, sha in manifest['implementation_pins'].items():
        if file_hash(Path(__file__).with_name(name)) != sha:
            raise ValueError('Implementation drift: ' + name)
    for name, sha in manifest['input_pins'].items():
        if file_hash(root / name) != sha:
            raise ValueError('Retry input drift: ' + name)
    for path in (root / 'outcomes').glob('*.json'):
        if path.stem not in manifest['selected']:
            if file_hash(path) != manifest['source_pins']['outcomes/' + path.name]:
                raise ValueError('Nonselected outcome changed: ' + path.name)
        elif (root / 'finished' / path.name).exists():
            if digest(load(path)) != load(root / 'finished' / path.name)['outcome_sha256']:
                raise ValueError('Completed retry outcome changed: ' + path.name)
    if file_hash(manifest['tests']) != manifest['tests_sha256']:
        raise ValueError('Test receipt drift')
    return manifest


class EndpointPool:
    """One request per endpoint, rotating leases and shared failure cooldown."""
    def __init__(self, session, endpoints, cooldown=60, unavailable_timeout=45):
        self.session, self.endpoints = session, endpoints
        self.cooldown, self.unavailable_timeout = cooldown, unavailable_timeout
        self.busy, self.until, self.cursor = set(), {}, 0

    async def health(self, endpoint):
        try:
            async with self.session.get(endpoint + '/models', timeout=aiohttp.ClientTimeout(total=4)) as response:
                response.raise_for_status()
                pilot.validate_endpoint_models(await response.json())
            return True
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return False

    async def acquire(self):
        unavailable_since = None
        while True:
            now = time.monotonic()
            for offset in range(len(self.endpoints)):
                i = (self.cursor + offset) % len(self.endpoints)
                endpoint = self.endpoints[i]
                if endpoint in self.busy or self.until.get(endpoint, 0) > now:
                    continue
                self.busy.add(endpoint)
                self.cursor = (i + 1) % len(self.endpoints)
                if await self.health(endpoint):
                    return endpoint
                self.release(endpoint, failed=True)
            if not self.busy:
                unavailable_since = unavailable_since or time.monotonic()
                if time.monotonic() - unavailable_since >= self.unavailable_timeout:
                    raise CircuitOpen('No healthy authorized endpoint; stop dispatch, preserve pending slots')
            else:
                unavailable_since = None
            await asyncio.sleep(.5)

    def release(self, endpoint, failed=False):
        self.busy.discard(endpoint)
        if failed:
            self.until[endpoint] = time.monotonic() + self.cooldown


async def stage_call(root, key, stage, payload, pool, query):
    directory = root / 'stages' / key / stage
    for number in range(1, 4):
        started = directory / f'{number}.started.json'
        finished = directory / f'{number}.result.json'
        if finished.exists():
            receipt = load(finished)
            if receipt['payload_sha256'] != digest(payload):
                raise ValueError('Stage payload drift')
            if receipt['status'] == 'success':
                return receipt['output']
            if not receipt['infrastructure']:
                raise ValueError('Prior non-infrastructure failure: ' + receipt['error'])
            continue
        if started.exists():
            raise ValueError('Indeterminate interrupted request; do not regenerate without transport evidence')
        endpoint = await pool.acquire()
        try:
            immutable(started, dict(endpoint=endpoint, payload_sha256=digest(payload), time=time.time()))
        except BaseException:
            pool.release(endpoint)
            raise
        failed = False
        try:
            output = await query(endpoint, payload, stage, key, number)
            immutable(finished, dict(status='success', output=output, payload_sha256=digest(payload)))
            return output
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            failed = infrastructure(exc)
            immutable(finished, dict(status='failed', error=repr(exc), infrastructure=failed,
                                     payload_sha256=digest(payload)))
            if not failed:
                raise
        finally:
            pool.release(endpoint, failed=failed)
    raise RuntimeError('Infrastructure attempt budget exhausted (3); no automatic retry reset')


async def retry_slot(root, key, selected, renderer, call, seen):
    result = copy.deepcopy(load(root / 'frozen_source' / 'outcomes' / f'{key}.json'))
    original = copy.deepcopy(result)
    result['retry'] = {'policy': POLICY, 'selected_stages': selected, 'original_sha256': digest(original)}
    result.update(admission='quarantined', admission_authorized=False)
    path = root / 'outcomes' / f'{key}.json'
    def save():
        write_json(path, result)
    new_candidate = 'generate' in selected and 'candidate' not in result
    if new_candidate:
        try:
            if 'generator_output' not in result:
                result['generator_output'] = await call(pilot.request(result['spec']), 'generate', key)
                save()
            candidate = pilot.assemble(result['spec'], result['generator_output'])
            result['candidate'] = await asyncio.to_thread(pilot.student_validate, renderer, candidate)
            result['errors'].pop('generate_or_validate', None)
            fingerprint = digest({k: result['candidate'][k] for k in ('messages', 'tools')})
            result['duplicate'] = fingerprint in seen
            seen.add(fingerprint)
            save()
        except CircuitOpen:
            raise
        except Exception as exc:
            result['status'] = 'invalid_generation'
            result['errors']['generate_or_validate'] = repr(exc)
            save()
            return result
    if 'candidate' not in result:
        return result
    record = pilot.audit_record(result['candidate'])
    for stage in ('primary_audit', 'review'):
        if not new_candidate and stage not in selected:
            continue
        try:
            if stage == 'primary_audit':
                payload = dict(model=pilot.MODEL, temperature=0, max_tokens=512,
                    chat_template_kwargs={'enable_thinking': False}, response_format=pilot.audit_schema(),
                    messages=[{'role': 'system', 'content': pilot.AUDIT},
                              {'role': 'user', 'content': json.dumps(record, ensure_ascii=False)}])
                result[stage] = await call(payload, stage, key)
                pilot.validate_audit(result[stage])
                result['primary_audit_valid'] = True
            else:
                result[stage] = await call(pilot.review_request(record), stage, key)
                result['reviewer_keep'] = pilot.keeps(result[stage], record)
                result['review_valid'] = True
            result['errors'].pop(stage, None)
        except CircuitOpen:
            raise
        except Exception as exc:
            result['errors'][stage] = repr(exc)
            result['primary_audit_valid' if stage == 'primary_audit' else 'review_valid'] = False
        save()
    both = result.get('primary_audit_valid', False) and result.get('review_valid', False)
    result['would_keep_by_both_audits'] = bool(both and result['primary_audit']['keep']
        and result.get('reviewer_keep') and not result.get('duplicate'))
    result['status'] = 'quarantined_reviewed' if both else 'quarantined_audit_invalid'
    save()
    return result


async def run(root, endpoints):
    manifest = verify(root)
    renderer, budget = pilot.training_renderer(root), pilot.PromptBudget()
    writer = pilot.RawResponseWriter(root / 'raw')
    seen = set(load(root / 'previous-hashes.json'))
    for path in (root / 'outcomes').glob('*.json'):
        o = load(path)
        if 'candidate' in o and (path.stem not in manifest['selected'] or (root / 'finished' / path.name).exists()):
            seen.add(digest({k: o['candidate'][k] for k in ('messages', 'tools')}))
    pending = iter(key for key in manifest['selected'] if not (root / 'finished' / f'{key}.json').exists())
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),
            connector=aiohttp.TCPConnector(limit=8)) as session:
        pool = EndpointPool(session, endpoints)
        async def query(endpoint, payload, stage, key, number):
            count = budget.measure(payload)
            transport, schema = pilot.compact_request(payload)
            output = await pilot.captured_query(session, endpoint, transport, writer,
                dict(case_id=key, stage=stage, attempt=number, prompt_tokens=count, diagnostic_only=True))
            immutable(root / 'decoded' / f'{key}-{stage}-{number}.json', output)
            if schema is not None:
                jsonschema.validate(output, schema)
            return output
        async def call(payload, stage, key):
            return await stage_call(root, key, stage, payload, pool, query)
        async def worker():
            for key in pending:
                outcome = await retry_slot(root, key, manifest['selected'][key], renderer, call, seen)
                immutable(root / 'finished' / f'{key}.json', dict(outcome_sha256=digest(outcome)))
                pilot.summarize(root)
                write_json(root / 'retry-progress.json', {'selected': len(manifest['selected']),
                    'finished': len(list((root / 'finished').glob('*.json'))), 'admission_authorized': False})
        tasks = [asyncio.create_task(worker()) for _ in range(8)]
        try:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=6 * 3600)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    verify(root)
    pilot.summarize(root, complete=True)
    write_json(root / 'retry-status.json', {'phase': 'completed_quarantined', 'admission_authorized': False})


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('action', choices=('prepare', 'run'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--tests', type=Path)
    parser.add_argument('--endpoints', nargs='+')
    args = parser.parse_args()
    if args.action == 'prepare':
        print(prepare(args.source, args.root, args.tests))
    else:
        if not args.endpoints or len(set(args.endpoints)) != 8 or len(args.endpoints) != 8:
            parser.error('Eight dedicated endpoints required')
        with lock(args.root / '.retry.lock'):
            if (args.root / 'completion.json').exists():
                raise ValueError('Completed retry immutable; no rerun')
            write_json(args.root / 'retry-status.json', {'phase': 'running', 'pid': os.getpid()})
            try:
                asyncio.run(run(args.root, args.endpoints))
            except BaseException as exc:
                write_json(args.root / 'retry-status.json', {'phase': 'interrupted', 'error': repr(exc)})
                raise


if __name__ == '__main__':
    main()
