"""CPU accepted-subset exports from terminal compact DaLA audit snapshots."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import closing
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import unicodedata

from .io import digest, file_hash, load, lock, write_json

CONTRACT = 'dala-compact-whole-pair-four-labels-v1'
FIELDS = ('clean_valid', 'noisy_has_error', 'correction_complete', 'meaning_preserved')
PRODUCER = Path('/work/mimir/DaLA')
TOKENIZER = Path('data/dfm11_tokenizer/tokenizer.json')
TEMPLATE = Path('data/dfm11_tokenizer/chat_template.jinja')
ALL_INPUTS = Path('data/dfm13/dala-v2-audit34-with-recovery-v1/manifest.json')
AUDITS = [Path('data/dfm13/dala-v2-nl-fa-recovery-batch-audit-20261004-v1'),
          Path('data/dfm13/dala-v2-baseline-batch-audit-20261004-v1')]


def readonly(path):
    db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True, timeout=5)
    db.execute('PRAGMA query_only=ON')
    db.execute('PRAGMA cache_size=-16384')
    return db


def pin(path):
    return dict(path=str(Path(path).resolve()), sha256=file_hash(path))


def text_key(text):
    return hashlib.sha256(' '.join(unicodedata.normalize('NFC', text).split()).encode()).hexdigest()


def canonical(row, language, kind):
    if row.get('language') != language or kind not in ('pair', 'clean_control'):
        raise ValueError('Language/kind mismatch')
    value = dict(language=language, kind=kind, original=row['original'])
    if kind == 'pair':
        value['corrupted'] = row['corrupted']
    if any(not isinstance(value[k], str) or not value[k].strip()
           for k in ('original', 'corrupted') if k in value):
        raise ValueError('Empty sentence')
    value['id'] = digest(value)
    return value


def accepted(record, result, status):
    """A compact pass is explicitly NOT a producer per-edit audit receipt."""
    if status != 'done' or not isinstance(result, dict):
        return False
    control = record['kind'] == 'clean_control'
    labels = ['yes', *(['not_applicable']*3 if control else ['yes']*3)]
    return (result.get('id') == record['id'] and result.get('decision') == 'pass'
            and [result.get(k) for k in FIELDS] == labels
            and isinstance(result.get('reason'), str) and bool(result['reason'].strip())
            and result.get('producer_v2_audit_equivalent') is False
            and bool(result.get('raw_request_id')))


def split_name(row):
    split, view = row.get('split'), row.get('view')
    if split not in ('train', 'validation', 'test') or view not in ('representative', 'challenge'):
        raise ValueError('Missing or unknown split/view')
    if split == 'train' and view != 'representative':
        raise ValueError('Unexpected train view')
    return split+'_'+view


def task_row(row, record, task, prompts, evidence):
    clean = record['kind'] == 'clean_control'
    text = row['original'] if clean else row['corrupted']
    target = ('yes' if clean else 'no') if task == 'acceptability' else row['original']
    return dict(id=task+':'+record['id'], language=row['language'], task=task,
        messages=[dict(role='user', content=prompts[task]+'\n\n'+text),
                  dict(role='assistant', content=target)], target_message_index=1,
        split=row['split'], view=row['view'], source_label='correct' if clean else 'incorrect',
        variant='clean' if clean else 'corrupted', compact_audit=evidence,
        provenance=row, producer_v2_audit_equivalent=False)


def sources_from(manifest):
    if 'sources' in manifest:
        return manifest['sources']
    return [dict(component=e['language']+':'+kind, language=e['language'],
        kind='pair' if kind == 'pairs' else 'clean_control', path=e['files'][kind]['path'],
        sha256=e['files'][kind]['sha256'], rows=e['counts'][kind],
        receipt=e['breadth']['path'], receipt_sha256=e['breadth']['sha256'])
        for e in manifest['languages'] for kind in ('controls', 'pairs')]


def snapshot(audit, sources, root):
    """One read transaction binds terminal aliases and decisions; never writes live DB."""
    config = pin(audit/'config.json')
    output = root/'decisions.sqlite'
    root.mkdir(parents=True, exist_ok=False)
    counts = Counter()
    with closing(readonly(audit/'jobs.sqlite')) as src, closing(sqlite3.connect(output)) as dst:
        dst.execute('CREATE TABLE decisions(component TEXT,ordinal INTEGER,id TEXT,record TEXT,status TEXT,result TEXT,alias TEXT,PRIMARY KEY(component,ordinal))')
        src.execute('BEGIN')
        for source in sources:
            state = src.execute('SELECT sha256,complete,input_rows,quarantined FROM sources WHERE component=?', (source['component'],)).fetchone()
            if state != (source['sha256'], 1, source['rows'], 0):
                return None
            n = 0
            query = '''SELECT a.ordinal,a.id,j.record,j.status,j.result,a.provenance
                       FROM aliases a LEFT JOIN jobs j ON j.id=a.id
                       WHERE a.component=? ORDER BY a.ordinal'''
            for ordinal, key, record, status, result, alias in src.execute(query, (source['component'],)):
                if ordinal != n or status not in ('done', 'failed'):
                    return None
                dst.execute('INSERT INTO decisions VALUES(?,?,?,?,?,?,?)',
                    (source['component'], ordinal, key, record, status, result, alias))
                counts[source['component']+':'+status] += 1
                n += 1
                if n % 4096 == 0:
                    dst.commit()
            if n != source['rows']:
                raise ValueError('Incomplete alias coverage')
        src.rollback()
        dst.commit()
    if pin(audit/'config.json') != config:
        raise ValueError('Audit configuration changed during snapshot')
    receipt = dict(contract=CONTRACT, consistent_read_transaction=True, terminal=True,
        audit_root=str(audit.resolve()), config=config, configuration=load(audit/'config.json'),
        decisions=pin(output), sources=sources, counts=dict(counts), captured_at=time.time(),
        config_history=[pin(p) for p in sorted(audit.glob('config-before-extension-*.json'))],
        producer_v2_audit_equivalent=False)
    write_json(root/'snapshot.json', receipt)
    return receipt


def inventory_for(language, recovery):
    if recovery:
        path = PRODUCER/f'la_output/v2/grammar-recovery-production-v3/{language}/inventory.json'
    else:
        options = [PRODUCER/'la_output/v2/additional-production-v1/production-inventory.json',
                   PRODUCER/f'la_output/v2/wave4-production-v1/{language}/inventory.json']
        for path in options:
            if path.exists() and any(e['language'] == language for e in load(path)['languages']):
                break
        else:
            raise ValueError('No producer prompt/prior inventory: '+language)
    entry = next(e for e in load(path)['languages'] if e['language'] == language)
    prior = entry['prior_release']
    if file_hash(prior['path']) != prior['sha256']:
        raise ValueError('Prior index drift')
    return entry, pin(path)


def build_heldout(sources, path):
    db = sqlite3.connect(path)
    db.executescript('CREATE TABLE held(kind TEXT,key TEXT,PRIMARY KEY(kind,key)) WITHOUT ROWID; CREATE TABLE seen(kind TEXT,key TEXT,PRIMARY KEY(kind,key)) WITHOUT ROWID;')
    count = 0
    for source in sources:
        if file_hash(source['path']) != source['sha256']:
            raise ValueError('Input drift')
        n = 0
        with gzip.open(source['path'], 'rt') as f:
            for line in f:
                row = json.loads(line); split_name(row); n += 1
                if row['split'] == 'train':
                    continue
                values = [('text', text_key(row[k])) for k in ('original','corrupted') if k in row]
                values += [('document', row[k]) for k in ('document_id','document_sha256') if row.get(k)]
                db.executemany('INSERT OR IGNORE INTO held VALUES(?,?)', values)
                count += 1
                if count % 4096 == 0:
                    db.commit()
        if n != source['rows']:
            raise ValueError('Input count mismatch')
    db.commit()
    return db, count


def exclusion(row, kind, prior, held):
    original = row['original']; noisy = row.get('corrupted', original)
    if not row.get('document_id') or row.get('document_lineage') == 'unknown':
        return 'unknown_document'
    split_name(row)
    texts = {text_key(original), text_key(noisy)}
    if kind == 'pair' and original == noisy:
        return 'unchanged_noisy_pair'
    prior_table = 'clean' if kind == 'clean_control' else 'pairs'
    key = text_key(original) if kind == 'clean_control' else digest([text_key(original), text_key(noisy)])
    if prior.execute(f'SELECT 1 FROM {prior_table} WHERE key=?', (key,)).fetchone():
        return 'prior_duplicate'
    for value in texts:
        if prior.execute('SELECT 1 FROM texts WHERE key=? AND split<>? LIMIT 1', (value,row['split'])).fetchone():
            return 'prior_split_conflict'
    if prior.execute('SELECT 1 FROM documents WHERE key=? AND split<>? LIMIT 1', (row['document_id'],row['split'])).fetchone():
        return 'prior_document_conflict'
    if row['split'] == 'train':
        values = [('text',v) for v in texts]+[('document',row[k]) for k in ('document_id','document_sha256') if row.get(k)]
        if any(held.execute('SELECT 1 FROM held WHERE kind=? AND key=?', v).fetchone() for v in values):
            return 'raw_heldout_overlap'
    # Preserve repeated correct originals across different noisy pairs, but not duplicate controls/inputs.
    identity = text_key(original if kind == 'clean_control' else noisy)
    if kind == 'pair' and held.execute("SELECT 1 FROM seen WHERE kind='clean_control' AND key=?", (identity,)).fetchone():
        return 'contradictory_clean_noisy_label'
    if held.execute('SELECT 1 FROM seen WHERE kind=? AND key=?', (kind,identity)).fetchone():
        return 'duplicate_control_or_noisy_input'
    held.execute('INSERT INTO seen VALUES(?,?)', (kind,identity))
    return None


def finalize(job):
    root, universe, tokenize = Path(job[0]), job[1], job[2]
    snap = load(root/'snapshot.json'); language = snap['sources'][0]['language']
    snapshot_sha = file_hash(root/'snapshot.json')
    if file_hash(root/'decisions.sqlite') != snap['decisions']['sha256']:
        raise ValueError('Frozen decisions changed')
    recovery = ':recovery-v3:' in snap['sources'][0]['component']
    inventory, inventory_pin = inventory_for(language, recovery)
    for s in snap['sources']:
        identity = load(Path(s['path']).parent/'identity.json')
        if identity['prior_index_sha256'] != inventory['prior_release']['sha256']:
            raise ValueError('Source/prior identity mismatch')
    relevant = [s for s in universe if s['language'] == language]
    held, held_count = build_heldout(relevant, root/'heldout.sqlite')
    db = readonly(root/'decisions.sqlite'); prior = readonly(inventory['prior_release']['path'])
    counts = Counter(); handles = {}; paths = {}; row_counts = Counter()
    def emit(relative, row):
        if relative not in handles:
            path = root/relative; path.parent.mkdir(parents=True, exist_ok=True)
            handles[relative] = gzip.open(path, 'wt', encoding='utf-8', compresslevel=1)
            paths[relative] = path
        handles[relative].write(json.dumps(row, ensure_ascii=False)+'\n')
        row_counts[relative] += 1
    try:
        for source in snap['sources']:
            if file_hash(source['path']) != source['sha256']:
                raise ValueError('Source changed')
            cursor = db.execute('SELECT ordinal,id,record,status,result,alias FROM decisions WHERE component=? ORDER BY ordinal', (source['component'],))
            n = 0
            with gzip.open(source['path'], 'rt') as f:
                for ordinal, line in enumerate(f):
                    row = json.loads(line); record = canonical(row, language, source['kind'])
                    saved = next(cursor, None)
                    if saved is None or saved[0] != ordinal or saved[1] != record['id'] or json.loads(saved[2]) != record or json.loads(saved[5])['row_sha256'] != digest(row):
                        raise ValueError('Snapshot/source/alias mismatch')
                    result = json.loads(saved[4]) if saved[4] else None
                    n += 1; counts['input:'+source['kind']] += 1
                    reason = None
                    if not accepted(record, result, saved[3]):
                        reason = 'audit_'+(saved[3] if saved[3] != 'done' else (result or {}).get('decision','invalid'))
                    if reason is None:
                        reason = exclusion(row, source['kind'], prior, held)
                    if reason:
                        counts['excluded:'+reason] += 1
                        emit('exclusions.jsonl.gz', dict(component=source['component'], ordinal=ordinal,
                            id=record['id'], row_sha256=digest(row), reason=reason, split=row['split']))
                        continue
                    split = split_name(row)
                    counts['accepted:'+split+':'+source['kind']] += 1
                    evidence = dict(contract=CONTRACT, decision=result, snapshot_sha256=snapshot_sha,
                        source_component=source['component'], ordinal=ordinal, source_row_sha256=digest(row),
                        producer_v2_audit_equivalent=False)
                    for task in ('acceptability','correction'):
                        value = task_row(row, record, task, inventory['profile']['prompts'], evidence)
                        emit(f'exports/{task}/{split}.jsonl.gz', value)
                        if row['split'] == 'train':
                            part = counts['train:'+task]//25000
                            emit(f'train/{task}/part-{part:05d}.jsonl.gz', value)
                            counts['train:'+task] += 1
                    if n % 4096 == 0:
                        held.commit()
            if n != source['rows'] or next(cursor, None) is not None:
                raise ValueError('Export coverage mismatch')
    finally:
        for handle in handles.values(): handle.close()
        held.commit(); held.close(); db.close(); prior.close()
    receipt = dict(status='accepted_subset_exported', contract=CONTRACT, language=language,
        producer_v2_audit_equivalent=False, snapshot=pin(root/'snapshot.json'), counts=dict(counts),
        producer_inventory=inventory_pin, prior_index=inventory['prior_release'],
        heldout_sources=relevant, heldout_rows=held_count, heldout_index=pin(root/'heldout.sqlite'),
        files=[dict(pin(p), rows=row_counts[k], relative=k) for k,p in paths.items()],
        balanced_producer_release=False, automatic_model_judgments=True,
        limitations=['Exact normalized text/document overlap; not semantic decontamination',
                     'Compact whole-pair review, not isolated per-edit certification'],
        tokenizer_inputs_train_only=True, publication_performed=False)
    write_json(root/'export.json', receipt)
    print('EXPORTED', root.name, dict(counts), flush=True)
    components = []
    if tokenize:
        import numpy as np
        for task in ('acceptability','correction'):
            if not counts['train:'+task]: continue
            output = root/'tokenized'/task
            subprocess.run([sys.executable, 'scripts/tokenize_chat_template.py', str(root/'train'/task),
                '--output-dir', str(output), '--tokenizer-path', str(TOKENIZER), '--chat-template', str(TEMPLATE),
                '--workers', '1', '--max-seq-len', '4096', '--preserve-first-user'], check=True,
                stdout=(root/(task+'-tokenization.log')).open('w'), stderr=subprocess.STDOUT)
            completion = load(output/'completion.json')
            if completion['rows'] != counts['train:'+task] or completion['skipped_rows_this_run']:
                raise ValueError('Tokenization dropped rows; no registry admission')
            arrays = {}; rows = tokens = 0
            for part in output.iterdir():
                if not part.is_dir(): continue
                il = np.load(part/'inst_len.npy', mmap_mode='r'); rl = np.load(part/'resp_len.npy', mmap_mode='r')
                if len(il) != len(rl) or np.any(rl <= 0) or np.any(il+rl > 4096):
                    raise ValueError('Invalid token lengths')
                count = int(il.sum())+int(rl.sum())
                if len(np.load(part/'tokens.npy', mmap_mode='r')) != count:
                    raise ValueError('Token array mismatch')
                rows += len(rl); tokens += count
                arrays.update({str(p.resolve()): file_hash(p) for p in part.glob('*.npy')})
            if rows != counts['train:'+task]: raise ValueError('Token rows mismatch')
            components.append(dict(name='dfm13_dala_v2_compact_'+root.name.replace('-','_')+'_'+task,
                language=language, task=task, status='accepted_local_tokenized', repeat=1,
                audit_contract=CONTRACT, producer_v2_audit_equivalent=False, split='train',
                tokenized_path=str(output.resolve()), rows=rows, tokens=tokens, array_pins=arrays,
                export_receipt=pin(root/'export.json'), snapshot=pin(root/'snapshot.json'),
                tokenizer=pin(TOKENIZER), template=pin(TEMPLATE), uploaded=False,
                canonical_assembly_pending=True))
    result = dict(status='complete_train_only' if tokenize else 'exported_not_tokenized',
        components=components, export=pin(root/'export.json'), contract=CONTRACT)
    write_json(root/'integration.json', result)
    return result


def run(root, workers, tokenize):
    if not 1 <= workers <= 8: raise ValueError('Use1..8 workers; token subprocesses keep total <=16')
    os.environ.update(CUDA_VISIBLE_DEVICES='', TOKENIZERS_PARALLELISM='false', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    with lock(root/'.lock'):
        if (root/'plan.json').exists(): raise ValueError('Existing pipeline; use a new immutable root')
        universe = load(ALL_INPUTS)['sources']
        write_json(root/'ownership.json', dict(pid=os.getpid(), integration_root=str(root.resolve()),
            central_registry_owner='Tesla', modifies_central_registry=False, gpu_actions=False))
        selected = []; waiting = []
        for audit in AUDITS:
            config = load(audit/'config.json')
            if file_hash(config['manifest']) != config['manifest_sha256']: raise ValueError('Audit manifest drift')
            sources = sources_from(load(config['manifest']))
            grouped = {}
            for source in sources: grouped.setdefault(source['language'], []).append(source)
            for lang, group in grouped.items():
                suffix = 'recovery' if ':recovery-v3:' in group[0]['component'] else 'baseline'
                target = root/'groups'/(lang+'-'+suffix)
                result = snapshot(audit, group, target)
                if result is None:
                    waiting.append(dict(language=lang, pool=suffix, reason='not_terminal_or_incomplete'))
                else:
                    selected.append(str(target.resolve()))
                    print('SNAPSHOT', target.name, result['counts'], flush=True)
        write_json(root/'plan.json', dict(selected=selected, waiting=waiting, all_inputs=pin(ALL_INPUTS),
            code=pin(__file__), workers=workers, tokenize=tokenize))
        done = []; errors = []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(finalize, (p,universe,tokenize)):p for p in selected}
            for future in as_completed(futures):
                try: done.append(future.result())
                except Exception as exc:
                    errors.append(dict(group=futures[future], error=repr(exc)))
                    print('FAILED', futures[future], repr(exc), flush=True)
                components = [c for r in done for c in r['components']]
                write_json(root/'registry.json', dict(schema=CONTRACT, additions=components,
                    inherits='dfm12', local_only=True, central_assembly_owner='Tesla'))
                write_json(root/'progress.json', dict(completed=len(done), errors=errors,
                    selected=len(selected), waiting=waiting, components=len(components)))
        write_json(root/'complete.json', dict(success=not errors, completed=len(done), errors=errors,
            waiting=waiting, registry=pin(root/'registry.json'), gpu_actions=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--tokenize', action='store_true')
    args = parser.parse_args()
    run(args.root, args.workers, args.tokenize)
