"""Pinned, resumable CPU clients for exposed controls and bounded generation.

No servers, GPU allocation, admission, bulk generation or automatic successors.
The parent owns prepare/run after the independently owned adapters are ready.
"""
import argparse
import asyncio
import base64
from collections import Counter
from collections.abc import Mapping
from contextlib import contextmanager
import copy
import fcntl
import importlib
import json
import os
from pathlib import Path
import time
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from .audit_pilot_gpu import TOKENIZER_DIR
from .io import digest, file_hash, load, write_json
from .multilingual_diagnose import RawResponseWriter, MAX_RESPONSE_BYTES
from .multilingual_seeds import LANGUAGES
from .multilingual_tasks import MODEL

VERSION = 'multilingual-calibration-v6'
REVIEW_MODULE = 'dfm12.multilingual_review_indexed'
GENERATION_MODULE = 'dfm12.multilingual_generation_v4'
TOOLS_MODULE = 'dfm12.multilingual_tool_dialogue'
TOOLS = {'single', 'clarify', 'multi', 'error', 'retry', 'no-call'}
NONTOOLS = {
    'grounded-instruct': {'factual QA', 'explanation', 'comparison', 'structured extraction'},
    'summary-rewrite': {'one-sentence summary', 'two-sentence summary', 'bullet summary',
        'longer summary', 'rewrite for a child', 'formal rewrite', 'past-tense rewrite',
        'plain-language rewrite', 'summary with exactly three bullets', 'rewrite and preserve all numbers'},
    'multiturn': {'follow-up reference resolution', 'change requirements', 'clarify ambiguity',
        'collaborative writing', 'correct a misunderstanding'},
    'openhermes': {'translate', 'adapt scenario'}, 'math-code': {'math', 'code'},
}
FLAGS = ('language_correct', 'meaning_correct', 'constraints_met')


def adapters():
    review = importlib.import_module(REVIEW_MODULE)
    generation = importlib.import_module(GENERATION_MODULE)
    importlib.import_module(TOOLS_MODULE)
    for module, names in ((review, ('request', 'keeps', 'deterministic_checks')),
                          (generation, ('request', 'assemble', 'decode'))):
        if not all(callable(getattr(module, n, None)) for n in names):
            raise ValueError('Adapter interface incomplete: ' + module.__name__)
    return review, generation


def generation_request(spec, generation, endpoint_models=None):
    if spec['family'] == 'tool-dialogue':
        payload = importlib.import_module(TOOLS_MODULE).request(spec)
    else:
        payload = generation.request(spec, endpoint_models=endpoint_models)
        payload.pop('structured_outputs', None)
        payload['response_format'] = {'type': 'json_schema', 'json_schema': {
            'name': 'generation', 'strict': True, 'schema': generation.schema(spec)}}
    payload['repetition_penalty'] = 1.15
    return payload


def generation_assemble(spec, output, generation):
    module = importlib.import_module(TOOLS_MODULE) if spec['family'] == 'tool-dialogue' else generation
    row = module.assemble(spec, output)
    if spec['family'] == 'tool-dialogue':
        from .multilingual_pilot import student_validate
        student_validate(generation._renderer(), row)
    return row


def review_request(record, review):
    payload = review.request(record)
    payload.pop('structured_outputs', None)
    payload['response_format'] = {'type': 'json_schema', 'json_schema': {
        'name': 'review', 'strict': True, 'schema': review.schema(record)}}
    payload['frequency_penalty'] = 0.5
    return payload


def compact_request(payload):
    # Native schema decoding avoids costly custom EBNF masks. Keep the original
    # bounds for CPU validation; bounded string lowering has escape defects.
    transport = copy.deepcopy(payload)
    response_format = transport.pop('response_format', None)
    if response_format is None:
        return transport, None
    schema = response_format['json_schema']['schema']
    grammar_schema = copy.deepcopy(schema)
    def strip_lengths(node):
        if isinstance(node, dict):
            if node.get('type') == 'string':
                node.pop('minLength', None)
                node.pop('maxLength', None)
            for value in node.values():
                strip_lengths(value)
        elif isinstance(node, list):
            for value in node:
                strip_lengths(value)
    strip_lengths(grammar_schema)
    transport['structured_outputs'] = {'json': grammar_schema}
    return transport, schema


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError('Nonfinite JSON constant: ' + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


class HTTPFailure(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__(f'HTTP {status}')


async def raw_query(session, endpoint, payload, writer, metadata, *, offload_writer=False):
    """Capture bytes before strict envelope parsing; leave completion text raw."""
    async def persist(fn, *args, **kwargs):
        if offload_writer:
            return await asyncio.to_thread(fn, *args, **kwargs)
        return fn(*args, **kwargs)
    rid = await persist(writer.begin, endpoint, payload, metadata)
    status, body, truncated = None, bytearray(), False
    try:
        async with session.post(endpoint.rstrip('/') + '/chat/completions', json=payload) as response:
            status = response.status
            async for chunk in response.content.iter_chunked(65536):
                remaining = MAX_RESPONSE_BYTES - len(body)
                body.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    truncated = True
                    break
    except BaseException as exc:
        await persist(writer.finish, rid, status=status, raw_body_base64=base64.b64encode(body).decode(),
            raw_body_utf8=body.decode('utf-8', errors='replace'), transport_error=repr(exc), truncated=truncated)
        raise
    await persist(writer.finish, rid, status=status, raw_body_base64=base64.b64encode(body).decode(),
        raw_body_utf8=body.decode('utf-8', errors='replace'), truncated=truncated)
    if status != 200:
        raise HTTPFailure(status)
    if truncated:
        raise ValueError('Raw HTTP byte budget exceeded')
    decoded = strict_json(bytes(body).decode('utf-8'))
    choice = decoded['choices'][0]
    return dict(content=choice['message']['content'], finish_reason=choice.get('finish_reason'),
                usage=decoded.get('usage'), raw_request_id=rid)


class Budget:
    """Actual local Gemma template; context is checked again against live servers."""
    def __init__(self, directory=TOKENIZER_DIR, tokenizer=None):
        if tokenizer is None:
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(str(directory), local_files_only=True)
        self.tokenizer = tokenizer

    def measure(self, payload, limit=16384):
        if payload.get('model') != MODEL or payload.get('chat_template_kwargs') != {'enable_thinking': False}:
            raise ValueError('Exact Gemma teacher and disabled thinking required')
        reserve = payload.get('max_tokens')
        if type(reserve) is not int or reserve <= 0 or not 0 < limit <= 16384:
            raise ValueError('Invalid token budget')
        ids = self.tokenizer.apply_chat_template(payload['messages'], tokenize=True,
            add_generation_prompt=True, enable_thinking=False)
        if isinstance(ids, Mapping):
            ids = ids['input_ids']
        if not isinstance(ids, list) or not all(type(i) is int for i in ids):
            raise ValueError('Expected flat actual-template token IDs')
        if len(ids) + reserve > limit:
            raise ValueError(f'Full prompt {len(ids)} + reserve {reserve} exceeds context {limit}; no truncation')
        return dict(prompt_tokens=len(ids), max_tokens=reserve, total_tokens=len(ids)+reserve,
                    context_limit=limit, token_ids_sha256=digest(ids))


def validate_specs(specs):
    if not 112 <= len(specs) <= 182:
        raise ValueError('Require 42 tools plus 70..140 representative non-tools')
    keys = [(s['language_code'], s['family'], s['slot']) for s in specs]
    if len(set(keys)) != len(keys) or any(s.get('contract_version') != 4 for s in specs):
        raise ValueError('Unique contract-v4 specifications required')
    if {s['language_code'] for s in specs} != set(LANGUAGES):
        raise ValueError('All seven languages required')
    for lang in LANGUAGES:
        selected = [s for s in specs if s['language_code'] == lang]
        tools = [s['subtype'] for s in selected if s['family'] == 'tool-dialogue']
        if len(tools) != 6 or set(tools) != TOOLS:
            raise ValueError('Exactly six tool subtypes per language required: ' + lang)
        if not set(NONTOOLS).issubset({s['family'] for s in selected}):
            raise ValueError('Every non-tool family required per language: ' + lang)
    for family, subtypes in NONTOOLS.items():
        if {s['subtype'] for s in specs if s['family'] == family} != subtypes:
            raise ValueError('Representative pool must cover every subtype: ' + family)
    if any(s['family'] not in {*NONTOOLS, 'tool-dialogue'} for s in specs):
        raise ValueError('Unknown generation family')


def verify_pins(root, manifest):
    for section in ('external_pins', 'implementation_pins'):
        for path, expected in manifest[section].items():
            if not Path(path).is_file() or file_hash(path) != expected:
                raise ValueError('Pinned file drift: ' + path)
    for name, expected in manifest['input_pins'].items():
        if file_hash(root / name) != expected:
            raise ValueError('Prepared input drift: ' + name)


def implementation_paths():
    # Explicit runtime/validation dependency surface, not unrelated DFM12 agents.
    names = ('multilingual_calibration_v6 multilingual_generation_v4 multilingual_review_indexed '
        'multilingual_tool_dialogue multilingual_tasks multilingual_references multilingual_seeds '
        'multilingual_tool_calibration multilingual_calibration multilingual_review '
        'multilingual_review_routed multilingual_review_tools multilingual_review_structured '
        'multilingual_review_evidence multilingual_pilot multilingual_diagnose identity_gpu '
        'audit_pilot_gpu io jobs records prepare catalog transform calibration_streaming').split()
    paths = [Path(__file__).with_name(n + '.py') for n in names]
    paths.extend(Path(__file__).resolve().parents[1] / 'scripts' / name for name in
        ('tokenize_chat_template.py', 'prepare_dfm11_tool_replacements.py', 'prepare_dfm7_special_sources.py'))
    return paths


def model_receipts(path):
    docs = load(path)
    # Earlier borrowed-endpoint receipts retain each returned model entry,
    # rather than its enclosing /models list. Preserve those exact entries.
    if isinstance(docs, dict) and docs and all(k.startswith('http://') for k in docs):
        docs = [{'data': [entry]} for entry in docs.values()]
    docs = [docs] if isinstance(docs, dict) and 'data' in docs else docs
    if not isinstance(docs, list) or not docs:
        raise ValueError('Supply saved actual /models document(s)')
    for doc in docs:
        endpoint_limit(doc)
    return docs


def build_inputs(root, seeds_root, endpoint_models, tokenizer_dir=TOKENIZER_DIR):
    """Deterministic pre-seal selection; failures logged, never silently dropped."""
    _, generation = adapters()
    from .multilingual_tasks import spec_for
    from .multilingual_tool_calibration import routed_cases
    root, seeds_root = Path(root), Path(seeds_root)
    if root.exists():
        raise ValueError('Input bundle root must be new')
    docs = model_receipts(endpoint_models)
    paths = [seeds_root / f'seeds-{lang}.json' for lang in (*LANGUAGES, 'openhermes')]
    paths.append(Path(endpoint_models))
    pins = {str(p.resolve()): file_hash(p) for p in paths}
    seeds = {lang: load(seeds_root / f'seeds-{lang}.json') for lang in (*LANGUAGES, 'openhermes')}
    budget, selected, exclusions = Budget(tokenizer_dir), [], []
    config = dict(contract_version=4, cohort=root.name, quotas={'openhermes': 1000})
    for li, lang in enumerate(LANGUAGES):
        targets = [('tool-dialogue', subtype) for subtype in ('single','clarify','multi','error','retry','no-call')]
        for family, subtypes in NONTOOLS.items():
            ordered = sorted(subtypes)
            targets.extend((family, ordered[(2*li+j) % len(ordered)]) for j in range(2))
        for target_index, (family, subtype) in enumerate(targets):
            for attempt in range(50):
                if family == 'tool-dialogue':
                    slot = attempt*6 + ('single','clarify','multi','error','retry','no-call').index(subtype)
                else:
                    slot = target_index*100 + attempt*2 + int(
                        (family=='math-code' and subtype=='code') or (family=='openhermes' and subtype=='adapt scenario'))
                try:
                    spec = spec_for(lang, family, slot, 0, seeds, config)
                    if family != 'tool-dialogue':
                        spec['subtype'] = subtype
                    request = generation_request(spec, generation, docs)
                    budget.measure(request)
                except ValueError as exc:
                    exclusions.append(dict(language=lang, family=family, subtype=subtype, slot=slot, error=str(exc)))
                    continue
                selected.append(spec)
                break
            else:
                raise ValueError(f'No fitting source for {lang}/{family}/{subtype}; selection not sealed')
    validate_specs(selected)
    if any(file_hash(p) != h for p, h in pins.items()):
        raise ValueError('Seed drift during bounded selection')
    root.mkdir(parents=True, exist_ok=False)
    write_json(root/'controls.json', routed_cases())
    write_json(root/'specifications.json', selected)
    write_json(root/'selection.json', dict(seed_pins=pins, excluded_count=len(exclusions), exclusions=exclusions,
        selected=len(selected), tools=42, nontools=70, preseal_selection=True,
        all_subtypes_across_pool=True, all_families_each_language=True,
        files={n:file_hash(root/n) for n in ('controls.json','specifications.json')}))
    return selected


def prepare(root, controls_path, specs_path, tests, endpoint_models, tokenizer_dir=TOKENIZER_DIR):
    """Explicit CPU action only; never called implicitly by run."""
    if Path(root).exists():
        raise ValueError('Prepared run root must be new')
    review, generation = adapters()  # Fail before creating a root if owners are not ready.
    xml = ET.parse(tests).getroot()
    suites = list(xml.iter('testsuite'))
    if not suites or not sum(int(s.get('tests', 0)) for s in suites) or any(
            int(s.get(k, 0)) for s in suites for k in ('failures', 'errors', 'skipped')):
        raise ValueError('Passing integration test XML required')
    tested = {c.get('classname', '').split('.')[-1] for c in xml.iter('testcase')}
    required = {'test_dfm12_multilingual_' + name for name in
                ('calibration_v6', 'generation_v4', 'review_indexed', 'tool_dialogue')}
    if not required.issubset(tested):
        raise ValueError('Test receipt must include v6 and all three adapter suites')
    docs = model_receipts(endpoint_models)
    external = [Path(controls_path), Path(specs_path), Path(tests), Path(endpoint_models)]
    selection = Path(specs_path).parent / 'selection.json'
    if not selection.exists():
        raise ValueError('Pre-seal selection/exclusion receipt required')
    selected = load(selection)
    if selected['files']['specifications.json'] != file_hash(specs_path):
        raise ValueError('Selection specification pin mismatch')
    external.extend([selection, *(Path(p) for p in selected['seed_pins'])])
    for p, expected in selected['seed_pins'].items():
        if file_hash(p) != expected:
            raise ValueError('Selected seed pin drift: ' + p)
    student_metadata = Path('data/sampled_dfm11/metadata.json')
    info = load(student_metadata)['tokenizer_info']
    external.extend([student_metadata, Path(info['tokenizer_path']), Path(info['chat_template_path'])])
    external += [Path(tokenizer_dir) / n for n in ('tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja')]
    pins = {str(p.resolve()): file_hash(p) for p in external}
    controls, specs = load(controls_path), load(specs_path)
    # Compare complete existing records/labels, not merely a count of 242.
    from .multilingual_tool_calibration import routed_cases
    if controls != routed_cases() or len(controls) != 242:
        raise ValueError('Require complete unchanged 242 routed controls')
    controls = copy.deepcopy(controls)
    for c in controls:
        c.update(original_split=c['split'], split='exposed_regression', native_gold=False)
    validate_specs(specs)
    budget = Budget(tokenizer_dir)
    items = []
    for kind, entries in (('control', controls), ('generation', specs)):
        for entry in entries:
            payload = review_request(entry['record'], review) if kind == 'control' else generation_request(entry, generation, docs)
            transport, schema = compact_request(payload)
            measurement = budget.measure(transport)
            items.append(dict(id=digest([kind, entry]), kind=kind, input=entry,
                request=transport, schema=schema, budget=measurement))
    if any(file_hash(p) != h for p, h in pins.items()):
        raise ValueError('Input changed during preparation')
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    write_json(root / 'items.json', items)
    # Pin local dependencies conservatively, including newly integrated adapters.
    modules = implementation_paths()
    modules.extend(Path(__file__).resolve().parents[1] / 'tests' / (name + '.py') for name in sorted(required))
    manifest = dict(version=VERSION, model=MODEL, tokenizer_dir=str(Path(tokenizer_dir).resolve()),
        controls=242, generation_cases=len(specs), control_labels='known/exposed; not fresh or native gold',
        ground_truth_counts=dict(Counter(str(c['expected_keep']) for c in controls)),
        context_ceiling=16384, max_infrastructure_retries=3, endpoint_circuit_failures=3,
        admission_authorized=False, bulk_authorized=False, automatic_successor=False,
        external_pins=pins, implementation_pins={str(p.resolve()): file_hash(p) for p in modules},
        input_pins={'items.json': file_hash(root / 'items.json')})
    write_json(root / 'manifest.json', manifest)
    write_json(root / 'seal.json', {'manifest_sha256': file_hash(root / 'manifest.json')})
    return manifest


@contextmanager
def timed_lock(path, seconds=10):
    with Path(path).open('a') as handle:
        deadline = time.monotonic() + seconds
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Calibration root already locked')
                time.sleep(.05)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def endpoint_limit(document):
    matches = [m for m in document.get('data', []) if m.get('id') == MODEL]
    if len(matches) != 1 or type(matches[0].get('max_model_len')) is not int:
        raise ValueError('Exact model and advertised context required')
    limit = min(16384, matches[0]['max_model_len'])
    if limit < 16384:
        raise ValueError('This prepared calibration requires verified 16K context')
    return limit


def validate_endpoints(endpoints):
    parsed = [urlparse(e) for e in endpoints]
    if (len(endpoints) != 8 or len(set(endpoints)) != 8
            or {p.port for p in parsed} != set(range(8600, 8608))
            or any(p.scheme != 'http' or p.hostname not in ('localhost', '127.0.0.1')
                   or p.path.rstrip('/') != '/v1' or p.query or p.fragment for p in parsed)):
        raise ValueError('Require eight borrowed local /v1 endpoints 8600..8607')


def audit_record(candidate):
    record = {k: candidate[k] for k in ('language', 'family', 'messages', 'tools')}
    record['language_name'] = LANGUAGES[candidate['language']]
    spec = candidate['provenance']
    record['requested_subtype'] = spec['subtype']
    for key in ('reference', 'scenario', 'terminal_evidence'):
        if key in spec:
            record[key] = spec[key]
        elif key in candidate:
            record[key] = candidate[key]
    if 'tool_dialogue_grounding' in spec:
        record['tool_dialogue_grounding'] = spec['tool_dialogue_grounding']
    if 'source' in spec:
        record['source'] = spec['source']
        if candidate['family'] == 'openhermes':
            record['source_messages'] = spec['source']['messages']
    return record


def review_result(review, record, adapter):
    semantic = adapter.keeps(review, record, deterministic=False)
    checks = adapter.deterministic_checks(record)
    return dict(status='valid', semantic_keep=semantic, deterministic_checks=checks,
                deterministic_pass=all(c['passed'] for c in checks),
                effective_keep=semantic and all(c['passed'] for c in checks))


class Stages:
    def __init__(self, root, budget, writer, session, query=raw_query):
        self.root, self.budget, self.writer, self.session, self.query = root, budget, writer, session, query
        self.failures = Counter()

    async def call(self, key, stage, payload, schema, endpoint, limit, spec=None):
        """Retry only explicit 429/503 rejections or proven pre-connect errors."""
        import aiohttp
        import jsonschema
        path = self.root / 'stages' / f'{key}-{stage}.json'
        state = load(path) if path.exists() else dict(attempts=0, status='pending')
        request_hash = digest(payload)
        if state.get('request_sha256', request_hash) != request_hash:
            raise ValueError('Stage request drift')
        if state['status'] == 'inflight':
            state.update(status='abort_status_unknown', error='Interrupted in-flight request; no automatic replay')
            write_json(path, state)
        if state['status'] not in ('pending', 'retryable'):
            return state
        if self.failures[endpoint] >= 3:
            return dict(status='circuit_open')
        try:
            measurement = self.budget.measure(payload, limit)
        except ValueError as exc:
            state.update(status='invalid_preflight', error=str(exc))
            write_json(path, state)
            return state
        write_json(self.root / 'requests' / f'{key}-{stage}.json', dict(request=payload,
            schema=schema, budget=measurement, request_sha256=request_hash))
        while state['attempts'] < 4 and self.failures[endpoint] < 3:
            state.update(status='inflight', attempts=state['attempts']+1,
                request_sha256=request_hash, endpoint=endpoint, started=time.time())
            write_json(path, state)
            try:
                raw = await self.query(self.session, endpoint, payload, self.writer,
                    dict(id=key, stage=stage, attempt=state['attempts'], **measurement))
                state['raw'] = raw
                write_json(path, state)
                if raw['finish_reason'] != 'stop':
                    raise ValueError('Incomplete output: ' + str(raw['finish_reason']))
                output = strict_json(raw['content'])
                state.update(output=output, json_valid=True)
                if schema is not None:
                    jsonschema.validate(output, schema)
                state['structure_valid'] = True
                if spec is not None and spec['family'] != 'tool-dialogue':
                    generator = importlib.import_module(GENERATION_MODULE)
                    state['structure_valid'] = False
                    jsonschema.validate(output, generator.schema(spec))
                    state['structure_valid'] = True
                    # Crucially use original text, never reserialized parsed JSON.
                    state['content_constraints_valid'] = False
                    output = generator.decode(spec, raw['content'], raw['finish_reason'])
                    state['output'] = output
                    state['content_constraints_valid'] = True
                state.update(status='complete', structure_valid=True)
                self.failures[endpoint] = 0
            except (asyncio.CancelledError, asyncio.TimeoutError) as exc:
                state.update(status='abort_status_unknown', error=repr(exc))
                self.failures[endpoint] = 3
                write_json(path, state)
                if isinstance(exc, asyncio.CancelledError):
                    raise
            except Exception as exc:
                retry = isinstance(exc, aiohttp.ClientConnectorError) or (
                    isinstance(exc, HTTPFailure) and exc.status in (429, 503))
                if retry:
                    self.failures[endpoint] += 1
                    state.update(status='retryable', error=repr(exc))
                elif isinstance(exc, aiohttp.ClientError) or (isinstance(exc, HTTPFailure) and exc.status in (502, 504)):
                    state.update(status='abort_status_unknown', error=repr(exc))
                    self.failures[endpoint] = 3
                elif isinstance(exc, HTTPFailure):
                    state.update(status='http_rejected', error=repr(exc))
                    # A bad chat route/auth/request contract must not consume
                    # the remaining queue as supposed model-quality failures.
                    self.failures[endpoint] = 3
                else:
                    state.update(status='invalid_output', error=repr(exc))
                    state.setdefault('structure_valid', False if 'output' in state else None)
            write_json(path, state)
            if state['status'] != 'retryable':
                break
            await asyncio.sleep(min(state['attempts'], 3))
        if state['status'] == 'retryable' and state['attempts'] >= 4:
            state['status'] = 'infrastructure_exhausted'
            write_json(path, state)
        return state


def summarize(root, items):
    outcomes = [load(p) for p in (root / 'outcomes').glob('*.json')]
    controls = [o for o in outcomes if o['kind'] == 'control']
    generation = [o for o in outcomes if o['kind'] == 'generation']
    report = dict(version=VERSION, target=len(items), recorded=len(outcomes),
        controls=dict(total=242, statuses=dict(Counter(o['status'] for o in controls)),
            missing=242-len(controls),
            semantic_agreements=sum(o.get('semantic_agreement') is True for o in controls),
            false_accepts=sum(o.get('false_accept') is True for o in controls),
            positive_rejections=sum(o.get('positive_rejection') is True for o in controls),
            effective_agreements=sum(o.get('effective_agreement') is True for o in controls),
            dimension_mismatches=sum(o.get('dimension_mismatches') or 0 for o in controls),
            labels='known/exposed; not fresh or native-language gold'),
        generation=dict(total=sum(i['kind']=='generation' for i in items),
            statuses=dict(Counter(o['status'] for o in generation)),
            json_valid=sum(o.get('json_valid') is True for o in generation),
            structure_valid=sum(o.get('structure_valid') is True for o in generation),
            content_constraints_valid=sum(o.get('content_constraints_valid') is True for o in generation),
            assembled=sum(o.get('assembled') is True for o in generation),
            semantic_keeps=sum(o.get('semantic_keep') is True for o in generation),
            deterministic_passes=sum(o.get('deterministic_pass') is True for o in generation)),
        by_language={lang:dict(Counter(o['status'] for o in outcomes if o.get('language')==lang)) for lang in LANGUAGES},
        admitted_rows=0, admitted_tokens=0, admission_authorized=False, bulk_authorized=False,
        automatic_successor=False, native_quality_certified=False)
    write_json(root / 'report.json', report)
    return report


async def execute(root, endpoints, timeout=180, deadline=21600, concurrency_per_server=1):
    import aiohttp
    validate_endpoints(endpoints)
    if not 1 <= concurrency_per_server <= 32:
        raise ValueError('Concurrency per server must be between 1 and 32')
    if not 1 <= timeout <= 600 or not 1 <= deadline <= 21600:
        raise ValueError('Request timeout <=600s and run deadline <=6h required')
    manifest = load(root / 'manifest.json')
    if file_hash(root / 'manifest.json') != load(root / 'seal.json')['manifest_sha256']:
        raise ValueError('Manifest seal drift')
    if manifest['version'] != VERSION or manifest['admission_authorized'] or manifest['bulk_authorized']:
        raise ValueError('Invalid diagnostic policy')
    verify_pins(root, manifest)
    review, generation = adapters()
    budget = Budget(manifest['tokenizer_dir'])
    items = load(root / 'items.json')
    review_queue, generation_queue = asyncio.Queue(), asyncio.Queue()
    for item in items:
        path = root / 'outcomes' / f"{item['id']}.json"
        if path.exists() and load(path).get('terminal'):
            continue
        candidate_path = root / 'candidates' / f"{item['id']}.json"
        generation_path = root / 'stages' / f"{item['id']}-generate.json"
        if item['kind'] == 'generation' and candidate_path.exists() and generation_path.exists():
            saved = load(generation_path)
            if saved.get('status') == 'complete':
                review_queue.put_nowait({**item, 'candidate': load(candidate_path),
                    'generation_checks': {k: saved.get(k, False) for k in
                        ('json_valid', 'structure_valid', 'content_constraints_valid')}})
                continue
        (review_queue if item['kind']=='control' else generation_queue).put_nowait(item)
    status = dict(pid=os.getpid(), endpoints=endpoints, phase='preflight', admission_authorized=False,
                  concurrency_per_server=concurrency_per_server)
    write_json(root / 'status.json', status)
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout),
                connector=aiohttp.TCPConnector(limit=len(endpoints)*concurrency_per_server,
                                               limit_per_host=concurrency_per_server)) as session:
            health = {}
            for endpoint in endpoints:
                async with session.get(endpoint.rstrip('/') + '/models') as response:
                    response.raise_for_status()
                    doc = await response.json()
                    health[endpoint] = dict(document=doc, context=endpoint_limit(doc), time=time.time())
            write_json(root / f'health-{time.time_ns()}.json', health)
            # All saved requests must fit before any generation/review call.
            for item in items:
                budget.measure(item['request'], min(v['context'] for v in health.values()))
            verify_pins(root, manifest)
            from .calibration_streaming import stream_query
            clients = Stages(root, budget, RawResponseWriter(root / 'raw'), session, query=stream_query)
            generation_done = asyncio.Event()

            async def process(item, endpoint):
                key = item['id']
                outcome = dict(id=key, kind=item['kind'], terminal=False, admission_authorized=False,
                    language=item['input']['record']['language'] if item['kind']=='control' else item['input']['language_code'])
                path = root / 'outcomes' / f'{key}.json'
                def save():
                    write_json(path, outcome)
                if item['kind'] == 'control':
                    record = item['input']['record']
                    outcome.update(name=item['input']['name'], expected_keep=item['input']['expected_keep'],
                        expected_dimensions=item['input']['expected_dimensions'], split='exposed_regression')
                    payload, schema = item['request'], item['schema']
                elif 'candidate' not in item:
                    state = await clients.call(key, 'generate', item['request'], item['schema'], endpoint, health[endpoint]['context'], spec=item['input'])
                    outcome.update(json_valid=state.get('json_valid', False), structure_valid=state.get('structure_valid', False),
                        content_constraints_valid=state.get('content_constraints_valid', False))
                    if state['status'] != 'complete':
                        outcome.update(status=state['status'], terminal=state['status'] not in ('retryable','circuit_open'))
                        save()
                        return
                    try:
                        candidate = generation_assemble(item['input'], state['output'], generation)
                        write_json(root / 'candidates' / f'{key}.json', candidate)
                    except Exception as exc:
                        outcome.update(status='assembly_invalid', error=repr(exc), terminal=True)
                        save()
                        return
                    outcome.update(status='awaiting_content_review', assembled=True)
                    save()
                    review_queue.put_nowait({**item, 'candidate': candidate, 'generation_checks': {
                        k:outcome[k] for k in ('json_valid','structure_valid','content_constraints_valid')}})
                    return
                else:
                    outcome.update(json_valid=True, structure_valid=True, assembled=True)
                    outcome.update(item.get('generation_checks', {}))
                    record = audit_record(item['candidate'])
                    try:
                        payload, schema = compact_request(review_request(record, review))
                    except (ValueError, TypeError) as exc:
                        outcome.update(status='review_preflight_invalid', error=repr(exc), terminal=True)
                        save()
                        return
                checks = review.deterministic_checks(record)
                outcome.update(deterministic_checks=checks, deterministic_pass=all(c['passed'] for c in checks))
                state = await clients.call(key, 'review', payload, schema, endpoint, health[endpoint]['context'])
                if state['status'] != 'complete':
                    outcome.update(status=state['status'], terminal=state['status'] not in ('retryable','circuit_open'))
                else:
                    try:
                        outcome.update(review_result(state['output'], record, review), terminal=True)
                        if item['kind'] == 'control':
                            expected = item['input']['expected_keep']
                            outcome.update(semantic_agreement=outcome['semantic_keep']==expected,
                                false_accept=outcome['semantic_keep'] and not expected,
                                positive_rejection=not outcome['semantic_keep'] and expected,
                                effective_agreement=outcome['effective_keep']==expected,
                                dimension_mismatches=sum(state['output'][k]!=v for k,v in item['input']['expected_dimensions'].items() if v is not None))
                    except (ValueError, TypeError, KeyError) as exc:
                        outcome.update(status='review_invalid', error=repr(exc), terminal=True)
                save()

            async def worker(endpoint, queue, is_generation):
                while clients.failures[endpoint] < 3:
                    try:
                        item = await asyncio.wait_for(queue.get(), .2)
                    except asyncio.TimeoutError:
                        if is_generation or generation_done.is_set():
                            return
                        continue
                    try:
                        await process(item, endpoint)
                        path = root / 'outcomes' / f"{item['id']}.json"
                        if path.exists() and load(path)['status'] in ('retryable', 'circuit_open'):
                            queue.put_nowait(item)
                        summarize(root, items)
                    finally:
                        queue.task_done()

            async def generators():
                try:
                    await asyncio.gather(*(worker(e, generation_queue, True)
                        for _ in range(concurrency_per_server) for e in endpoints[4:]))
                finally:
                    generation_done.set()
            status['phase'] = 'running'
            write_json(root / 'status.json', status)
            tasks = [asyncio.create_task(generators())] + [
                asyncio.create_task(worker(e, review_queue, False))
                for _ in range(concurrency_per_server) for e in endpoints[:4]]
            try:
                await asyncio.wait_for(asyncio.gather(*tasks), deadline)
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            pending = [i['id'] for i in items if not (root/'outcomes'/f"{i['id']}.json").exists()
                or not load(root/'outcomes'/f"{i['id']}.json").get('terminal')]
            status.update(phase='blocked_infrastructure' if pending else 'completed_diagnostic', pending=pending,
                          endpoint_circuits=dict(clients.failures))
    except BaseException as exc:
        status.update(phase='interrupted', error=repr(exc))
        raise
    finally:
        summarize(root, items)
        write_json(root / 'status.json', status)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build-inputs', 'prepare', 'run'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--controls', type=Path)
    parser.add_argument('--specifications', type=Path)
    parser.add_argument('--tests', type=Path)
    parser.add_argument('--seeds-root', type=Path)
    parser.add_argument('--endpoint-models', type=Path, help='Saved actual /models receipt; live run rechecks all eight')
    parser.add_argument('--tokenizer-dir', type=Path, default=TOKENIZER_DIR)
    parser.add_argument('--endpoints', nargs='+')
    parser.add_argument('--request-timeout', type=int, default=180)
    parser.add_argument('--deadline', type=int, default=21600)
    parser.add_argument('--concurrency-per-server', type=int, default=1)
    args = parser.parse_args()
    if args.action == 'build-inputs':
        if not args.seeds_root or not args.endpoint_models:
            parser.error('build-inputs requires --seeds-root --endpoint-models')
        build_inputs(args.root, args.seeds_root, args.endpoint_models, args.tokenizer_dir)
    elif args.action == 'prepare':
        if not all((args.controls, args.specifications, args.tests, args.endpoint_models)):
            parser.error('prepare requires --controls --specifications --tests --endpoint-models')
        prepare(args.root, args.controls, args.specifications, args.tests, args.endpoint_models, args.tokenizer_dir)
    else:
        with timed_lock(args.root / '.v6.lock'):
            asyncio.run(execute(args.root, args.endpoints or [], args.request_timeout, args.deadline,
                                args.concurrency_per_server))


if __name__ == '__main__':
    main()
