"""Verify terminal compact DaLA train subsets without claiming producer equivalence."""
from contextlib import closing
import gzip
import json
from pathlib import Path

from .dala_compact_finalize import CONTRACT, accepted, canonical, readonly, task_row, text_key
from .io import atomic, file_hash, load, write_json


def unready(entry):
    if (entry.get('audit_contract') != CONTRACT or entry.get('status') != 'accepted_local_tokenized'
            or entry.get('split') != 'train' or entry.get('uploaded') is not False
            or entry.get('producer_v2_audit_equivalent') is not False
            or entry.get('task') not in ('acceptability', 'correction')):
        return 'invalid_dala_compact_contract'
    if not entry.get('output') or not entry.get('tokenized_path'):
        return 'dala_local_view_not_ready'
    return None


def prepare(finalized, output):
    complete = load(finalized/'complete.json')
    if not complete['success'] or file_hash(complete['registry']['path']) != complete['registry']['sha256']:
        raise ValueError('DaLA finalization incomplete or registry drift')
    entries = []
    for raw in load(finalized/'registry.json')['additions']:
        export = load(raw['export_receipt']['path'])
        folder = output/raw['name']; folder.mkdir(parents=True, exist_ok=True)
        source = folder/'train.jsonl'
        selected = sorted((f for f in export['files'] if f['relative'].startswith('train/'+raw['task']+'/')),
                          key=lambda f:f['relative'])
        if not selected: raise ValueError('Missing train shards')
        count = 0
        with atomic(source) as out:
            for item in selected:
                if file_hash(item['path']) != item['sha256']: raise ValueError('DaLA train shard drift')
                with gzip.open(item['path'], 'rt') as stream:
                    for line in stream:
                        row = json.loads(line)
                        if row['split'] != 'train' or row['view'] != 'representative':
                            raise ValueError('Heldout in training view')
                        out.write(line); count += 1
        if count != raw['rows']: raise ValueError('DaLA train count mismatch')
        entries.append(dict(raw, output=str(source.resolve()), output_sha256=file_hash(source),
            tokenized_rows=raw['rows'], tokenized_tokens=raw['tokens'],
            local_view_shards=selected, finalization_complete=dict(path=str((finalized/'complete.json').resolve()),
                sha256=file_hash(finalized/'complete.json'))))
    return entries


def verify(entry, contract, pins, api):
    require = api.require
    require(unready(entry) is None, 'Invalid DaLA admission')
    def evidence(item):
        return api.read_json(item['path'], pins, item['sha256'])
    done = evidence(entry['finalization_complete']); require(done['success'], 'DaLA finalization failed')
    for path, sha in done.get('group_integrations', {}).items():
        group = api.read_json(path, pins, sha)
        require(group['status'] == 'complete_train_only', 'Incomplete scoped DaLA group')
    export = evidence(entry['export_receipt']); snap = evidence(entry['snapshot'])
    for item in export.get('recovery_training_exclusion_pins', []):
        api.pin(item['path'], pins, item['sha256'])
    if export.get('additional_exclusion_implementation'):
        item = export['additional_exclusion_implementation']
        api.pin(item['path'], pins, item['sha256'])
    require(export['contract'] == snap['contract'] == CONTRACT and snap['terminal'] is True,
            'Invalid compact snapshot')
    require(export['tokenizer_inputs_train_only'] and export['producer_v2_audit_equivalent'] is False,
            'DaLA split/equivalence mismatch')
    source = api.pin(entry['output'], pins, entry['output_sha256'])
    api.pin(entry['tokenizer']['path'], pins, contract['tokenizer_path_sha256'])
    api.pin(entry['template']['path'], pins, contract['chat_template_path_sha256'])
    require(entry['tokenizer']['sha256'] == contract['tokenizer_path_sha256'] and
            entry['template']['sha256'] == contract['chat_template_path_sha256'], 'DaLA tokenizer pin mismatch')
    for item in export['files'] + export['heldout_sources'] + snap['sources']:
        api.pin(item['path'], pins, item['sha256'])
    inventory = evidence(export['producer_inventory'])
    profile = next(x for x in inventory['languages'] if x['language'] == entry['language'])['profile']
    for item in (snap['decisions'], export['heldout_index'], export['prior_index']):
        api.pin(item['path'], pins, item['sha256'])
    count = 0
    with closing(readonly(snap['decisions']['path'])) as db, closing(readonly(export['heldout_index']['path'])) as held:
        with source.open() as stream:
            for line in stream:
                row = json.loads(line); ev = row['compact_audit']; original = row['provenance']
                require(row['split'] == original['split'] == 'train' and row['view'] == 'representative', 'Heldout row admitted')
                result = db.execute('SELECT record,status,result,alias FROM decisions WHERE component=? AND ordinal=?',
                    (ev['source_component'], ev['ordinal'])).fetchone()
                require(result is not None, 'Missing DaLA decision')
                record, status, audit, alias = result
                record, audit, alias = json.loads(record), json.loads(audit), json.loads(alias)
                from .io import digest
                require(record == canonical(original, entry['language'], record['kind']) and
                        alias['row_sha256'] == digest(original) == ev['source_row_sha256'], 'DaLA source binding mismatch')
                require(accepted(record, audit, status) and audit == ev['decision'] and
                        ev['snapshot_sha256'] == entry['snapshot']['sha256'], 'DaLA nonpassing decision')
                require(row == task_row(original, record, entry['task'], profile['prompts'], ev), 'DaLA task reconstruction mismatch')
                keys = [('text',text_key(original[k])) for k in ('original','corrupted') if k in original]
                keys += [('document', original[k]) for k in ('document_id','document_sha256') if original.get(k)]
                require(not any(held.execute('SELECT 1 FROM held WHERE kind=? AND key=?', k).fetchone() for k in keys),
                        'DaLA heldout overlap')
                count += 1
    require(count == entry['rows'], 'DaLA source count mismatch')
    root = Path(entry['tokenized_path']).resolve()
    info = api.read_json(root/'tokenizer_info.json', pins)
    require(api.token_contract(info, pins) == contract, 'DaLA native template mismatch')
    completion = api.read_json(root/'completion.json', pins)
    require(completion['rows'] == count and not completion['skipped_rows_this_run'] and completion['max_seq_len'] == 4096,
            'DaLA dropped rows/context mismatch')
    parts = []
    for part in sorted(p for p in root.iterdir() if p.is_dir()):
        checked = api.verify_arrays(part, contract['vocab_size'], pins)
        for arr in checked['arrays'].values():
            require(entry['array_pins'].get(arr['path']) == arr['sha256'], 'DaLA array seal mismatch')
        parts.append(dict(checked, path=str(part), link_name=entry['name']+'__'+part.name))
    require(len(parts) == completion['files'] and sum(p['rows'] for p in parts) == count and
            sum(p['tokens'] for p in parts) == entry['tokens'], 'DaLA token totals mismatch')
    parity = api.verify_native_sample(source, parts, info, count)
    return dict(name=entry['name'], source=str(source), repeat=entry['repeat'], rows=count, tokens=entry['tokens'],
        parts=parts, tokenized_root=str(root), native_token_parity=parity, uploaded=False, hf_revision=None,
        publication_pending=True, audit_contract=CONTRACT, producer_v2_audit_equivalent=False,
        heldout_preserved=True, decontamination='exact normalized text and document, not semantic')
