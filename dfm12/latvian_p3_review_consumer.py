"""Explicit P3 source-fidelity protocol; preparation never launches inference."""
import argparse
import json
import os
from pathlib import Path
import time
import urllib.request
import uuid

from .io import digest, file_hash, load, rows, write_json
from .jobs import Queue, response_json
from .latvian_p3_alignment import REPAIR
from .latvian_p3_export import check
from .records import validate_messages

AUDIT_STAGE = 'p3_source_fidelity_protocol_31b'
REPAIR_STAGE = 'p3_source_fidelity_repair_31b'
REAUDIT_STAGE = 'p3_source_fidelity_reaudit_31b'
DIMENSIONS = ('source_fidelity', 'answer_correctness', 'instruction_compliance', 'latvian_quality')
PROTOCOL = """
Additional result contract: candidate_id is one supplied ID or null. Alignment is
supported/uncertain/wrong. Return pairing_checks with english_to_latvian and
latvian_to_english, each pass/fail/uncertain, checking all task-relevant premises,
entities, options, negation and requested output in BOTH directions. This checks
semantic correspondence, not a global one-to-one row mapping: duplicates exist.
Return pairing_evidence as a nonempty list of objects with english_quote and
latvian_quote, copied literally from the selected English question and the full
Latvian user question, plus explanation. Explain conflicting alternatives in
reason. Ordinal, retrieval agreement and previous verification flags are not
evidence. If no candidate is defensible, candidate_id=null, alignment=uncertain,
pairing_evidence=[] and keep=false. The four independent quality dimensions are
pass/fail/uncertain; keep can be true only when BOTH pairing checks and every
dimension pass. literal_evidence and reason must be nonempty strings. These are
model proposals, not independent pairing certification or training admission.
"""


def validate_review(result, record):
    candidates = {c['candidate_id']: c for c in record['english_candidates']}
    key = result.get('candidate_id')
    check(key is None or key in candidates, 'Unknown selected reference')
    check(result.get('alignment') in ('supported', 'uncertain', 'wrong'), 'Bad alignment')
    check(type(result.get('keep')) is bool, 'Bad keep')
    for name in DIMENSIONS:
        check(result.get(name) in ('pass', 'fail', 'uncertain'), 'Bad dimension: ' + name)
    checks = result.get('pairing_checks', {})
    for name in ('english_to_latvian', 'latvian_to_english'):
        check(checks.get(name) in ('pass', 'fail', 'uncertain'), 'Missing bidirectional pairing check')
    for name in ('reason', 'literal_evidence'):
        check(isinstance(result.get(name), str) and result[name].strip(), 'Missing ' + name)
    evidence = result.get('pairing_evidence')
    check(isinstance(evidence, list), 'Missing pairing evidence')
    if key is None:
        check(not evidence and result['alignment'] != 'supported', 'Null reference certified')
    else:
        check(bool(evidence), 'Selected reference lacks literal evidence')
        lv = '\n'.join(m['content'] for m in record['messages'] if m['role'] == 'user')
        for item in evidence:
            for field, source in [('english_quote', candidates[key]['question']), ('latvian_quote', lv)]:
                quote = item.get(field)
                check(isinstance(quote, str) and quote.strip() and quote in source, 'Nonliteral ' + field)
            check(isinstance(item.get('explanation'), str) and item['explanation'].strip(), 'Missing evidence explanation')
    if result['alignment'] == 'supported':
        check(key is not None and all(v == 'pass' for v in checks.values()), 'Unsupported pairing certification')
    if result['keep']:
        check(result['alignment'] == 'supported' and all(result[d] == 'pass' for d in DIMENSIONS), 'Keep contradicts dimensions')


def prepare(root, fused_root):
    root, fused_root = Path(root), Path(fused_root)
    root.mkdir(parents=True, exist_ok=True)
    manifest = load(fused_root / 'manifest.json')
    source = fused_root / 'requests.jsonl'
    check(file_hash(source) == manifest['files']['requests.jsonl'], 'Fused requests changed')
    pins = {str(p): file_hash(p) for p in (source, Path(__file__))}
    pin_path = root / 'input-pins.json'
    if pin_path.exists():
        check(load(pin_path) == pins, 'Protocol inputs/code changed')
    else:
        write_json(pin_path, pins)
    queue = Queue(root / 'review.sqlite')
    inventory = []
    try:
        with (root / 'requests.jsonl').open('w') as out:
            for source_payload in rows(source):
                parent_id = source_payload.pop('job_id')
                payload = source_payload
                payload['schema'] = 'p3-source-fidelity-consumer-v1'
                payload['parent_job_id'] = parent_id
                payload['request']['messages'][0]['content'] += '\n' + PROTOCOL
                key = queue.add(AUDIT_STAGE, payload)
                out.write(json.dumps(dict(job_id=key, **payload), ensure_ascii=False) + '\n')
                inventory.append({'job_id': key, 'parent_job_id': parent_id})
        write_json(root / 'inventory.json', inventory)
        receipt = dict(schema='p3-source-fidelity-consumer-v1', rows=len(inventory), inputs=pins,
                       requests_sha256=file_hash(root / 'requests.jsonl'), calls=0,
                       automatic_admission=False, source_hold_cleared=False)
        write_json(root / 'manifest.json', receipt)
        return receipt
    finally:
        queue.close()


def preflight(root, tokenizer_path, budget=32768):
    # Tokenizer only: no weights, CUDA, endpoint or generation client is loaded.
    from transformers import AutoTokenizer
    root, tokenizer_path = Path(root), Path(tokenizer_path)
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True)
    lengths = []; blocked = []; requests = root / 'requests.jsonl'
    for payload in rows(requests):
        request = payload['request']
        ids = tokenizer.apply_chat_template(request['messages'], tokenize=True,
                    add_generation_prompt=True, enable_thinking=False, return_dict=False)
        total = len(ids) + request['max_tokens']
        lengths.append(dict(job_id=payload['job_id'], input_tokens=len(ids),
                            reserved_output_tokens=request['max_tokens'], total=total))
        if total > budget:
            blocked.append(payload['job_id'])
    with (root / 'native-render-lengths.jsonl').open('w') as out:
        for value in lengths:
            out.write(json.dumps(value) + '\n')
    receipt = dict(schema='p3-native-render-preflight-v1', rows=len(lengths), context_budget=budget,
                   maximum_input_plus_reserved_output_tokens=max((r['total'] for r in lengths), default=0),
                   blocked_job_ids=blocked, requests_sha256=file_hash(requests), truncation=False,
                   lengths_sha256=file_hash(root / 'native-render-lengths.jsonl'), review_calls=0,
                   tokenizer_files={str(tokenizer_path / f): file_hash(tokenizer_path / f)
                                    for f in ('tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja')})
    write_json(root / 'native-render-preflight.json', receipt)
    return receipt


def enqueue_repairs(root, pairing_receipts):
    """External independently reviewed pairing receipts are required; model output is insufficient."""
    root = Path(root)
    receipts = {r['record_sha256']: r for r in rows(pairing_receipts)}
    queue = Queue(root / 'review.sqlite'); count = 0
    try:
        for key, payload, result in list(queue.completed(AUDIT_STAGE)):
            record = payload['record']; pairing = receipts.get(record['record_sha256'])
            if not pairing or result['decision']['keep']:
                continue
            check(pairing.get('independently_verified') is True and pairing.get('reviewer'), 'Unverified external pairing')
            candidate = next((c for c in record['english_candidates'] if c['candidate_id'] == pairing['candidate_id']), None)
            check(candidate is not None and pairing.get('candidate_sha256') == digest(candidate), 'Pairing reference drift')
            check(pairing.get('evidence') and pairing.get('method') != 'ordinal', 'No independent content evidence')
            request = dict(payload['request'], messages=[{'role': 'system', 'content': REPAIR},
                {'role': 'user', 'content': json.dumps(dict(record=record, verified_reference=candidate,
                    pairing_receipt=pairing, review_proposal=result['decision']), ensure_ascii=False)}])
            queue.add(REPAIR_STAGE, dict(record=record, request=request, parent_job_id=key,
                pairing_receipt=pairing, pairing_receipts_sha256=file_hash(pairing_receipts), automatic_admission=False))
            count += 1
        return {'eligible_repair_jobs': count, 'automatic_admission': False}
    finally:
        queue.close()


def validate_repair(result, record):
    check(result.get('status') in ('hold', 'proposed_correction'), 'Bad repair status')
    check(isinstance(result.get('reason'), str) and result['reason'].strip(), 'Missing repair reason')
    if result['status'] == 'hold':
        check(result.get('messages') is None, 'Hold contains replacement')
        return
    validate_messages(result.get('messages'))
    check([m['role'] for m in result['messages']] == [m['role'] for m in record['messages']], 'Repair changed conversation structure')
    check(isinstance(result.get('changes'), list) and result['changes'], 'Missing repair change ledger')
    old = '\n'.join(m['content'] for m in record['messages'])
    new = '\n'.join(m['content'] for m in result['messages'])
    for change in result['changes']:
        check(isinstance(change, dict) and all(isinstance(change.get(k), str) and change[k].strip()
            for k in ('original', 'replacement', 'evidence')), 'Invalid repair ledger entry')
        check(change['original'] in old and change['replacement'] in new, 'Nonliteral repair ledger')


def stage_reaudits(queue):
    """Replayable reconciliation avoids orphaning a repair if its worker crashes after finish."""
    for key, payload, result in list(queue.completed(REPAIR_STAGE)):
        repair = result['decision']
        if repair['status'] != 'proposed_correction':
            continue
        record = dict(payload['record'], messages=repair['messages'],
                      original_messages=payload['record']['messages'],
                      record_sha256=digest(repair['messages']), repaired_from_job=key)
        from .latvian_p3_content_alignment import REVIEW
        request = dict(payload['request'], messages=[{'role': 'system', 'content': REVIEW + '\n' + PROTOCOL},
             {'role': 'user', 'content': json.dumps(record, ensure_ascii=False)}])
        queue.add(REAUDIT_STAGE, dict(record=record, request=request, parent_job_id=key,
                                     automatic_admission=False))


def run(root, endpoint, stage, tokenizer_path, limit=1):
    """Explicit opt-in sequential client. No source admission or registry writes."""
    from transformers import AutoTokenizer
    root = Path(root)
    pins = load(root / 'input-pins.json')
    check(all(file_hash(path) == sha for path, sha in pins.items()), 'Pinned protocol code/inputs changed')
    receipt = load(root / 'native-render-preflight.json')
    check(receipt['requests_sha256'] == file_hash(root / 'requests.jsonl'), 'Stale render receipt')
    check(not receipt['blocked_job_ids'], 'Context-blocked initial requests')
    check(all(file_hash(path) == sha for path, sha in receipt['tokenizer_files'].items()), 'Tokenizer drift')
    check(str(Path(tokenizer_path) / 'tokenizer.json') in receipt['tokenizer_files'], 'Wrong tokenizer')
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True)
    queue = Queue(root / 'review.sqlite'); owner = uuid.uuid4().hex
    (root / 'raw').mkdir(exist_ok=True)
    try:
        stage_reaudits(queue)
        for _ in range(limit):
            job = queue.claim(stage, owner)
            if job is None:
                break
            key, encoded, attempts = job; payload = json.loads(encoded)
            try:
                request = payload['request']
                tokens = tokenizer.apply_chat_template(request['messages'], tokenize=True,
                    add_generation_prompt=True, enable_thinking=False, return_dict=False)
                check(len(tokens) + request['max_tokens'] <= receipt['context_budget'], 'Full context exceeds budget; no truncation')
                headers = {'Content-Type': 'application/json'}
                if os.environ.get('DFM12_API_KEY'):
                    headers['Authorization'] = 'Bearer ' + os.environ['DFM12_API_KEY']
                req = urllib.request.Request(endpoint.rstrip('/') + '/chat/completions',
                    json.dumps(request).encode(), headers)
                with urllib.request.urlopen(req, timeout=300) as handle:
                    raw = json.load(handle)
                write_json(root / 'raw' / f'{key}-{attempts + 1}.json', raw)
                choice = raw['choices'][0]
                check(choice.get('finish_reason') == 'stop', 'Incomplete generation')
                result = response_json(choice['message']['content'])
                if stage == REPAIR_STAGE:
                    validate_repair(result, payload['record'])
                else:
                    validate_review(result, payload['record'])
                queue.finish(key, owner, attempts + 1, result=dict(decision=result,
                    pairing_certified=False, automatic_admission=False, request_sha256=digest(request)))
                stage_reaudits(queue)
            except Exception as exc:
                queue.finish(key, owner, attempts + 1, error=f'{type(exc).__name__}: {exc}'[:4000])
                time.sleep(min(30, 2 ** attempts))
        return queue.status()
    finally:
        queue.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__); sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('prepare'); a.add_argument('--root', required=True); a.add_argument('--fused-root', required=True)
    a = sub.add_parser('preflight'); a.add_argument('--root', required=True); a.add_argument('--tokenizer', required=True)
    a = sub.add_parser('enqueue-repairs'); a.add_argument('--root', required=True); a.add_argument('--pairing-receipts', required=True)
    a = sub.add_parser('run'); a.add_argument('--root', required=True); a.add_argument('--endpoint', required=True)
    a.add_argument('--tokenizer', required=True); a.add_argument('--limit', type=int, default=1)
    a.add_argument('--stage', choices=[AUDIT_STAGE, REPAIR_STAGE, REAUDIT_STAGE], default=AUDIT_STAGE)
    args = p.parse_args()
    if args.command == 'prepare': result = prepare(args.root, args.fused_root)
    elif args.command == 'preflight': result = preflight(args.root, args.tokenizer)
    elif args.command == 'enqueue-repairs': result = enqueue_repairs(args.root, args.pairing_receipts)
    else: result = run(args.root, args.endpoint, args.stage, args.tokenizer, args.limit)
    print(json.dumps(result, indent=2))
