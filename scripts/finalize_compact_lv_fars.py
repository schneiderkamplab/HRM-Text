"""Read-only LV/Fars compact-audit selection and native-student staging."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

from dfm12.io import digest, file_hash, load, lock, write_json
from dfm12.multilingual_calibration_v6 import strict_json
from dfm12.multilingual_pilot import student_validate
from dfm12.prepare import Renderer
from dfm12.wave_compact_review import visible
from scripts.compact_audit_postprocess import classify

BASE = Path('data/dfm13')
AUDIT = BASE / 'compact-source-audit-lv-fars-20261003-v1'
INVALID = BASE / 'compact-source-audit-lv-fars-invalid-retry-20261003-v1'
INTERRUPTED = BASE / 'compact-source-audit-lv-fars-interrupted-retry-20261003-v1'
REPAIRS = BASE / 'compact-source-repairs-lv-fars-20261003-v1'
FARS_HOLDS = Path('docs/reports/dfm13_farsinstruct_independent_holds_20261003.json')


def readonly(path):
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)


def keep(row):
    raw = row.get('raw', {})
    if raw.get('finish_reason') != 'stop':
        return False
    try:
        parsed = strict_json(raw['content'])
    except (ValueError, KeyError, TypeError):
        return False
    if 'raw_decision' in row and row['raw_decision'] != parsed:
        raise ValueError('Stored decision differs from raw review')
    result = classify(dict(raw=raw))
    return (result['status'] == 'usable_model_verdict'
            and result['decision']['verdict'] == 'keep'
            and result['decision']['issues'] == [])


def chosen(key, original, audit=AUDIT, invalid=INVALID,
           interrupted=INTERRUPTED, repairs=REPAIRS):
    """Explicit stage precedence; no fallback after a newer failed stage."""
    state = original.get('status')
    if state == 'valid' and original['decision']['verdict'] == 'repair':
        path = repairs / 'outcomes' / (key + '.json')
        return 'repair', path if path.exists() else None
    root = invalid if state == 'invalid' else interrupted if state == 'interrupted_unknown' else audit
    path = root / 'outcomes' / (key + '.json')
    return ('original' if root == audit else 'retry'), path if path.exists() else None


def validate_repair(original_record, row, bundle, request, parent_request_sha, parent_outcome_sha):
    if (row.get('status') != 'reaudited'
            or row.get('parent_request_sha256') != parent_request_sha
            or row.get('parent_outcome_sha256') != parent_outcome_sha
            or bundle.get('parent_request_sha256') != parent_request_sha
            or bundle.get('original_record_sha256') != digest(original_record)):
        raise ValueError('Repair lineage mismatch')
    raw = row['repair_raw']
    if raw.get('finish_reason') != 'stop':
        raise ValueError('Incomplete repair')
    output = strict_json(raw['content'])
    indices = {str(i) for i, m in enumerate(original_record['messages'])
               if m['role'] == 'assistant' and m.get('content') and not m.get('tool_calls')}
    if set(output) != indices:
        raise ValueError('Repair modified immutable fields')
    reconstructed = deepcopy(original_record)
    for index, text in output.items():
        if not isinstance(text, str) or not text.strip() or any(t in text for t in ('<start_of_turn>', '<end_of_turn>', '<|')):
            raise ValueError('Invalid repaired target')
        reconstructed['messages'][int(index)]['content'] = text
    if (reconstructed != bundle['record'] or reconstructed == original_record
            or request.get('repaired_record_sha256') != digest(reconstructed)
            or json.loads(request['request']['messages'][1]['content']) != reconstructed):
        raise ValueError('Fresh review candidate binding mismatch')
    return reconstructed


def stage(output, audit=AUDIT, invalid=INVALID, interrupted=INTERRUPTED,
          repairs=REPAIRS, workers=4):
    if output.exists():
        raise ValueError('Fresh immutable staging root required')
    manifest = load(audit / 'manifest.json')
    for root in (audit, invalid, interrupted):
        if not (root / 'complete.json').exists():
            raise ValueError('Original and technical retries must be complete')
    for root in (invalid, interrupted, repairs):
        m = load(root / 'manifest.json')
        if (Path(m['source']).resolve() != audit.resolve()
                or m.get('completion_sha256', m.get('source_completion_sha256')) != file_hash(audit / 'complete.json')):
            raise ValueError('Wrong retry/repair parent')
    lv, fars = Path(manifest['lv']), Path(manifest['fars'])
    # Verify immutable source metadata pins, not historical mutable implementation files.
    for p in (lv / 'manifest.json', lv / 'independent-review-holds.json', fars / 'manifest.json'):
        if manifest['pins'].get(str(p.resolve())) != file_hash(p):
            raise ValueError('Source metadata drift')
    holds_lv = {x['job_id'] for x in load(lv / 'independent-review-holds.json')['holds']}
    holds_fars = {x['ledger_row_id'] for x in load(FARS_HOLDS)['holds']}
    output.mkdir(parents=True)
    db = sqlite3.connect(output / 'selection.sqlite')
    db.execute('CREATE TABLE sources(id TEXT PRIMARY KEY,record TEXT,candidate TEXT,component TEXT,ledger_id TEXT,provenance TEXT)')
    db.execute('CREATE TABLE selections(id TEXT PRIMARY KEY,component TEXT,status TEXT,record TEXT,evidence TEXT,tokens INTEGER)')
    pins = {str(p.resolve()): file_hash(p) for p in (
        Path(__file__), FARS_HOLDS, lv / 'independent-review-holds.json',
        audit / 'manifest.json', audit / 'complete.json', invalid / 'manifest.json',
        invalid / 'complete.json', interrupted / 'manifest.json', interrupted / 'complete.json',
        repairs / 'manifest.json', lv / 'manifest.json', fars / 'manifest.json',
        Path('data/sampled_dfm11/metadata.json'))}
    info = load('data/sampled_dfm11/metadata.json')['tokenizer_info']
    for field in ('tokenizer_path', 'chat_template_path'):
        p = Path(info[field]); pins[str(p.resolve())] = file_hash(p)
    renderer = Renderer(info, 4096)
    counts = Counter()
    def add(key, record, candidate, component, ledger, provenance):
        db.execute('INSERT INTO sources VALUES(?,?,?,?,?,?)',
            (key, json.dumps(record, ensure_ascii=False), json.dumps(candidate, ensure_ascii=False),
             component, ledger, json.dumps(provenance)))
    with readonly(lv / 'jobs.sqlite') as source:
        source.execute('BEGIN')
        for key, raw, outcome, workdir, fp in source.execute("SELECT id,spec_json,outcome_json,workdir,fingerprint FROM jobs WHERE status='accepted' AND language='lv' AND family='grounded-instruct' ORDER BY id"):
            spec = json.loads(raw); result = json.loads(outcome)
            candidate = load(Path(workdir) / 'accepted' / (key + '.json'))
            if (digest({k: candidate[k] for k in ('messages', 'tools')}) != fp
                    or digest(spec) != result['spec_sha256'] or candidate['provenance']['source'] != spec['source']):
                raise ValueError('LV source binding mismatch')
            add('lv-' + key, visible(candidate), candidate, 'lv-grounded-instruct', key,
                dict(candidate_sha256=digest(candidate), spec_sha256=digest(spec), source_sha256=digest(spec['source'])))
    with readonly(fars / 'catalog.sqlite') as source:
        source.execute('BEGIN')
        for key, raw in source.execute('SELECT id,packet FROM catalog ORDER BY id'):
            packet = json.loads(raw); candidate = packet['candidate']; upstream = packet['upstream_record']
            if (digest(candidate) != packet['candidate_sha256'] or digest(upstream) != packet['upstream_sha256']
                    or candidate['messages'][0]['content'] != upstream['inputs']):
                raise ValueError('Fars packet binding mismatch')
            record = dict(language='fa', family='summary', messages=candidate['messages'],
                source=dict(text=upstream['inputs']), upstream_record=upstream, upstream_reference_is_not_gold=True)
            add('fars-' + key, record, candidate, packet['component'], packet['ledger_row_id'],
                dict(candidate_sha256=digest(candidate), source_sha256=digest(upstream), source_pin=packet['source_pin']))
    db.commit()
    if db.execute('SELECT count(*) FROM sources').fetchone()[0] != manifest['total']:
        raise ValueError('Population count mismatch')
    write_json(output / 'progress.json', dict(phase='selecting', total=manifest['total']))

    def inspect(item):
        key, encoded, candidate_raw, component, ledger, provenance = item
        base = json.loads(encoded); candidate = json.loads(candidate_raw)
        evidence = {}; status = 'invalid_evidence'; tokens = 0; exported = None
        try:
            op = audit / 'outcomes' / (key + '.json'); original = load(op)
            rp = audit / 'requests' / (key + '.json'); envelope = load(rp)
            parent_sha = file_hash(rp)
            evidence.update(original_outcome=str(op.resolve()), original_outcome_sha256=file_hash(op),
                original_request=str(rp.resolve()), original_request_sha256=parent_sha,
                original_candidate_sha256=digest(candidate), original_record_sha256=digest(base))
            if (json.loads(envelope['request']['messages'][1]['content']) != base
                    or envelope['provenance'] != json.loads(provenance)):
                raise ValueError('Audited original/source mismatch')
            kind, path = chosen(key, original, audit, invalid, interrupted, repairs)
            if path is None:
                return key, component, 'pending_repair_or_retry', None, evidence, 0
            row = load(path)
            evidence.update(stage=kind, final_outcome=str(path.resolve()), final_outcome_sha256=file_hash(path))
            if kind == 'retry' and row.get('parent_request_sha256') != parent_sha:
                raise ValueError('Retry request hash mismatch')
            if kind == 'repair':
                if row.get('status') != 'reaudited':
                    return key, component, 'repair_unresolved', None, evidence, 0
                bundle_path = repairs / 'repaired-records' / path.name
                request_path = repairs / 'reaudit-requests' / path.name
                base = validate_repair(base, row, load(bundle_path), load(request_path), parent_sha, file_hash(op))
                evidence.update(repaired_record=str(bundle_path.resolve()), repaired_record_sha256=file_hash(bundle_path),
                    fresh_request=str(request_path.resolve()), fresh_request_sha256=file_hash(request_path))
            if not keep(row):
                result = classify(row)
                return key, component, result.get('decision', {}).get('verdict', result['status']), None, evidence, 0
            evidence.update(final_record_sha256=digest(base), final_messages_sha256=digest(base['messages']),
                            compact_decision=classify(row)['decision'])
            if ledger in (holds_lv if key.startswith('lv-') else holds_fars):
                return key, component, 'independent_source_fidelity_hold', None, evidence, 0
            exported = deepcopy(candidate)
            exported['messages'] = deepcopy(base['messages'])
            exported.setdefault('tools', [])
            exported['id'] = digest([key, exported['messages'], exported['tools']])
            exported.update(admission_authorized=False, task='instruction',
                target_message_index=len(exported['messages']) - 1,
                target_policy='final_assistant_only_native_gemma', compact_audit=evidence)
            if ([m['role'] for m in exported['messages']] != ['user', 'assistant']
                    or exported['messages'][0] != candidate['messages'][0]):
                raise ValueError('Final target/user mismatch')
            student_validate(renderer, exported)
            tokens = exported['rendered_training_tokens']
            status = 'staged_keep'
        except Exception as exc:
            evidence['error'] = repr(exc)
        return key, component, status, exported if status == 'staged_keep' else None, evidence, tokens

    cursor = db.execute('SELECT * FROM sources ORDER BY id')
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while batch := cursor.fetchmany(128):
            for key, component, status, record, evidence, tokens in pool.map(inspect, batch):
                db.execute('INSERT INTO selections VALUES(?,?,?,?,?,?)',
                    (key, component, status, json.dumps(record, ensure_ascii=False) if record else None,
                     json.dumps(evidence, ensure_ascii=False), tokens))
                counts[status] += 1
            db.commit()
            write_json(output / 'progress.json', dict(phase='selecting', total=manifest['total'],
                terminal=sum(counts.values()), counts=dict(counts), upload_authorized=False))
    components = {}
    for component, count, tokens in db.execute("SELECT component,count(*),sum(tokens) FROM selections WHERE status='staged_keep' GROUP BY component"):
        folder = output / 'packages' / component
        (folder / 'data').mkdir(parents=True)
        path = folder / 'data/train.jsonl'
        with path.open('w') as handle:
            for raw, in db.execute("SELECT record FROM selections WHERE component=? AND status='staged_keep' ORDER BY id", (component,)):
                handle.write(raw + '\n')
        package = dict(component=component, rows=count, rendered_tokens=tokens, output=str(path.resolve()),
            output_sha256=file_hash(path), target_policy='final_assistant_only_native_gemma',
            context_length=4096, admission_authorized=False, publication_ready=False,
            pending='Poincare source-fidelity review, final repair completion, publication naming/license binding')
        write_json(folder / 'manifest.json', package)
        components[component] = package
    db.close()
    for path, sha in pins.items():
        if file_hash(path) != sha:
            raise ValueError('Immutable input changed during staging: ' + path)
    result = dict(total=manifest['total'], counts=dict(counts), packages=components, pins=pins,
        repairs_complete=(repairs / 'complete.json').exists(), selection_sha256=file_hash(output / 'selection.sqlite'),
        publication_ready=False, admission_authorized=False)
    write_json(output / 'receipt.json', result)
    write_json(output / 'seal.json', dict(receipt_sha256=file_hash(output / 'receipt.json')))
    print(json.dumps(dict(counts=dict(counts), packages={k:v['rows'] for k,v in components.items()})), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--workers', type=int, choices=range(1,9), default=4)
    a = p.parse_args()
    with lock(a.output.parent / (a.output.name + '.lock')):
        stage(a.output, workers=a.workers)
