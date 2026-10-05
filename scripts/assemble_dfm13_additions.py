"""Prepare a verified wave3/4 additions tree and explicit base reference. No sampling.

Verification is sequential and reads every selected source and token array.
Symlinks are hash-pinned references, not immutable copies of their targets.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[1]
if __package__ in (None, ''):
    sys.path.insert(0, str(REPO))
FIELDS = ('tokens', 'inst_start', 'inst_len', 'resp_start', 'resp_len')


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def signature(path):
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def checksum(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def pin(path, pins, expected=None):
    path = Path(path).resolve(strict=True)
    before = signature(path)
    digest = checksum(path)
    require(signature(path) == before, f'File changed while hashing: {path}')
    require(expected is None or digest == expected, f'Hash mismatch: {path}')
    if str(path) in pins:
        require(pins[str(path)]['sha256'] == digest, f'Previously pinned file changed: {path}')
    pins[str(path)] = dict(sha256=digest, bytes=before[2], signature=list(before))
    return path


def read_json(path, pins, expected=None):
    path = pin(path, pins, expected)
    return json.loads(path.read_text())


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def token_contract(info, pins):
    require(info.get('enable_thinking') is False, 'Thinking must be explicitly disabled')
    require(info.get('template_mode') == 'jinja_chat_template', 'Unsupported template mode')
    result = {k: info[k] for k in ('enable_thinking', 'template_mode', 'vocab_size')}
    require(type(result['vocab_size']) is int and result['vocab_size'] > 0, 'Invalid vocabulary size')
    for field in ('tokenizer_path', 'chat_template_path'):
        path = Path(info[field])
        path = path if path.is_absolute() else REPO / path
        path = pin(path, pins)
        result[field + '_sha256'] = pins[str(path)]['sha256']
    return result


def base_reference(base, pins):
    meta = read_json(base / 'metadata.json', pins)
    require(meta.get('max_seq_len') == 4097, 'Base must use the 4096-position sampled training contract')
    contract = token_contract(meta['tokenizer_info'], pins)
    epochs = []
    for directory in sorted(base.glob('epoch_*')):
        if not directory.is_dir() or not re.fullmatch(r'epoch_\d+', directory.name):
            continue
        refs = {}
        for field in FIELDS[1:]:
            path = (directory / (field + '.npy')).resolve(strict=True)
            refs[field] = dict(path=str(path), signature=list(signature(path)),
                               validation='reference_only_not_payload_hashed')
        epochs.append(dict(name=directory.name, files=refs))
    require(bool(epochs), 'No base epoch indices found')
    tokens = (base / 'tokens.npy').resolve(strict=True)
    for filename in ('epoch-mapping.json', 'build-receipt.json'):
        if (base / filename).exists():
            pin(base / filename, pins)
    return dict(path=str(base), metadata_sha256=pins[str((base / 'metadata.json').resolve())]['sha256'],
                tokenizer_contract=contract, epochs=epochs,
                tokens=dict(path=str(tokens), signature=list(signature(tokens)), validation='reference_only_not_payload_hashed'),
                policy='Explicit caller choice; epoch files untouched, no epoch selection or repeat inference'), meta['tokenizer_info']


def blkt_publication(entry):
    from dfm12.blkt_publish import TASKS
    return entry.get('name') in {
        'dfm13_wave3_transform_baltic_lt_blkt_' + task.replace('-', '_') + '_newgenltu'
        for task in TASKS}


def verify_blkt_publication(entry, source, pins):
    from dfm12.blkt_publish import MODEL_CONDITIONS, PREPARATION_SHA, TASKS
    from dfm12.blkt_export import LICENSE_SHA, REPO, REVISION
    folder = source.parent.parent
    export = read_json(folder / 'manifest.json', pins, entry['export_manifest_sha256'])
    publication = read_json(folder.parent / (folder.name + '.verified.json'), pins)
    require(Path(entry['export_manifest']).resolve() == folder / 'manifest.json', 'BLKT manifest path mismatch')
    require(entry.get('publication_status') == publication.get('publication_status') == 'verified'
            and entry.get('uploaded') is True and publication.get('uploaded') is True,
            'BLKT publication not verified/uploaded')
    require(publication.get('hf_revision') == entry.get('hf_revision') and bool(entry.get('hf_revision')),
            'BLKT publication revision mismatch')
    require((entry.get('repo_id'), entry.get('revision')) == (REPO, REVISION), 'BLKT source mismatch')
    require(entry.get('task') in TASKS and entry['rows'] == TASKS[entry['task']], 'BLKT population mismatch')
    expected_name = 'dfm13_wave3_transform_baltic_lt_blkt_' + entry['task'].replace('-', '_') + '_newgenltu'
    require(entry['name'] == expected_name and entry['hf_repo_id'] == 'schneiderkamplab/' + expected_name.replace('_', '-'),
            'BLKT destination mismatch')
    for field in ('name', 'rows', 'rendered_tokens', 'output_sha256', 'hf_repo_id', 'target_policy',
                  'repo_id', 'revision', 'license', 'task', 'files', 'preparation_sha256',
                  'preparation_data_sha256', 'model_use_conditions', 'admission_authorized'):
        require(field in entry and entry[field] == publication.get(field) == export.get(field),
                'BLKT publication/export mismatch: ' + field)
    require(entry['preparation_sha256'] == PREPARATION_SHA and entry['admission_authorized'] is True,
            'BLKT preparation/admission mismatch')
    require(entry['model_use_conditions'] == MODEL_CONDITIONS, 'BLKT model-use conditions mismatch')
    require(Path(publication['output']).resolve() == source and Path(export['output']).resolve() == source,
            'BLKT output path mismatch')
    required = {'LICENSE.txt', 'NOTICE.txt', 'USE_CONDITIONS.md', 'SOURCE_README.md',
                'attribution.jsonl', 'README.md', 'data/train.jsonl'}
    require(set(export['files']) == required and export['files']['LICENSE.txt'] == LICENSE_SHA,
            'BLKT mandatory attachments missing')
    for relative, sha in export['files'].items():
        path = (folder / relative).resolve()
        require(path.is_relative_to(folder), 'BLKT attachment escapes package')
        pin(path, pins, sha)
    return publication, export


def verify_lt_summary_publication(entry, source, pins):
    from dfm12.lt_summary_publish import verify_package
    folder = source.parent.parent
    export = verify_package(folder, entry['export_manifest_sha256'])
    publication = read_json(folder.parent / (folder.name + '.verified.json'), pins)
    pin(folder / 'manifest.json', pins, entry['export_manifest_sha256'])
    require(Path(entry['export_manifest']).resolve() == folder / 'manifest.json', 'Summary manifest path mismatch')
    require(entry.get('publication_status') == publication.get('publication_status') == 'verified',
            'Summary publication not verified')
    for field in export:
        if field not in ('uploaded', 'tokenization_performed'):
            require(entry.get(field) == publication.get(field) == export[field],
                    'Summary publication/export mismatch: ' + field)
    for relative, sha in export['files'].items():
        pin(folder / relative, pins, sha)
    return publication, export


def unready_reason(entry):
    if entry.get('publication_contract') == 'wave4-compact-recovered-full-history-v1':
        from dfm12.wave4_finished_assembly import unready
        return unready(entry)
    if entry.get('publication_contract') == 'baltic-compact-accepted-full-history-v1':
        from dfm12.baltic_finished_assembly import unready
        return unready(entry)
    from dfm12.wave_publication_holds import entry_quality_hold
    if entry_quality_hold(entry):
        return 'quality_hold_source_fidelity'
    if entry.get('publication_contract') == 'tlpc-grounded-audited-v1':
        from dfm12.tlpc_assembly import unready
        return unready(entry)
    if entry.get('audit_contract') == 'dala-compact-whole-pair-four-labels-v1':
        from dfm12.dala_compact_assembly import unready
        return unready(entry)
    from dfm12.local_wave_assembly import CONTRACT, unready as local_unready
    if entry.get('publication_contract') == CONTRACT:
        return local_unready(entry)
    if entry.get('name') == 'hendrycks_math_worked':
        from dfm12.math_assembly import unready_reason as math_unready_reason
        return math_unready_reason(entry)
    identity = re.sub(r'[^a-z0-9]', '', str(entry.get('name', '')).lower())
    if any(name in identity for name in ('mimirsearch', 'searcharena', 'repochat')):
        return 'research_only_source_excluded_by_user_policy'
    from dfm12.nonwave_assembly import NAMES, unready_reason as nonwave_unready
    if entry.get('name') in NAMES:
        return nonwave_unready(entry)
    if not entry.get('name', '').startswith(('dfm13_wave3_', 'dfm13_wave4_')):
        return 'unsupported_non_wave_contract; not asserted unusable, requires a separate verified adapter'
    if entry.get('status') != 'accepted_uploaded' or entry.get('uploaded') is not True or not entry.get('hf_revision'):
        return 'not_accepted_uploaded_with_revision'
    if entry.get('tokenization_performed') is not True or not entry.get('tokenized_path') or not entry.get('tokenization_receipt'):
        return 'tokenization_not_ready'
    if type(entry.get('repeat')) is not int or entry['repeat'] < 0:
        return 'invalid_repeat'
    if not entry['repeat']:
        return 'repeat_zero_explicitly_excluded'
    return None


def verify_arrays(directory, vocab, pins):
    arrays = {}
    for field in FIELDS:
        path = pin(directory / (field + '.npy'), pins)
        array = np.load(path, mmap_mode='r', allow_pickle=False)
        require(array.ndim == 1 and array.dtype.kind in 'iu', f'Noninteger/nonvector array: {path}')
        arrays[field] = array
    n = len(arrays['inst_len']); size = len(arrays['tokens'])
    require(all(len(arrays[k]) == n for k in FIELDS[1:]), 'Array row counts differ')
    cursor = total = 0
    for lo in range(0, n, 65536):
        values = {k: a[lo:lo+65536] for k, a in arrays.items() if k != 'tokens'}
        require(all(np.all(v >= 0) and np.all(v <= size) for v in values.values()), 'Negative/out-of-bounds index or length')
        a = {k: v.astype(np.int64) for k, v in values.items()}
        require(np.all(a['resp_len'] >= 2), 'Empty/invalid supervised target')
        require(np.all(a['inst_len'] + a['resp_len'] <= 4096), 'Oversize target')
        require(np.all(a['resp_start'] == a['inst_start'] + a['inst_len']), 'Noncontiguous prompt/response')
        ends = a['resp_start'] + a['resp_len']
        require(np.all(ends <= size), 'Response outside token array')
        require(a['inst_start'][0] == cursor and np.array_equal(a['inst_start'][1:], ends[:-1]), 'Gap/overlap/reordered target starts')
        cursor = int(ends[-1]); total += int((a['inst_len'] + a['resp_len']).sum())
    require(cursor == size == total, 'Unreferenced or missing tokens')
    for lo in range(0, size, 1 << 20):
        values = arrays['tokens'][lo:lo+(1 << 20)]
        require(np.all(values >= 0) and np.all(values < vocab), 'Token outside vocabulary')
    return dict(rows=n, tokens=total, arrays={field: dict(path=str((directory / (field + '.npy')).resolve()),
        sha256=pins[str((directory / (field + '.npy')).resolve())]['sha256']) for field in FIELDS})


def native_encoder(info):
    import jinja2
    from tokenizers import Tokenizer
    from scripts.tokenize_chat_template import examples_from_messages, tokenize_example
    def path(key):
        p = Path(info[key])
        return p if p.is_absolute() else REPO / p
    tokenizer = Tokenizer.from_file(str(path('tokenizer_path')))
    template = jinja2.Environment().from_string(path('chat_template_path').read_text())

    def encode(row, final_only=True):
        examples = examples_from_messages(row['messages'], row.get('tools'),
            row['target_message_index'] if final_only else None)
        values = [tokenize_example(tokenizer, template, e, False, max_seq_len=None) for e in examples]
        require(bool(values) and all(v is not None for v in values), 'Native render failed')
        return values
    return encode


def verify_native_sample(source, parts, info, rows):
    """At most eight rows: five spread ordinals plus the first three multi-turn rows."""
    selected = {0, rows // 4, rows // 2, 3 * rows // 4, rows - 1}
    samples = {}; multi = 0
    with source.open() as handle:
        for ordinal, line in enumerate(handle):
            row = json.loads(line)
            assistants = sum(m.get('role') == 'assistant' for m in row['messages'])
            if assistants > 1 and multi < 3:
                selected.add(ordinal); multi += 1
            if ordinal in selected:
                samples[ordinal] = row
    encode = native_encoder(info)
    results = []
    for ordinal, row in sorted(samples.items()):
        local = ordinal
        for part in parts:
            if local < part['rows']:
                break
            local -= part['rows']
        else:
            raise ValueError('Native sample ordinal outside shards')
        arrays = {k: np.load(Path(part['path']) / (k + '.npy'), mmap_mode='r', allow_pickle=False) for k in FIELDS}
        encoded = encode(row)
        require(len(encoded) == 1, 'Final target expanded')
        prompt, response = encoded[0]
        require(len(prompt) + len(response) <= 4096, 'Untruncated native target exceeds context limit')
        for prefix, expected in (('inst', prompt), ('resp', response)):
            start = int(arrays[prefix + '_start'][local]); length = int(arrays[prefix + '_len'][local])
            require(length == len(expected) and np.array_equal(arrays['tokens'][start:start+length], expected),
                    f'Native {prefix} token parity mismatch at source row {ordinal}')
        all_tokens = sum(sum(map(len, v)) for v in encode(row, False))
        declared = row.get('rendered_tokens')
        if declared is not None:
            require(declared == all_tokens, f'Preflight all-assistant count mismatch at source row {ordinal}')
        results.append(dict(ordinal=ordinal, part=Path(part['path']).name, part_row=local,
            row_sha256=hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            assistant_messages=sum(m.get('role') == 'assistant' for m in row['messages']),
            inst_start=int(arrays['inst_start'][local]), resp_start=int(arrays['resp_start'][local]),
            prompt_tokens=len(prompt), response_tokens=len(response),
            final_target_tokens=len(prompt)+len(response), all_assistant_rendered_tokens=all_tokens,
            declared_preflight_tokens=declared, exact_prompt_and_response_tokens=True))
    return dict(scope='deterministic_sample_not_full_corpus', truncation=False,
        selection='five spread row ordinals plus first three multi-assistant rows', rows=results)


def verify_entry(entry, contract, pins):
    if entry.get('publication_contract') == 'wave4-compact-recovered-full-history-v1':
        from dfm12.wave4_finished_assembly import verify
        return verify(entry, contract, pins, sys.modules[__name__])
    if entry.get('publication_contract') == 'baltic-compact-accepted-full-history-v1':
        from dfm12.baltic_finished_assembly import verify
        return verify(entry, contract, pins, sys.modules[__name__])
    from dfm12.wave_publication_holds import entry_quality_hold
    require(not entry_quality_hold(entry), 'quality_hold_source_fidelity')
    if entry.get('publication_contract') == 'tlpc-grounded-audited-v1':
        from dfm12.tlpc_assembly import verify
        return verify(entry, contract, pins, sys.modules[__name__])
    if entry.get('audit_contract') == 'dala-compact-whole-pair-four-labels-v1':
        from dfm12.dala_compact_assembly import verify
        return verify(entry, contract, pins, sys.modules[__name__])
    if entry.get('name') == 'hendrycks_math_worked':
        from dfm12.math_assembly import verify as verify_math
        return verify_math(entry, contract, pins, api=sys.modules[__name__])
    from dfm12.nonwave_assembly import NAMES, verify as verify_nonwave
    if entry.get('name') in NAMES:
        return verify_nonwave(entry, contract, pins, api=sys.modules[__name__])
    name = entry['name']
    from dfm12.local_wave_assembly import CONTRACT, publication as local_publication
    local = entry.get('publication_contract') == CONTRACT
    require(re.fullmatch(r'[A-Za-z0-9_]+', name) is not None, 'Unsafe source name')
    require(entry.get('target_policy') == 'final_assistant_only_native_gemma', 'Unsupported target policy')
    require(type(entry.get('rows')) is int and entry['rows'] > 0, 'Invalid source count')
    source = pin(entry['output'], pins, entry['output_sha256'])
    scoped_blkt = blkt_publication(entry)
    scoped_summary = entry['name'] == 'dfm13_wave3_baltic_lt_summary_newgenltu'
    from dfm12.finepdf_assembly import NAMES as FINEPDF_NAMES, publication as finepdf_publication
    if local:
        publication, export = local_publication(entry, source, pins, sys.modules[__name__])
    elif entry['name'] in FINEPDF_NAMES:
        publication, export = finepdf_publication(entry, source, pins, sys.modules[__name__])
    elif entry.get('subset_policy') == 'fa_minimal_structural_v2':
        from dfm12.fa_transform_subset import verify_assembly_publication
        publication, export = verify_assembly_publication(entry, source, pins, sys.modules[__name__])
    elif entry.get('subset_policy') == 'hr_reordering_manual44_v1':
        from dfm12.hr_transform_subset import verify_assembly_publication
        publication, export = verify_assembly_publication(entry, source, pins, sys.modules[__name__])
    elif entry.get('subset_policy') == 'sl_sq_reviewed_exact4_v1':
        from dfm12.reviewed_transform_subset import verify_assembly_publication
        publication, export = verify_assembly_publication(entry, source, pins, sys.modules[__name__])
    elif scoped_summary:
        publication, export = verify_lt_summary_publication(entry, source, pins)
    elif scoped_blkt:
        publication, export = verify_blkt_publication(entry, source, pins)
    else:
        publication = read_json(entry['manifest'], pins, entry.get('manifest_sha256'))
        export = read_json(source.parent.parent / 'manifest.json', pins, entry.get('export_manifest_sha256'))
    for field in ('name', 'rows', 'rendered_tokens', 'output_sha256', 'hf_repo_id', 'target_policy'):
        require(field in entry and publication.get(field) == entry[field] == export.get(field), f'Publication/export mismatch: {field}')
    for field in ('repo_id', 'revision', 'input_sha256', 'selection_sha256', 'license', 'licenses', 'attribution_files'):
        if field in entry:
            require(publication.get(field) == entry[field] == export.get(field), f'Provenance mismatch: {field}')
    if not local:
        require(publication.get('status') == 'accepted_uploaded' and publication.get('uploaded') is True,
                'Publication not accepted/uploaded')
        require(publication.get('hf_revision') == entry['hf_revision'], 'Publication revision mismatch')
    require(Path(publication['output']).resolve() == source and Path(export['output']).resolve() == source, 'Export output path mismatch')
    for expected, relative in entry.get('attribution_files', {}).items():
        path = (source.parent.parent / relative).resolve()
        require(path.is_relative_to(source.parent.parent), 'Attribution escapes package')
        pin(path, pins, expected)
    rows = 0; declared_tokens = 0; declared_rows = 0
    with source.open() as handle:
        for line in handle:
            row = json.loads(line); messages = row['messages']; target = row.get('target_message_index')
            if local:
                from dfm12.jobs import validate_audit
                validate_audit(row['audit'])
                require(row['audit']['keep'] is True and row.get('quality_status') == 'accepted',
                        'Local row not accepted')
            require(bool(messages) and type(target) is int and target == len(messages)-1,
                    'Missing final target marker')
            require(messages[target].get('role') == 'assistant' and
                    bool(messages[target].get('content') or messages[target].get('tool_calls')), 'Invalid final assistant')
            if 'rendered_tokens' in row:
                require(type(row['rendered_tokens']) is int and row['rendered_tokens'] > 0, 'Invalid row preflight count')
                declared_tokens += row['rendered_tokens']; declared_rows += 1
            rows += 1
    require(rows == entry['rows'], 'Source row count mismatch')
    require(declared_rows in (0, rows), 'Partial row preflight counts')
    if declared_rows:
        require(declared_tokens == entry['rendered_tokens'], 'Source preflight sum mismatch')
    root = Path(entry['tokenized_path']).resolve(strict=True)
    receipt = read_json(entry['tokenization_receipt'], pins, entry.get('tokenization_receipt_sha256'))
    expected_token_pins = dict(source_sha256=entry['output_sha256'],
        tokenizer_sha256=contract['tokenizer_path_sha256'], template_sha256=contract['chat_template_path_sha256'])
    if local:
        expected_token_pins.update(export_manifest_sha256=entry['export_manifest_sha256'],
                                   selection_sha256=entry['selection_sha256'])
    require(receipt['pins'] == expected_token_pins,
        'Tokenization pins differ from source/base')
    require(Path(receipt['output']).resolve() == root, 'Receipt tokenized path mismatch')
    info = read_json(root / 'tokenizer_info.json', pins)
    require(token_contract(info, pins) == contract, 'Tokenizer/template contract differs')
    completion = read_json(root / 'completion.json', pins)
    require(completion.get('rows') == rows and completion.get('skipped_rows_this_run') == 0 and
            completion.get('max_seq_len') == 4096, 'Tokenization dropped/expanded rows or wrong context limit')
    parts = sorted(p for p in root.iterdir() if p.is_dir())
    require(bool(parts) and all(re.fullmatch(r'part-\d{6}\.jsonl', p.name) for p in parts), 'Unexpected token shard directory')
    require(len(parts) == completion.get('files'), 'Completion shard count mismatch')
    verified = []
    for part in parts:
        item = verify_arrays(part, contract['vocab_size'], pins)
        verified.append(dict(item, path=str(part.resolve()), link_name=name + '__' + part.name))
    n = sum(p['rows'] for p in verified); tokens = sum(p['tokens'] for p in verified)
    require(n == rows == receipt['rows'] == entry['tokenized_rows'], 'Materialized row count mismatch')
    require(tokens == receipt['tokens'] == entry['tokenized_tokens'], 'Materialized token count mismatch')
    require(type(entry['rendered_tokens']) is int and entry['rendered_tokens'] >= tokens,
            'All-assistant preflight budget below final-target tokens')
    parity = verify_native_sample(source, verified, info, rows)
    return dict(name=name, source=str(source), repeat=entry['repeat'], rows=n, tokens=tokens, parts=verified,
        token_metrics=dict(training=dict(tokens=tokens, basis='final_assistant_only_native_gemma_prompt_plus_response'),
            preflight=dict(tokens=entry['rendered_tokens'], basis='all_assistant_targets_with_repeated_prefixes',
                source_row_sum_verified=declared_rows == rows,
                verification='publisher/export agreement; native rerender sampled, not full total recomputation')),
        native_token_parity=parity,
        hf_repo_id=entry['hf_repo_id'], hf_revision=entry['hf_revision'], tokenized_root=str(root),
        **(dict(publication_contract=CONTRACT, uploaded=False, publication_pending=True) if local else {}),
        **(dict(model_use_conditions=entry['model_use_conditions'], license=entry['license'],
                publication_contract=('lt-summary-privacy-newgenltu-v1' if scoped_summary
                                      else 'blkt-newgenltu-verified-v1')) if scoped_blkt or scoped_summary else {}))


def verify_current_registry(manifest, snapshot):
    """Admission follows current source versions, not just historical byte pins."""
    current = json.loads(Path(manifest['registry_path']).read_text())
    require(current.get('inherits') == snapshot.get('inherits') == 'dfm12',
            'Current registry inheritance changed')
    entries = current['additions']
    names = [e['name'] for e in entries]
    require(len(names) == len(set(names)), 'Duplicate current registry source names')
    live = {e['name']: e for e in entries}
    frozen = {e['name']: e for e in snapshot['additions']}
    fields = {
        'output', 'manifest', 'export_manifest', 'hf_repo_id', 'hf_revision',
        'repo_id', 'revision', 'split', 'configs', 'rows', 'tokens', 'rendered_tokens',
        'repeat', 'target_policy', 'hard_truncation', 'admission_authorized', 'context_view',
        'status', 'uploaded', 'publication_status', 'tokenization_performed',
        'tokenized_path', 'tokenized_output', 'tokenization_receipt',
        'tokenized_rows', 'tokenized_tokens', 'files', 'attribution_files',
        'license', 'licenses', 'model_use_conditions', 'subset_policy',
        'publication_contract', 'publication_pending', 'selection_receipt',
        'subset_receipt', 'parent_hf_revision', 'counts',
    }
    for source in manifest['ready_additions']:
        name = source['name']
        require(name in live and name in frozen, 'Assembled source withdrawn from current registry: '+name)
        before, now = frozen[name], live[name]
        reason = unready_reason(now)
        require(reason is None, 'Current source admission blocked: '+name+': '+str(reason))
        pins = {k for k in before.keys() | now.keys()
                if k.endswith(('_sha256', '_pins'))}
        changed = sorted(k for k in fields | pins if before.get(k) != now.get(k))
        require(not changed, 'Assembled source superseded in current registry: '+name+
                '; changed='+','.join(changed))


def verify_assembly(output):
    """Recheck linked additions before later consumption; does not sample."""
    manifest = json.loads((output / 'assembly.json').read_text())
    from dfm12.wave_publication_holds import entry_quality_hold
    require(not any(entry_quality_hold(e) for e in manifest.get('ready_additions', [])),
            'quality_hold_source_fidelity: previously assembled source now held')
    require(checksum(output / 'registry.snapshot.json') == manifest['registry_sha256'], 'Registry snapshot changed')
    verify_current_registry(manifest, json.loads((output / 'registry.snapshot.json').read_text()))
    for path, record in manifest['files'].items():
        require(checksum(Path(path)) == record['sha256'], f'Assembly input changed: {path}')
    for relative, expected in manifest['generated_files'].items():
        require(checksum(output / relative) == expected, f'Generated assembly file changed: {relative}')
    for source in manifest['ready_additions']:
        require((output / 'accepted_inputs' / source['name'] / 'train.jsonl').resolve() == Path(source['source']), 'Source link changed')
        for part in source['parts']:
            require((output / 'tokenized_additions' / part['link_name']).resolve() == Path(part['path']), 'Tokenized link changed')
    for epoch in manifest['base']['epochs']:
        for record in epoch['files'].values():
            require(list(signature(Path(record['path']))) == record['signature'], 'Base epoch reference changed')
    require(list(signature(Path(manifest['base']['tokens']['path']))) == manifest['base']['tokens']['signature'], 'Base token reference changed')
    verify_current_registry(manifest, json.loads((output / 'registry.snapshot.json').read_text()))
    return manifest


def assemble(registry, base, output):
    registry = registry.resolve(strict=True); base = base.resolve(strict=True); output = output.resolve()
    require(not output.exists(), 'Output already exists; use a new isolated root')
    require(not output.is_relative_to(base) and not base.is_relative_to(output) and not registry.is_relative_to(output), 'Output overlaps inputs')
    raw_registry = registry.read_bytes(); config = json.loads(raw_registry)
    require(config.get('inherits') == 'dfm12', 'Registry does not declare DFM12 inheritance')
    entries = config['additions']; names = [e['name'] for e in entries]
    require(len(names) == len(set(names)), 'Duplicate registry source names')
    for entry in entries:
        if entry.get('tokenized_path'):
            require(not output.is_relative_to(Path(entry['tokenized_path']).resolve()), 'Output overlaps tokenized input root')
        if entry.get('output') and entry['name'].startswith(('dfm13_wave3_', 'dfm13_wave4_')):
            require(not output.is_relative_to(Path(entry['output']).resolve().parent.parent), 'Output overlaps export package')
    pins = {}; base_ref, base_info = base_reference(base, pins)
    ready = []; unready = []; used_payloads = set(); used_parts = set()
    for entry in entries:
        reason = unready_reason(entry)
        if reason:
            unready.append(dict(name=entry['name'], reason=reason)); continue
        candidate_pins = {}
        try:
            candidate = verify_entry(entry, base_ref['tokenizer_contract'], candidate_pins)
            require(entry['output_sha256'] not in used_payloads, 'Duplicate source payload')
            require(not any(p['path'] in used_parts for p in candidate['parts']), 'Duplicate tokenized shard target')
            require(all(not Path(p).is_relative_to(output) for p in candidate_pins), 'Output overlaps source input')
            for path, record in candidate_pins.items():
                require(path not in pins or pins[path]['sha256'] == record['sha256'], 'Shared input changed')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            unready.append(dict(name=entry['name'], reason='verification_failed', detail=str(exc))); continue
        pins.update(candidate_pins); ready.append(candidate); used_payloads.add(entry['output_sha256'])
        used_parts.update(p['path'] for p in candidate['parts'])
    for path, record in pins.items():
        require(list(signature(Path(path))) == record['signature'], f'Input mutated during assembly: {path}')
    for source in ready:
        require(sorted(p.resolve() for p in Path(source['tokenized_root']).iterdir() if p.is_dir()) ==
                sorted(Path(p['path']) for p in source['parts']), 'Shard inventory changed during assembly')
    for epoch in base_ref['epochs']:
        for record in epoch['files'].values():
            require(list(signature(Path(record['path']))) == record['signature'], 'Base epoch changed during assembly')
    require(list(signature(Path(base_ref['tokens']['path']))) == base_ref['tokens']['signature'], 'Base tokens changed during assembly')
    prefixes = [s['name'] + '__' for s in ready]
    require(not any(a != b and b.startswith(a) for a in prefixes for b in prefixes), 'Overlapping repeat prefixes')
    stage = output.with_name(output.name + '.building')
    stage.mkdir(parents=True, exist_ok=False)
    (stage / 'registry.snapshot.json').write_bytes(raw_registry)
    (stage / 'accepted_inputs').mkdir(); (stage / 'tokenized_additions').mkdir()
    normalized_info = dict(base_info)
    for field in ('tokenizer_path', 'chat_template_path'):
        path = Path(base_info[field]); normalized_info[field] = str(path if path.is_absolute() else (REPO / path).resolve())
    write_json(stage / 'tokenized_additions/tokenizer_info.json', normalized_info)
    repeats = []
    for source in ready:
        directory = stage / 'accepted_inputs' / source['name']; directory.mkdir()
        (directory / 'train.jsonl').symlink_to(source['source'])
        repeats.append(dict(prefix=source['name']+'__', repeat=source['repeat']))
        for part in source['parts']:
            (stage / 'tokenized_additions' / part['link_name']).symlink_to(part['path'], target_is_directory=True)
    write_json(stage / 'repeat_mapping.json', repeats)
    manifest = dict(schema='dfm13-verified-additions-assembly-v1', status='prepared_wave_subset_not_training_dataset',
        complete_dfm13=False, sampling_performed=False, base=base_ref, registry_path=str(registry),
        totals_basis='One stored copy of each verified addition; repeat policy recorded but not materialized',
        registry_sha256=hashlib.sha256(raw_registry).hexdigest(), ready_additions=ready, unready_additions=unready,
        files=pins, totals=dict(ready_sources=len(ready), unready_sources=len(unready),
            rows=sum(r['rows'] for r in ready), tokens=sum(r['tokens'] for r in ready)),
        generated_files={p: checksum(stage / p) for p in ('registry.snapshot.json', 'repeat_mapping.json', 'tokenized_additions/tokenizer_info.json')},
        limitations=['No epoch selection, sampled indices, token concatenation or training config produced.',
            'Base payload/epoch files are unchanged stat references, not freshly content-hashed.',
            'Full array structural integrity and hash pins; untruncated native prompt/response token parity only on bounded deterministic samples.',
            'Publication is verified against local publisher receipts; no new remote HF request.',
            'No semantic or whole-corpus deduplication; exact duplicate source payload/shard targets rejected.',
            'Symlink targets remain external; reverify pinned hashes before later consumption.'])
    write_json(stage / 'assembly.json', manifest)
    stage.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--registry', type=Path, default=REPO / 'config/dfm13_sources.json')
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = assemble(args.registry, args.base, args.output)
    print(json.dumps(dict(output=str(args.output), status=result['status'], **result['totals']), indent=2))


if __name__ == '__main__':
    main()
