"""CPU-only heldout exclusion and exact reviewer-request preflight; no GPU client."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Mapping
from concurrent.futures import ProcessPoolExecutor
import importlib
import json
import multiprocessing
import os
from pathlib import Path

from scripts.prepare_dfm13_pending_arena import ROOT, DOWNLOADS, HUB, digest, json_write, records, sha256

REVISION = 'f6d145777bcbde96137596340fab89793acd1031'
SUBSETS = ('preference', 'edit', 'feedback', 'edit_quality', 'principle')
ANSWER_FIELDS = ('response1', 'response2', 'original_response', 'edited_response',
                 'good_edited_response', 'bad_edited_response', 'response')
CONTEXT_LIMIT = 32768
REQUEST_MODULE = 'scripts.dfm13_arena_bulk_reasonfirst'
TOKENIZER_DIR = Path('/work/mimir/.home/.cache/huggingface/hub/models--google--gemma-4-26B-A4B-it/snapshots/4d7ae4984b7db7de8f8457170b3f1a419ee76d52')
DEPENDENCIES = [
    'scripts/screen_dfm13_pending_arena.py', 'scripts/prepare_dfm13_pending_arena.py',
    'scripts/dfm13_arena_bulk_reasonfirst.py', 'scripts/dfm13_arena_bulk_recovery.py',
    'scripts/dfm13_arena_bulk_audit.py', 'scripts/dfm13_arena_reasonfirst_probe.py',
    'scripts/dfm13_arena_semantic_v1.py', 'scripts/dfm13_arena_reviewer_v4_schema.py',
    'scripts/dfm13_arena_reviewer_v4.py', 'scripts/dfm13_arena_audit.py',
    'dfm12/io.py', 'dfm12/multilingual_calibration_v6.py', 'dfm12/multilingual_diagnose.py',
]


def verify_pins(pins):
    for path, expected in pins.items():
        if sha256(Path(path)) != expected:
            raise ValueError('Pinned file changed: '+path)


def validation_inventory(download=False):
    result = []
    for subset in SUBSETS:
        relative = subset+'/validation.jsonl.gz'
        path = DOWNLOADS/'HelpSteer3'/relative
        if download:
            from huggingface_hub import hf_hub_download
            hf_hub_download('nvidia/HelpSteer3', relative, repo_type='dataset', revision=REVISION,
                            local_dir=DOWNLOADS/'HelpSteer3')
        receipt = DOWNLOADS/'HelpSteer3/.cache/huggingface/download'/(relative+'.metadata')
        revision, etag, *_ = receipt.read_text().splitlines()
        if revision != REVISION or sha256(path) != etag:
            raise ValueError('Validation revision/content mismatch: '+relative)
        result.append(dict(subset=subset, path=str(path.resolve()), sha256=etag,
            repo_id='nvidia/HelpSteer3', revision=revision, file=relative, split='validation',
            receipt_path=str(receipt), receipt_sha256=sha256(receipt)))
    return result


def heldout_index(inventory):
    contexts, pairs, rows = defaultdict(list), defaultdict(list), []
    for source in inventory:
        count = 0
        for line, row in enumerate(records(Path(source['path'])), 1):
            count += 1
            context = row['context']
            if not isinstance(context, list) or not context:
                raise ValueError('Malformed validation context')
            canonical = []
            for m in context:
                if (not isinstance(m, dict) or m.get('role') not in ('system', 'user', 'assistant')
                        or not isinstance(m.get('content'), str) or m.get('tool_calls')):
                    raise ValueError('Unsupported validation message; no silent omission')
                canonical.append(dict(role=m['role'], content=m['content']))
            if canonical[-1]['role'] != 'user':
                raise ValueError('Validation context must end with a user message')
            identity = dict(repo_id=source['repo_id'], revision=source['revision'], file=source['file'],
                split='validation', line=line, raw_row_sha256=digest(row),
                source_id=f"{source['repo_id']}@{source['revision']}:{source['file']}:{line}",
                source_id_kind='derived_pinned_file_and_one_based_line; no upstream row ID published')
            key = digest(canonical)
            contexts[key].append(identity)
            answers = []
            for field in ANSWER_FIELDS:
                if field in row:
                    if not isinstance(row[field], str):
                        raise ValueError('Nontext heldout answer')
                    if row[field].strip():
                        answer_key = digest([canonical[-1], dict(role='assistant', content=row[field])])
                        pairs[answer_key].append(dict(identity, response_field=field))
                        answers.append(dict(field=field, pair_sha256=answer_key))
            if not any(field in row for field in ANSWER_FIELDS):
                raise ValueError('Unknown validation response schema')
            rows.append(dict(identity, context_sha256=key, answer_pair_hashes=answers))
        source['rows'] = count
    return contexts, pairs, rows


def overlap_hits(row, contexts, pairs):
    messages = row['messages']
    hits = []
    for i, message in enumerate(messages):
        if message['role'] != 'assistant':
            continue
        context_hash = digest(messages[:i])
        if context_hash in contexts:
            hits.append(dict(kind='exact_full_context', assistant_message_index=i,
                             hash=context_hash, matches=contexts[context_hash]))
        if i and messages[i-1]['role'] == 'user':
            pair_hash = digest(messages[i-1:i+1])
            if pair_hash in pairs:
                hits.append(dict(kind='exact_user_answer_pair', assistant_message_index=i,
                                 hash=pair_hash, matches=pairs[pair_hash]))
    return hits


def flat_ids(encoded):
    ids = encoded['input_ids'] if isinstance(encoded, Mapping) else encoded
    if not isinstance(ids, list) or any(type(x) is not int for x in ids):
        raise ValueError('Expected flat actual token IDs')
    return ids


def worker_init(tokenizer_dir, pins):
    global REVIEWER, TOKENIZER
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    os.environ['OMP_NUM_THREADS'] = '1'
    verify_pins(pins)
    REVIEWER = importlib.import_module(REQUEST_MODULE)
    TOKENIZER = REVIEWER.bulk.engine.tokenizer(tokenizer_dir)


def measure(row):
    payload = REVIEWER.request(row)
    if payload['max_tokens'] != 8192 or payload['chat_template_kwargs'] != {'enable_thinking': True}:
        raise ValueError('Unexpected current reviewer contract')
    ids = flat_ids(TOKENIZER.apply_chat_template(payload['messages'], tokenize=True,
        add_generation_prompt=True, **payload['chat_template_kwargs']))
    return dict(id=row['id'], request_sha256=digest(payload), prompt_tokens=len(ids),
        token_ids_sha256=digest(ids), max_tokens=payload['max_tokens'], context_limit=CONTEXT_LIMIT,
        eligible=len(ids)+payload['max_tokens'] <= CONTEXT_LIMIT,
        thinking=True, truncation=False)


def eligible_for_audit(component, hits, budget=None):
    if component == 'prism':
        return False, 'license_pending_noncommercial'
    if hits:
        return False, 'heldout_overlap'
    if budget is None or not budget['eligible']:
        return False, 'full_context_overflow'
    return True, None


def prepare(source_root, output, workers=16, download=False):
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError('CPU workers must be 1..16')
    source_root, output = source_root.resolve(), output.resolve()
    if output.exists():
        raise ValueError('Fresh output root required')
    old = json.loads((source_root/'manifest.json').read_text())
    if sha256(source_root/'manifest.json') != json.loads((source_root/'seal.json').read_text())['manifest_sha256']:
        raise ValueError('Input inventory seal mismatch')
    verify_pins(old['pins'])
    pins = {str(ROOT/p):sha256(ROOT/p) for p in DEPENDENCIES}
    pins[str(source_root/'manifest.json')] = sha256(source_root/'manifest.json')
    for name in ('tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja'):
        pins[str(TOKENIZER_DIR/name)] = sha256(TOKENIZER_DIR/name)
    inventory = validation_inventory(download)
    contexts, pairs, heldout_rows = heldout_index(inventory)
    output.mkdir(parents=True)
    for entry in inventory:
        pins[entry['path']] = entry['sha256']
        pins[entry['receipt_path']] = entry['receipt_sha256']
    with (output/'validation-index.jsonl').open('x') as stream:
        for row in heldout_rows:
            stream.write(json.dumps(row, ensure_ascii=False)+'\n')
    json_write(output/'preparation.json', dict(status='cpu_only_preparing', pid=os.getpid(), workers=workers,
        request_factory=REQUEST_MODULE+'.request', context_limit=CONTEXT_LIMIT, max_tokens=8192,
        validation_sources=inventory, no_gpu=True, no_admission=True))
    sources, summaries = [], []
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'),
                             initializer=worker_init, initargs=(str(TOKENIZER_DIR), pins)) as pool:
        for source in old['sources']:
            name = source['name']
            path = Path(source['path'])
            if sha256(path) != source['sha256'] or sha256(Path(source['manifest_path'])) != source['manifest_sha256']:
                raise ValueError('Input component drift')
            pins[str(path)] = source['sha256']
            pins[source['manifest_path']] = source['manifest_sha256']
            directory = output/name
            directory.mkdir()
            counts, pending = Counter(), []
            with (directory/'candidates.jsonl').open('x') as eligible, \
                 (directory/'excluded.jsonl').open('x') as excluded, \
                 (directory/'preflight.jsonl').open('x') as preflight:
                def flush():
                    for (raw, row), budget in zip(pending, pool.map(measure, [r for _,r in pending], chunksize=8)):
                        preflight.write(json.dumps(budget)+'\n')
                        counts['preflight_measured'] += 1
                        counts['max_prompt_tokens'] = max(counts['max_prompt_tokens'], budget['prompt_tokens'])
                        allowed, reason = eligible_for_audit(name, [], budget)
                        if allowed:
                            eligible.write(raw)
                            counts['audit_eligible'] += 1
                        else:
                            counts[reason] += 1
                            excluded.write(json.dumps(dict(id=row['id'], source_id=row['metadata']['source_id'],
                                reason=reason, row_sha256=digest(row), budget=budget))+'\n')
                    pending.clear()
                with path.open() as stream:
                    for raw in stream:
                        row = json.loads(raw)
                        counts['input_rows'] += 1
                        if name == 'prism':
                            counts['license_pending_noncommercial'] += 1
                            excluded.write(json.dumps(dict(id=row['id'], reason='license_pending_noncommercial',
                                row_sha256=digest(row), source_id=row['metadata']['source_id']))+'\n')
                            continue
                        hits = overlap_hits(row, contexts, pairs)
                        if hits:
                            counts['heldout_overlap'] += 1
                            excluded.write(json.dumps(dict(id=row['id'], reason='heldout_overlap',
                                row_sha256=digest(row), source_id=row['metadata']['source_id'], hits=hits))+'\n')
                            continue
                        pending.append((raw, row))
                        if len(pending) >= 256:
                            flush()
                flush()
            if counts['input_rows'] != source['rows']:
                raise ValueError('Input row count mismatch')
            accounted = sum(counts[k] for k in ('audit_eligible','heldout_overlap','full_context_overflow','license_pending_noncommercial'))
            if accounted != counts['input_rows']:
                raise ValueError('Incomplete disposition accounting')
            component_manifest = dict(version=1, name=name, counts=dict(counts), input=source,
                no_admission=True, no_upload=True, audit_eligible_only=True,
                output_sha256=sha256(directory/'candidates.jsonl'),
                preflight_sha256=sha256(directory/'preflight.jsonl'), exclusions_sha256=sha256(directory/'excluded.jsonl'))
            json_write(directory/'manifest.json', component_manifest)
            if counts['audit_eligible']:
                sources.append(dict(name=name, path=str(directory/'candidates.jsonl'), rows=counts['audit_eligible'],
                    sha256=component_manifest['output_sha256'], manifest_path=str(directory/'manifest.json'),
                    manifest_sha256=sha256(directory/'manifest.json'),
                    preflight_path=str(directory/'preflight.jsonl'), preflight_sha256=component_manifest['preflight_sha256']))
            summaries.append(dict(component=name, counts=dict(counts)))
            print(name, json.dumps(dict(counts)), flush=True)
    verify_pins(pins)
    manifest = dict(version='dfm13-pending-screened-audit-v1', status='cpu_preflight_passed',
        sources=sources, total=sum(s['rows'] for s in sources), components=summaries,
        validation_sources=inventory, validation_index_sha256=sha256(output/'validation-index.jsonl'),
        pins=pins, tokenizer_dir=str(TOKENIZER_DIR), context_limit=CONTEXT_LIMIT,
        request_factory=REQUEST_MODULE+'.request', max_tokens=8192, thinking=True,
        no_admission=True, no_upload=True, no_gpu=True, cpu_workers=workers,
        heldout_scope='All five pinned HelpSteer3 validation configs; exact complete context and exact adjacent user/answer pair, including earlier context assistant turns; no fuzzy or answer-only matching.',
        prism='Fully held; not included in audit sources or context preflight.',
        expert_policy='Upstream train split; no registered Expert5K evaluation found in inspected local DFM configs/tasks. No blanket benchmark-clean claim; retain general benchmark-overlap gap.',
        unresolved=['Exhaustive inherited corpus overlap not performed', 'Other benchmark prompt/text overlaps untested',
                    'Source/provider licensing and absolute quality remain admission gates',
                    'Existing live bulk preparation hardcodes 205242; needs separately owned inventory integration'],
        rows_unchanged=True, original_outputs_immutable=True)
    json_write(output/'manifest.json', manifest)
    json_write(output/'seal.json', dict(manifest_sha256=sha256(output/'manifest.json')))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=ROOT/'data/dfm13/pending-arena-candidates-20261001')
    parser.add_argument('--output', type=Path, default=ROOT/'data/dfm13/pending-arena-screened-20261001')
    parser.add_argument('--workers', type=int, default=16)
    parser.add_argument('--download-validation', action='store_true')
    args = parser.parse_args()
    result = prepare(args.source_root, args.output, args.workers, args.download_validation)
    print(json.dumps(dict(root=str(args.output), total=result['total'])))


if __name__ == '__main__':
    main()
