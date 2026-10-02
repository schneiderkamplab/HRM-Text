"""CPU-only Search training contract/inventory. No accepted exports or admission."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sqlite3

import jinja2
from tokenizers import Tokenizer

from scripts import dfm13_search_calibration as base
from scripts import tokenize_chat_template as training
from scripts import dfm13_search_cached_repairs as repair

LEDGER = Path('data/dfm13/search-source-checked-drafts-20261001-v2/campaign-ledger.json')
METADATA = Path('data/sampled_dfm11/metadata.json')
ROOT = Path('data/dfm13/search-training-contract-20261001')
MANUAL_RECEIPT = Path('docs/reports/dfm13_search_heldout8_receipt_20261001.json')


def strict_row(row, original_prompt):
    row = deepcopy(row)
    if row.get('tools') != base.TOOLS:
        raise ValueError('tool schema differs from pinned native search/open_page contract')
    messages = row.get('messages')
    if not isinstance(messages, list) or not messages:
        raise ValueError('missing messages')
    users = [m.get('content') for m in messages if m.get('role') == 'user']
    if not users or users[0] != original_prompt:
        raise ValueError('original user prompt changed or generation steering leaked')
    targets = row.get('target_message_indices')
    if (not isinstance(targets, list) or not targets or any(type(i) is not int for i in targets)
            or targets != sorted(set(targets))):
        raise ValueError('explicit unique integer target indices required')
    pending = {}; seen = set(); calls = {}
    for index, message in enumerate(messages):
        role = message.get('role')
        if role not in ('system', 'user', 'assistant', 'tool'):
            raise ValueError('unknown role')
        if not isinstance(message.get('content', ''), str):
            raise ValueError('nontext content requires separate multimodal contract')
        if pending and role != 'tool':
            raise ValueError('unresolved native tool call before next turn')
        if role == 'tool':
            call_id = message.get('tool_call_id')
            if call_id not in pending:
                raise ValueError('orphan or repeated tool response')
            name, args = pending.pop(call_id)
            if message.get('name') not in (None, name):
                raise ValueError('tool response name mismatch')
            base.strict_json(message['content'])
            calls[index] = dict(name=name, arguments=args)
        native = message.get('tool_calls')
        if native:
            if role != 'assistant' or not isinstance(native, list) or len(native) != 1:
                raise ValueError('only recorded single native assistant calls supported')
            call = native[0]
            if set(call) != {'id', 'type', 'function'} or call['type'] != 'function':
                raise ValueError('invalid native function envelope')
            if not isinstance(call['id'], str) or not call['id'] or call['id'] in seen:
                raise ValueError('invalid or reused call ID')
            function = call['function']
            if not isinstance(function, dict) or set(function) != {'name', 'arguments'}:
                raise ValueError('invalid function')
            name = function['name']; args = function['arguments']
            if isinstance(args, str):
                args = base.strict_json(args)
            key = {'search': 'query', 'open_page': 'url'}.get(name)
            if not key or not isinstance(args, dict) or set(args) != {key} or not isinstance(args[key], str) or not args[key].strip():
                raise ValueError('arguments fail exact native schema')
            if name == 'open_page':
                base.public_url(args[key])
            function['arguments'] = args
            pending[call['id']] = name, args
            seen.add(call['id'])
    if pending:
        raise ValueError('incomplete tool cycle')
    for index in targets:
        if not 0 <= index < len(messages) or messages[index]['role'] != 'assistant':
            raise ValueError('target must be an assistant message')
        if not messages[index].get('tool_calls') and not messages[index].get('content', '').strip():
            raise ValueError('empty assistant target')
    if messages[-1]['role'] != 'assistant' or messages[-1].get('tool_calls'):
        raise ValueError('no completed final answer')
    return row, calls


def fingerprint(row):
    messages = deepcopy(row['messages']); ids = {}
    for message in messages:
        for call in message.get('tool_calls', []):
            ids[call['id']] = 'call_' + str(len(ids))
            call['id'] = ids[call['id']]
        if message.get('tool_call_id') in ids:
            message['tool_call_id'] = ids[message['tool_call_id']]
    return base.digest(dict(messages=messages, tools=row['tools'], targets=row['target_message_indices']))


def student_views(row):
    # Singular selector is the actual tokenizer API; metadata never enters the student row.
    for index in row['target_message_indices']:
        yield dict(messages=deepcopy(row['messages']), tools=deepcopy(row['tools']), target_message_index=index)


def require_admission(row, receipt, actual_sha256, holds):
    content_hash = base.digest(row)
    if any(h.get('candidate_sha256') == actual_sha256 or h.get('candidate_content_sha256') == content_hash for h in holds):
        raise ValueError('independent candidate-hash hold overrides all automated keeps')
    if (receipt.get('admission_authorized') is not True or receipt.get('candidate_sha256') != actual_sha256
            or receipt.get('independent_review_complete') is not True or receipt.get('decision') != 'admit'
            or receipt.get('provenance_verified') is not True or receipt.get('student_mask_verified') is not True
            or receipt.get('approved_target_message_indices') != row['target_message_indices']
            or receipt.get('unresolved_findings') != [] or receipt.get('independent_hold')):
        raise ValueError('pending or mismatched quality/provenance/mask receipt; export forbidden')


def rendered_targets(row, tokenizer, template, info, limit):
    result = []
    for view in student_views(row):
        examples = list(training.examples_from_messages(view['messages'], view['tools'], view['target_message_index']))
        if len(examples) != 1:
            raise ValueError('singular target selection did not produce one example')
        encoded = training.tokenize_example(tokenizer, template, examples[0], info['enable_thinking'])
        if encoded is None:
            raise ValueError('student template token-prefix mismatch')
        prompt, target = encoded
        # V1Dataset uses prompt[:-1] labels=-100, then the unshifted response IDs.
        labels = [-100] * len(prompt) + target
        assert labels[1:] == [-100] * (len(prompt) - 1) + target
        result.append(dict(target_message_index=view['target_message_index'], prompt_tokens=len(prompt),
            target_tokens=len(target), total_tokens=len(prompt) + len(target),
            fits_student_context=len(prompt) + len(target) <= limit,
            masked_prompt_tokens=len(prompt), shifted_masked_tokens=len(prompt) - 1,
            target_kind='native_tool_call' if row['messages'][view['target_message_index']].get('tool_calls') else 'final_answer'))
    return result


def evidence_check(row, calls, cached):
    matches = []; failures = []; body_pages = 0
    for index, call in calls.items():
        observed = base.strict_json(row['messages'][index]['content'])
        expected_hash = observed.get('raw_cache_sha256') or observed.get('cache_sha256') or observed.get('provenance', {}).get('response_sha256')
        candidates = [c for c in cached if (not expected_hash or c['sha256'] == expected_hash)
                      and (call['name'] != 'search' or c['query'] == call['arguments']['query'])]
        if not expected_hash or len(candidates) != 1:
            failures.append(dict(message_index=index, reason='missing or ambiguous same-owner raw-cache binding'))
            continue
        cache = candidates[0]
        source = {p['url']: p for p in cache['payload'].get('data', []) if p.get('url')}
        for page in observed.get('results', []):
            body = page.get('body', page.get('content', ''))
            if not isinstance(body, str) or not body.strip():
                continue
            url = page.get('url'); full = source.get(url, {}).get('content', '')
            good = bool(full)
            excerpts = page.get('excerpts', [])
            if excerpts:
                remainder = body
                for excerpt in excerpts:
                    start, end, text = excerpt.get('start'), excerpt.get('end'), excerpt.get('text')
                    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(full) or full[start:end] != text:
                        good = False; break
                    if text not in remainder:
                        good = False; break
                    remainder = remainder.replace(text, '', 1)
                if not re.fullmatch(r'(?:\s|\[Cached passage \d+:\d+\]|\[Technical context \d+:\d+\])*', remainder):
                    good = False
            elif body not in full:
                good = False
            if good:
                body_pages += 1
                matches.append(dict(message_index=index, url=url, cache_sha256=cache['sha256']))
            else:
                failures.append(dict(message_index=index, url=url, reason='delivered body not exact cached content/excerpts'))
    return dict(verified_page_observations=body_pages, matches=matches, failures=failures,
                complete=body_pages > 0 and not failures,
                source_factual_quality='not established by byte identity')


def choose_candidate(entry):
    if entry.get('source_checked_draft'):
        return Path(entry['source_checked_draft']), 'source_checked_draft'
    if isinstance(entry.get('selected'), dict) and entry['selected'].get('candidate'):
        return Path(entry['selected']['candidate']), 'earlier_automated_keep_not_admitted'
    paths = []
    for item in entry['history']:
        path = Path(item['candidate']) if item.get('candidate') else Path(item['outcome']).parent / 'candidate.json'
        if path.exists():
            paths.append(path)
    return (paths[-1], 'latest_available_not_quality_selected') if paths else (None, 'no_saved_candidate')


def manual_holds():
    receipt = repair.read(MANUAL_RECEIPT)
    queue_path = Path(receipt['queue'])
    if base.file_hash(queue_path) != receipt['queue_sha256']:
        raise ValueError('manual assessment queue hash mismatch')
    queue = repair.read(queue_path)
    for path, expected in queue['pins'].items():
        if base.file_hash(Path(path)) != expected:
            raise ValueError('manual packet source pin mismatch')
    holds = []
    for finding in receipt['cases']:
        matching = [r for r in queue['cases'] if r['id'].startswith(finding['id_prefix'])]
        if len(matching) != 1:
            raise ValueError('ambiguous manual assessment identity')
        packet_path = Path(matching[0]['packet']); packet = repair.read(packet_path)
        holds.append(dict(id=packet['id'], candidate_content_sha256=base.digest(packet['candidate']),
            candidate_sha256=packet['source_sha256'] if Path(packet['source_candidate']).name == 'candidate.json' else None,
            packet_sha256=base.file_hash(packet_path), assessment_sha256=base.file_hash(MANUAL_RECEIPT),
            finding=finding['finding'], correction=finding['correction'], admission_authorized=False))
    return holds


def prepare(root):
    if root.exists():
        raise ValueError('new isolated contract root required')
    ledger = repair.read(LEDGER)
    holds = manual_holds()
    metadata = repair.read(METADATA); info = metadata['tokenizer_info']
    if info['template_mode'] != 'jinja_chat_template' or info['enable_thinking'] is not False:
        raise ValueError('unexpected student template semantics')
    tokenizer = Tokenizer.from_file(info['tokenizer_path'])
    template = jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
    limit = metadata['max_seq_len'] - 1
    samples = {s['id']: s for s in repair.read(Path('data/dfm13/search-calibration-100-20261001-v9-cited/samples.json'))}
    db = sqlite3.connect('file:' + str(base.CAMPAIGN / 'cache.sqlite') + '?mode=ro', uri=True)
    cache = {}
    for owner, query, raw in db.execute('SELECT owner,query,raw FROM searches WHERE status="done"'):
        cache.setdefault(owner, []).append(dict(query=query, payload=json.loads(raw), sha256=hashlib.sha256(raw).hexdigest()))
    paid = dict(db.execute('SELECT status,count(*) FROM searches GROUP BY status')); db.close()
    pins = {str(p.resolve()): base.file_hash(p) for p in (Path(__file__), Path(training.__file__),
        Path(base.__file__), Path(repair.__file__), Path('dataset_new.py'), LEDGER, METADATA,
        MANUAL_RECEIPT, Path(info['tokenizer_path']), Path(info['chat_template_path']))}
    rows = []; fingerprints = {}; target_counts = Counter()
    for entry in ledger['rows']:
        key = entry['id']; path, lineage = choose_candidate(entry)
        result = dict(id=key, candidate=str(path) if path else None, lineage=lineage,
            quality_disposition=entry['disposition'], quality_admission=False,
            source_cache_available=key in cache, semantic_target_status='pending individual task-completion review')
        if path is None:
            result['contract_status'] = 'no_candidate'; rows.append(result); continue
        pins[str(path.resolve())] = base.file_hash(path)
        result['candidate_sha256'] = base.file_hash(path)
        original = repair.read(path)
        result['candidate_content_sha256'] = base.digest(original)
        if entry.get('independent_hold') or entry.get('independent_repair_findings'):
            holds.append(dict(id=key, candidate_sha256=base.file_hash(path), candidate_content_sha256=base.digest(original),
                finding=entry.get('independent_hold') or entry['independent_repair_findings'],
                applies_to='selected exact candidate snapshot; independent clearance required for new revisions', admission_authorized=False))
        result['exact_hash_hold'] = any(h.get('candidate_sha256') == result['candidate_sha256'] or
            h['candidate_content_sha256'] == result['candidate_content_sha256'] for h in holds)
        parent_repair = path.parent / 'repair.json'
        if parent_repair.exists():
            value = repair.read(parent_repair)
            result['generator_evidence_sufficient'] = value.get('evidence_sufficient')
            result['generator_limitation'] = value.get('reason')
            pins[str(parent_repair.resolve())] = base.file_hash(parent_repair)
        try:
            row, calls = strict_row(original, samples[key]['prompt'])
            fp = fingerprint(row)
            result['fingerprint'] = fp
            result['duplicate_of'] = fingerprints.get(fp)
            fingerprints.setdefault(fp, key)
            result['evidence'] = evidence_check(row, calls, cache.get(key, []))
            result['targets'] = rendered_targets(row, tokenizer, template, info, limit)
            for target in result['targets']:
                target_counts[target['target_kind']] += 1
                if target['fits_student_context']:
                    target_counts[target['target_kind'] + '_fits'] += 1
            result['contract_status'] = 'structurally_valid'
            result['all_targets_fit'] = all(t['fits_student_context'] for t in result['targets'])
            result['controller_system_present'] = any(m['role'] == 'system' for m in row['messages'])
            result['system_prompt_policy'] = 'preserved, requires review; do not silently drop date/control context'
            result['answer_preview'] = row['messages'][-1]['content'][:800]
        except Exception as error:
            result['contract_status'] = 'blocked'
            result['blocker'] = str(error)
        rows.append(result)
    summary = dict(total=100, candidate_rows=sum(r['candidate'] is not None for r in rows),
        cached_owners=len(cache), paid_reservations=sum(paid.values()),
        statuses=dict(Counter(r['contract_status'] for r in rows)), target_counts=dict(target_counts),
        provenance_complete=sum(r.get('evidence', {}).get('complete', False) for r in rows),
        all_targets_fit=sum(r.get('all_targets_fit', False) for r in rows),
        explicit_generator_evidence_insufficient=sum(r.get('generator_evidence_sufficient') is False for r in rows),
        exact_duplicate_rows=sum(r.get('duplicate_of') is not None for r in rows),
        meaningful_retrieval_target_count='not certified; byte checks and keeps do not establish task completion',
        export_admitted_rows=0, training_files_written=0, student_context=limit,
        admission_authorized=False, upload_authorized=False)
    base.atomic(root / 'inventory.json', dict(summary=summary, rows=rows))
    base.atomic(root / 'holds.json', dict(holds=holds, manual_receipt=str(MANUAL_RECEIPT),
        manual_receipt_sha256=base.file_hash(MANUAL_RECEIPT), admission_authorized=False))
    base.atomic(root / 'contract.json', dict(pins=pins, student_tokenizer_info=info, max_tokens=limit,
        student_columns=['messages', 'tools', 'target_message_index'],
        required_receipt_fields=['candidate_sha256', 'admission_authorized', 'independent_review_complete',
            'decision', 'provenance_verified', 'student_mask_verified', 'approved_target_message_indices', 'unresolved_findings'],
        plural_target_indices_not_supported_by_generic_reader=True, no_truncation=True,
        metadata_outside_student_data=True, accepted_export_implemented=False, admission_authorized=False))
    print(json.dumps(summary))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    prepare(parser.parse_args().root)
