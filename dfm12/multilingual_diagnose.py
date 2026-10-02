"""Bounded same-model reviewer diagnostics; never starts servers or admits data."""
import argparse
import asyncio
import base64
from collections import Counter
from collections.abc import Mapping
import copy
import hashlib
import json
import itertools
import os
from pathlib import Path
import time
import uuid

from .audit_pilot_gpu import TOKENIZER_DIR
from .io import file_hash, load, lock, write_json
from .jobs import response_json
from .multilingual_calibration import calibration_cases
from .multilingual_review import review_keeps, review_request
from .multilingual_tasks import MODEL

AB_VARIANTS = ('schema1024', 'schema4096', 'bounded4096', 'plain4096')
VARIANTS = (*AB_VARIANTS, 'grammar4096', 'evidence4096', 'evidence_plain4096', 'structured4096', 'tools4096', 'routed4096')
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def text_characteristics(text):
    if not isinstance(text, str):
        return None
    words = text.split()
    counts = Counter(words)
    return dict(characters=len(text), whitespace_characters=sum(c.isspace() for c in text),
        whitespace_fraction=sum(c.isspace() for c in text) / max(1, len(text)),
        whitespace_separated_tokens=len(words), unique_whitespace_separated_tokens=len(counts),
        most_common_token_count=max(counts.values(), default=0),
        longest_identical_character_run=max((sum(1 for _ in group) for _, group in itertools.groupby(text)), default=0),
        prefix=text[:200], suffix=text[-200:])


def selected_cases():
    cases = calibration_cases()
    selected = [c for c in cases if c['split'] == 'regression']
    for language, group, keep in (('nb', 'arithmetic', True), ('nn', 'source_number', True),
                                  ('nl', 'code_constant', True), ('pl', 'source_injection', False)):
        selected.append(next(c for c in cases if c['split'] == 'development'
                             and c['record']['language'] == language and c['group'] == group
                             and c['expected_keep'] == keep))
    if len(selected) != 8 or sum(c['expected_keep'] for c in selected) != 4:
        raise ValueError('Diagnostic selection must remain eight balanced non-heldout controls')
    return selected


def diagnostic_request(record, variant):
    if variant not in VARIANTS:
        raise ValueError('Unknown diagnostic review variant')
    if variant == 'routed4096':
        from .multilingual_review_routed import request
        return request(record)
    if variant == 'tools4096':
        from .multilingual_review_tools import request
        return request(record)
    if variant == 'structured4096':
        from .multilingual_review_structured import request
        return request(record)
    if variant in ('evidence4096', 'evidence_plain4096'):
        from .multilingual_review_evidence import request
        payload = request(record)
        if variant == 'evidence_plain4096':
            del payload['structured_outputs']
        return payload
    payload = copy.deepcopy(review_request(record))
    payload['max_tokens'] = 1024 if variant == 'schema1024' else 4096
    if variant in ('bounded4096', 'plain4096'):
        payload['messages'][0]['content'] += (
            '\nReturn only one compact JSON object, no markdown or reasoning preamble. '
            'Keep the same three independent boolean judgments. issues must contain at most '
            '4 strings, each at most 240 characters; back_translation must be 1..800 characters '
            'and quote the decisive literal candidate span. Never omit a quality failure to fit '
            'these limits. Do not repair the candidate or lower any acceptance standard. '
            'Required JSON keys: language_correct, meaning_correct, constraints_met '
            '(booleans), issues (array of strings), back_translation (nonempty string).')
        properties = payload['response_format']['json_schema']['schema']['properties']
        properties['issues'].update(maxItems=4, items={'type': 'string', 'maxLength': 240})
        properties['back_translation']['maxLength'] = 800
    if variant == 'plain4096':
        del payload['response_format']
    if variant == 'grammar4096':
        import xgrammar
        schema = payload.pop('response_format')['json_schema']['schema']
        # Explicit grammar bypasses this vLLM version's server-global JSON
        # whitespace setting. String content and semantic schema stay unchanged.
        grammar = xgrammar.Grammar.from_json_schema(schema, any_whitespace=False,
                                                    indent=None, separators=(',', ':'))
        payload['structured_outputs'] = {'grammar': str(grammar)}
    return payload


def configured_review_request(record, config):
    config = config or {}
    options = config.get('review_options')
    if options is None:
        return review_request(record)
    if config.get('diagnostic_followup') is not True or set(options) != {'variant'}:
        raise ValueError('Review options require an explicit new diagnostic-followup root')
    return diagnostic_request(record, options['variant'])


def configured_review_keeps(review, record, config):
    if (config or {}).get('review_options', {}).get('variant') == 'routed4096':
        from .multilingual_review_routed import keeps
        return keeps(review, record)
    if (config or {}).get('review_options', {}).get('variant') == 'tools4096':
        from .multilingual_review_tools import keeps
        return keeps(review, record)
    if (config or {}).get('review_options', {}).get('variant') == 'structured4096':
        from .multilingual_review_structured import keeps
        return keeps(review, record)
    if (config or {}).get('review_options', {}).get('variant') in ('evidence4096', 'evidence_plain4096'):
        from .multilingual_review_evidence import keeps
        return keeps(review, record)
    return review_keeps(review)


class PromptBudget:
    def __init__(self, tokenizer_dir=TOKENIZER_DIR):
        from transformers import AutoTokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_dir), local_files_only=True)

    def measure(self, payload):
        if payload['model'] != MODEL or payload.get('chat_template_kwargs') != {'enable_thinking': False}:
            raise ValueError('Only 26B-A4B with thinking disabled is authorized')
        ids = self.tokenizer.apply_chat_template(payload['messages'], tokenize=True,
            add_generation_prompt=True, enable_thinking=False)
        if isinstance(ids, Mapping):
            ids = ids['input_ids']
        if not isinstance(ids, list) or not all(type(i) is int for i in ids):
            raise ValueError('Unexpected tokenizer output')
        count = len(ids)
        if count + payload['max_tokens'] > 8192:
            raise ValueError('Measured prompt plus completion exceeds 8192 tokens')
        return count


class RawResponseWriter:
    """Single event-loop writer; immutable request IDs and bounded full raw bodies."""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.run_id = uuid.uuid4().hex
        self.sequence = 0

    def begin(self, endpoint, payload, metadata=None):
        self.sequence += 1
        request_id = f'{self.run_id}-{self.sequence:06d}'
        write_json(self.root / f'{request_id}.request.json', dict(request_id=request_id,
            endpoint=endpoint, request=payload, metadata=metadata or {}, time=time.time()))
        return request_id

    def finish(self, request_id, **fields):
        path = self.root / f'{request_id}.response.json'
        if path.exists():
            raise RuntimeError('Duplicate raw-response ID')
        write_json(path, dict(request_id=request_id, time=time.time(), **fields))


async def captured_query(session, endpoint, payload, writer, metadata=None):
    """Persist status/body before JSON parsing, including non-200 and length outputs."""
    request_id = writer.begin(endpoint, payload, metadata)
    status, body, truncated, headers = None, bytearray(), False, {}
    try:
        async with session.post(endpoint.rstrip('/') + '/chat/completions', json=payload) as response:
            status = response.status
            headers = {key: value for key, value in getattr(response, 'headers', {}).items()
                       if key.lower() in ('content-type', 'x-request-id')}
            async for chunk in response.content.iter_chunked(65536):
                available = MAX_RESPONSE_BYTES - len(body)
                body.extend(chunk[:available])
                if len(chunk) > available:
                    truncated = True
                    break
    except (Exception, asyncio.CancelledError) as exc:
        writer.finish(request_id, status=status, raw_body_base64=base64.b64encode(body).decode(),
                      raw_body_utf8=body.decode('utf-8', errors='replace'), bytes_saved=len(body),
                      truncated=truncated, headers=headers, transport_error=repr(exc))
        raise
    writer.finish(request_id, status=status, raw_body_base64=base64.b64encode(body).decode(),
                  raw_body_utf8=body.decode('utf-8', errors='replace'), bytes_saved=len(body),
                  sha256=hashlib.sha256(body).hexdigest(), truncated=truncated, headers=headers)
    # Raw usage, finish reasons, IDs, and content are durable before either parse.
    if truncated:
        raise ValueError('HTTP response exceeded bounded raw capture limit')
    if status != 200:
        raise RuntimeError(f'HTTP {status}; raw response {request_id}')
    decoded = json.loads(body)
    choice = decoded['choices'][0]
    write_json(writer.root / f'{request_id}.metadata.json', dict(request_id=request_id,
        response_id=decoded.get('id'), usage=decoded.get('usage'), finish_reason=choice.get('finish_reason'),
        content_characteristics=text_characteristics(choice.get('message', {}).get('content')),
        reasoning_characteristics=text_characteristics(choice.get('message', {}).get('reasoning_content'))))
    if choice.get('finish_reason') != 'stop':
        raise ValueError('Incomplete output: ' + str(choice.get('finish_reason')))
    return response_json(choice['message']['content'])


def assess(case, review, variant=None):
    keep = configured_review_keeps(review, case['record'], {'review_options': {'variant': variant}})
    dimensions = {key: {'expected': expected, 'actual': review[key], 'agreement': review[key] == expected}
                  for key, expected in case['expected_dimensions'].items() if expected is not None}
    return dict(actual_keep=keep, expected_keep=case['expected_keep'], dimensions=dimensions,
                agrees=keep == case['expected_keep'] and all(v['agreement'] for v in dimensions.values()))


def prepare(root, budget, variant=None):
    root.mkdir(parents=True, exist_ok=False)
    cases = selected_cases()
    write_json(root / 'controls.json', cases)
    requests = []
    variants = (variant,) if variant is not None else AB_VARIANTS
    for variant in variants:
        for case in cases:
            payload = diagnostic_request(case['record'], variant)
            requests.append(dict(variant=variant, name=case['name'], language=case['record']['language'],
                                 prompt_tokens=budget.measure(payload), request=payload))
    write_json(root / 'requests.json', requests)
    write_json(root / 'manifest.json', dict(model=MODEL, enable_thinking=False, context_limit=8192,
        controls=8, controls_by_split=dict(Counter(c['split'] for c in cases)),
        controls_sha256=file_hash(root / 'controls.json'), requests_sha256=file_hash(root / 'requests.json'),
        max_requests=len(requests), variants=list(variants), retries=0, concurrency_limit=8,
        default_concurrency=2, raw_response_cap_bytes=MAX_RESPONSE_BYTES,
        heldout_used=False, quality_gate_changes_authorized=False,
        implementation_pins={name: file_hash(Path(__file__).with_name(name)) for name in
            ('multilingual_diagnose.py', 'multilingual_calibration.py', 'multilingual_review.py', 'multilingual_review_evidence.py', 'multilingual_review_structured.py')},
        tokenizer_pins={name: file_hash(TOKENIZER_DIR / name) for name in
            ('tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja')}))
    return cases, requests


async def replay(root, endpoints, cases, requests, concurrency=2, variant=None):
    import aiohttp
    if not endpoints or not 1 <= concurrency <= 8:
        raise ValueError('Require existing endpoints and concurrency 1..8')
    writer = RawResponseWriter(root / 'raw')
    outcomes = []
    semaphore = asyncio.Semaphore(concurrency)
    async def one(session, item, index):
        case = next(c for c in cases if c['name'] == item['name'])
        outcome = {key: item[key] for key in ('name', 'variant', 'language', 'prompt_tokens')}
        outcome.update(group=case['group'], split=case['split'], expected_keep=case['expected_keep'])
        async with semaphore:
            try:
                review = await captured_query(session, endpoints[index % len(endpoints)], item['request'], writer,
                                             {key: item[key] for key in ('name', 'variant', 'prompt_tokens')})
                outcome['review'] = review
                outcome.update(**assess(case, review, item['variant']))
            except Exception as exc:
                outcome.update(agrees=False, error=repr(exc))
        outcomes.append(outcome)
        write_json(root / 'progress.json', {'outcomes': outcomes})
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),
            connector=aiohttp.TCPConnector(limit=concurrency)) as session:
        stages = ((variant,),) if variant is not None else (AB_VARIANTS[:2], AB_VARIANTS[2:])
        for variants in stages:
            if variant is None and variants == AB_VARIANTS[2:] and all(o['agrees'] for o in outcomes if o['variant'] == 'schema4096'):
                break
            for current_variant in variants:
                selected = [r for r in requests if r['variant'] == current_variant]
                await asyncio.gather(*(one(session, item, i) for i, item in enumerate(selected)))
    summary = {variant: {'completed': len(rows := [o for o in outcomes if o['variant'] == variant]),
                        'agreement': sum(o['agrees'] for o in rows), 'errors': sum('error' in o for o in rows)}
               for variant in VARIANTS}
    passing = [v for v in VARIANTS if summary[v]['completed'] == 8 and summary[v]['agreement'] == 8]
    report = dict(outcomes=outcomes, summary=summary, concurrency=concurrency,
        recommended_variant=passing[0] if passing else None,
        recommendation='Re-run the full pinned calibration in a NEW root before generation; no automatic setting changes.'
            if passing else 'Pause: inspect raw output and language/dimension failures; do not relax the quality gate.',
        heldout_used=False, generation_authorized=False, native_quality_certified=False)
    from .multilingual_calibration import score_reviews
    report['calibration_by_variant'] = {}
    for current_variant in dict.fromkeys(o['variant'] for o in outcomes):
        reviews = {o['name']: o['review'] for o in outcomes
                   if o['variant'] == current_variant and 'review' in o}
        report['calibration_by_variant'][current_variant] = score_reviews(
            cases, reviews, validator=lambda review, record: configured_review_keeps(
                review, record, {'review_options': {'variant': current_variant}}))
    raw_evidence = []
    for path in sorted(writer.root.glob('*.response.json')):
        response = load(path)
        request_id = response['request_id']
        request_record = load(writer.root / f'{request_id}.request.json')
        metadata_path = writer.root / f'{request_id}.metadata.json'
        metadata = load(metadata_path) if metadata_path.exists() else {'finish_reason': None, 'usage': None}
        raw_evidence.append(dict(request_id=request_id, path=str(path),
            control=request_record['metadata'], status=response['status'], bytes_saved=response['bytes_saved'],
            truncated=response['truncated'], transport_error=response.get('transport_error'), **{
                k: v for k, v in metadata.items() if k != 'request_id'}))
    report['raw_evidence'] = raw_evidence
    report['diagnostic_caution'] = ('Length finishes alone do not establish insufficient useful output budget. '
        'Inspect usage, literal content, whitespace and repetition before attributing cause.')
    write_json(root / 'report.json', report)
    return report


async def wait_ready(root, endpoints, seconds):
    import aiohttp
    deadline = time.monotonic() + seconds
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
        while True:
            ready = []
            for endpoint in endpoints:
                try:
                    async with session.get(endpoint.rstrip('/') + '/models') as response:
                        body = await response.json()
                        ready.append(response.status == 200 and MODEL in {m['id'] for m in body['data']})
                except Exception:
                    ready.append(False)
            write_json(root / 'client-status.json', dict(phase='ready' if all(ready) else 'waiting_for_existing_teacher',
                pid=os.getpid(), endpoints=endpoints, ready=ready, time=time.time()))
            if all(ready):
                return
            if time.monotonic() >= deadline:
                raise TimeoutError('Existing teacher readiness deadline expired; no teacher launched')
            await asyncio.sleep(min(5, max(0, deadline - time.monotonic())))


async def run_prepared(root, endpoints, cases, requests, concurrency, wait_seconds, variant=None):
    if wait_seconds:
        await wait_ready(root, endpoints, wait_seconds)
    manifest = load(root / 'manifest.json')
    for name, expected in manifest['implementation_pins'].items():
        if file_hash(Path(__file__).with_name(name)) != expected:
            raise ValueError('Diagnostic implementation changed while waiting: ' + name)
    for name in ('controls', 'requests'):
        if file_hash(root / f'{name}.json') != manifest[f'{name}_sha256']:
            raise ValueError('Diagnostic prepared input changed: ' + name)
    write_json(root / 'client-status.json', dict(phase='replaying', pid=os.getpid(), endpoints=endpoints,
        concurrency=concurrency, time=time.time()))
    report = await replay(root, endpoints, cases, requests, concurrency, variant)
    write_json(root / 'client-status.json', dict(phase='complete', pid=os.getpid(), time=time.time(),
        recommended_variant=report['recommended_variant'], generation_authorized=False))
    print(json.dumps(report['summary']), flush=True)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--endpoints', nargs='+')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--concurrency', type=int, default=2, choices=range(1, 9))
    parser.add_argument('--wait-ready-seconds', type=int, default=0)
    parser.add_argument('--variant', choices=VARIANTS)
    args = parser.parse_args()
    if not args.prepare_only and not args.endpoints:
        parser.error('--endpoints is required unless --prepare-only')
    if args.endpoints and len(args.endpoints) > 8:
        parser.error('At most eight existing endpoints')
    if not 0 <= args.wait_ready_seconds <= 7200:
        parser.error('--wait-ready-seconds must be in 0..7200')
    cases, requests = prepare(args.root, PromptBudget(), args.variant)
    if not args.prepare_only:
        with lock(args.root / '.diagnose.lock'):
            try:
                asyncio.run(run_prepared(args.root, args.endpoints, cases, requests,
                                         args.concurrency, args.wait_ready_seconds, args.variant))
            except BaseException as exc:
                write_json(args.root / 'client-status.json', dict(phase='failed', pid=os.getpid(),
                    error=repr(exc), time=time.time(), generation_authorized=False))
                raise


if __name__ == '__main__':
    main()
