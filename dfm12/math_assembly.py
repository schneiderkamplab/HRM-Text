"""Verify the existing worked-MATH local contract without retokenizing it."""
from pathlib import Path

import numpy as np

NAME = 'hendrycks_math_worked'
REPO = 'EleutherAI/hendrycks_math'
REVISION = '21a5633873b6a120296cce3e2df9d5550074f4a3'
MANIFEST_SHA = 'b26a5dbfdc4bbae88f14e8ca6036da7d6d43a77a6896c6c5d37712d8f187723e'
RECEIPT_SHA = '032e4f097a38a966d96149d0e6c5fe87ae286d42cd4ba623e4f8e61e5d5c9682'
ROWS, TOKENS = 7496, 2431145
PART = 'dfm13_math_worked__train.jsonl'


def unready_reason(entry):
    if type(entry.get('repeat')) is not int or entry['repeat'] != 5:
        return 'worked_math_requires_explicit_repeat_5'
    if not entry.get('tokenized_output') or not entry.get('tokenization_receipt'):
        return 'worked_math_tokenization_not_ready'
    return None


def verify(entry, contract, pins, api=None):
    if api is None:
        from scripts import assemble_dfm13_additions as api
    require = api.require
    require(entry.get('name') == NAME and unready_reason(entry) is None, 'Wrong MATH scope/repeat')
    require((entry.get('repo_id'), entry.get('revision'), entry.get('split'), entry.get('license')) ==
            (REPO, REVISION, 'train', 'mit'), 'Wrong MATH source/split/license')
    require(entry.get('target_policy') == 'worked_solution_single_assistant_target', 'Wrong MATH target policy')
    require(entry.get('hard_truncation') is False and entry.get('rows') == ROWS
            and entry.get('tokens') == TOKENS, 'MATH count/truncation mismatch')
    require(entry.get('manifest_sha256') == MANIFEST_SHA and
            entry.get('tokenization_receipt_sha256') == RECEIPT_SHA, 'MATH receipt pins changed')
    manifest = api.read_json(entry['manifest'], pins, MANIFEST_SHA)
    receipt = api.read_json(entry['tokenization_receipt'], pins, RECEIPT_SHA)
    require(manifest.get('schema') == 'dfm13-math-worked-v1' and manifest.get('name') == NAME,
            'Wrong MATH conversion schema')
    for key in ('repo_id', 'revision', 'license', 'rows', 'hard_truncation'):
        require(manifest[key] == entry[key], 'MATH conversion mismatch: ' + key)
    require(manifest['test_rows_in_output'] == 0 and manifest['hard_truncation'] is False,
            'MATH test/truncation policy changed')
    require(receipt['converted_manifest_sha256'] == MANIFEST_SHA and
            receipt['hard_truncation'] is False and receipt['regex_fix'] is False,
            'MATH tokenization conversion/regex mismatch')
    source = api.pin(entry['output'], pins, entry['output_sha256'])
    require(entry['output_sha256'] == manifest['train_sha256'], 'MATH converted payload mismatch')
    api.pin(Path(entry['manifest']).parent / 'screening.jsonl', pins, manifest['screening_sha256'])
    evidence = manifest['license_evidence']
    api.pin(evidence['path'], pins, evidence['sha256'])
    source_files = {}
    for item in manifest['source_files']:
        api.pin(item['path'], pins, item['sha256'])
        key = (item['config'], item['split'])
        require(key not in source_files, 'Duplicate MATH source partition')
        source_files[key] = item
    require(set(source_files) == {(c, s) for c in entry['configs'] for s in ('train', 'test')},
            'MATH source configuration coverage changed')
    from dfm12.io import rows
    seen = set()
    for row in rows(source):
        metadata = row['metadata']
        require(row['id'] not in seen, 'Duplicate MATH row ID')
        seen.add(row['id'])
        require(len(row['messages']) == 2 and [m['role'] for m in row['messages']] == ['user', 'assistant']
                and row.get('target_message_index') == 1 and not row.get('tools')
                and all(isinstance(m.get('content'), str) and m['content'].strip() for m in row['messages'])
                and row.get('chat_template_kwargs') == {'enable_thinking': False}, 'Wrong MATH conversation')
        require((metadata['source'], metadata['revision'], metadata['split']) == (REPO, REVISION, 'train'),
                'MATH row source/test leakage')
        item = source_files[(metadata['config'], 'train')]
        require(metadata['source_file_sha256'] == item['sha256'] and
                metadata['source_file'] == metadata['config'] + '/' + Path(item['path']).name and
                type(metadata['source_row_index']) is int and
                0 <= metadata['source_row_index'] < item['rows'], 'MATH source ordinal/hash mismatch')
    require(len(seen) == ROWS, 'MATH source population mismatch')
    root = Path(entry['tokenized_output']).resolve(strict=True)
    require(Path(receipt['output']).resolve() == root, 'MATH token output mismatch')
    for path, sha in receipt['files'].items():
        require(Path(path).resolve().is_relative_to(root), 'MATH token file escapes root')
        api.pin(path, pins, sha)
    require({str(p.resolve()) for p in root.rglob('*') if p.is_file()} ==
            {str(Path(p).resolve()) for p in receipt['files']}, 'MATH token file inventory changed')
    info = api.read_json(root / 'tokenizer_info.json', pins)
    require(api.token_contract(info, pins) == contract, 'MATH tokenizer/template differs from base')
    for key, suffix in (('tokenizer_path', 'tokenizer_path_sha256'),
                        ('chat_template_path', 'chat_template_path_sha256')):
        path = Path(info[key]); path = path if path.is_absolute() else api.REPO / path
        require(manifest['pins'][str(path.resolve())] == contract[suffix], 'MATH historical tokenizer pin changed')
    completion = api.read_json(root / 'completion.json', pins)
    require(completion['rows'] == ROWS and completion['files'] == 1 and
            completion['skipped_rows_this_run'] == 0 and completion['max_seq_len'] is None,
            'MATH completion/drop/truncation mismatch')
    require([p.name for p in root.iterdir() if p.is_dir()] == [PART], 'Unexpected MATH shard layout')
    part = api.verify_arrays(root / PART, contract['vocab_size'], pins)
    require(part['rows'] == receipt['rows'] == ROWS and part['tokens'] == receipt['tokens'] == TOKENS,
            'MATH materialized counts differ')
    prompt = np.load(root / PART / 'inst_len.npy', mmap_mode='r')
    response = np.load(root / PART / 'resp_len.npy', mmap_mode='r')
    require(int(prompt.sum()) == receipt['prompt_tokens'] and int(response.sum()) == receipt['target_tokens']
            and int((prompt.astype(np.int64) + response).max()) == receipt['max_sequence_tokens']
            and receipt['sequences_over_4096'] == 0, 'MATH token statistics mismatch')
    part.update(path=str(root / PART), link_name=NAME + '__' + PART)
    parity = api.verify_native_sample(source, [part], info, ROWS)
    require(isinstance(entry.get('corpus_overlap'), str) and
            'share problems intentionally' in entry['corpus_overlap'], 'Missing MATH lineage overlap warning')
    return dict(name=NAME, source=str(source), repeat=5, rows=ROWS, tokens=TOKENS, parts=[part],
        tokenized_root=str(root), native_token_parity=parity,
        token_metrics=dict(training=dict(tokens=TOKENS, basis='single_assistant_native_gemma_prompt_plus_response')),
        repo_id=REPO, revision=REVISION, license='mit', publication_contract='local-worked-math-v1',
        quality_basis='Original source worked solutions; not model audited',
        corpus_overlap=entry['corpus_overlap'], conversion_corpus_overlap=manifest['corpus_overlap'],
        conversion_repeat=manifest['repeat'], effective_repeat=5,
        repeat_policy='Current registry repeat 5; historical conversion repeat is not resampling authorization',
        screening=dict(policy=manifest['overlap_policy'], exclusions=manifest['exclusions'],
                       test_rows_in_output=0, whole_corpus_deduplicated=False))
