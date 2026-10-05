"""Isolated, unadmitted LB source-view reserve from the existing capacity study."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sqlite3

from .io import atomic, digest, file_hash, load, rows, write_json
from .identity_extension import NativeRenderer
from .lb_seed_capacity import nonoverlap
from .multilingual_production_seeds import native_window


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text_key(text):
    return digest(' '.join(text.split()))


def validate_window(candidate, document, original, intervals):
    text = document['text']; start = candidate['offset']; end = candidate['end']
    require(type(start) is int and type(end) is int and 0 <= start < end <= len(text), 'Invalid offsets')
    require(text[start:end] == candidate['text'] and digest(candidate['text']) == candidate['id'], 'Window text drift')
    require(str(document['id']) == candidate['parent_document_id'], 'Wrong parent')
    require(document.get('url') == candidate['url'], 'URL drift')
    require(500 <= len(candidate['text']) <= 2400, 'Window length')
    require(digest(text[original['start']:original['end']]) == original['text_sha256'], 'Original seed/source mismatch')
    require(len(intervals) < 3 and all(nonoverlap((start,end), old) for old in intervals), 'Overlap or parent view cap')
    expected = native_window(text, digest(['lb-capacity-v1', str(document['id']), candidate['variant']]))
    require(expected == (candidate['text'], start), 'Extractor reproduction mismatch')
    require(sum(c.isalpha() for c in candidate['text']) / len(candidate['text']) >= .6, 'Text quality floor')


def build(root, study, base, metadata):
    root, study, base, metadata = map(Path, (root,study,base,metadata))
    require(not root.exists(), 'Use a fresh reserve root')
    receipt = load(study/'receipt.json'); base_receipt = load(base/'receipt.json')
    require(file_hash(base/'receipt.json') == receipt['existing_pool_receipt_sha256'], 'Base receipt drift')
    require(file_hash(base/'seeds.sqlite') == base_receipt['sha256'], 'Base seed bytes drift')
    require(file_hash(study/'candidate-windows.jsonl') == receipt['candidates_sha256'], 'Study candidates drift')
    license_evidence = load(study/'source-license-evidence.json')
    require(set(license_evidence['hf_card_licenses']) == {'cc-by-sa-3.0','gfdl'}, 'Unexpected rights evidence')
    info = load(metadata)['tokenizer_info']
    paths = [study/'receipt.json',study/'candidate-windows.jsonl',study/'source-license-evidence.json',
             base/'receipt.json',base/'seeds.sqlite',metadata,Path(info['tokenizer_path']),
             Path(info['chat_template_path']),Path(__file__),Path('dfm12/lb_seed_capacity.py'),
             Path('dfm12/multilingual_production_seeds.py'),Path('dfm12/identity_extension.py'),
             Path('scripts/tokenize_chat_template.py')]
    pins = {str(p.resolve()):file_hash(p) for p in paths if p != base/'seeds.sqlite'}
    pins[str((base/'seeds.sqlite').resolve())] = base_receipt['sha256']
    original = {}; seen = set()
    with sqlite3.connect((base/'seeds.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db:
        for raw, in db.execute("SELECT payload FROM seeds WHERE pool='lb'"):
            r = json.loads(raw); parent = str(r['source_document_id'])
            require(parent not in original, 'Base has multiple views; re-review parent caps')
            original[parent] = dict(start=r['offset'],end=r['offset']+len(r['text']),
                text_sha256=digest(r['text']),source_id=r['id'],source_sha256=r['source_sha256'])
            seen.add(text_key(r['text']))
    require(len(original) == receipt['counts']['existing_documents'], 'Original count mismatch')
    candidates = list(rows(study/'candidate-windows.jsonl'))
    require(len(candidates) == receipt['counts']['additional_window_same_document'], 'Study count mismatch')
    wanted = {c['parent_document_id'] for c in candidates}; documents = {}
    for name, sha in receipt['input_pins'].items():
        path = Path(name); require(file_hash(path) == sha, 'Source Parquet drift')
        pins[str(path.resolve())] = sha
        download = path.parent.parent/'wave4-download.json'; source = load(download)
        pins[str(download.resolve())] = file_hash(download)
        require(source['repo'] == license_evidence['repo'] and source['revision'] == license_evidence['revision'], 'Rights/source revision mismatch')
        for row in rows(path):
            parent = str(row['id'])
            if parent in wanted:
                require(parent not in documents, 'Ambiguous source document ID')
                documents[parent] = (row, sha, source, str(path.resolve()))
    require(set(documents) == wanted and wanted <= set(original), 'Missing/nonexisting parent')
    renderer = NativeRenderer(metadata)
    root.mkdir(parents=True)
    out = sqlite3.connect(root/'seeds.sqlite')
    out.executescript('''CREATE TABLE seeds(pool TEXT,seq INTEGER,source_id TEXT,payload TEXT,
      PRIMARY KEY(pool,seq),UNIQUE(pool,source_id));
      CREATE VIEW available_seeds AS SELECT pool AS language,pool,seq,source_id,payload FROM seeds;''')
    counts = Counter(); parents = Counter(); lengths = []; intervals = defaultdict(list)
    for parent, row in original.items(): intervals[parent].append((row['start'],row['end']))
    try:
        with atomic(root/'reserve.jsonl') as output, atomic(root/'validation-ledger.jsonl') as ledger:
            for c in candidates:
                parent = c['parent_document_id']; document, sha, source, path = documents[parent]
                require(c['kind'] == 'additional_window_same_document' and c['language'] == 'lb', 'Wrong candidate kind/language')
                require(c['source'] == source['repo'] and c['revision'] == source['revision']
                    and c['config'] == source['config'] and c['source_sha256'] == sha
                    and original[parent]['source_sha256'] == sha, 'Source lineage mismatch')
                validate_window(c, document, original[parent], intervals[parent])
                intervals[parent].append((c['offset'],c['end']))
                key = text_key(c['text']); reason = None; probe = None
                if key in seen: reason = 'exact_or_whitespace_duplicate'
                else:
                    try:
                        # Capacity probe only, not a generated/training conversation.
                        probe = renderer([dict(role='user',content=c['text']),dict(role='assistant',content=c['text'])])
                    except ValueError: reason = 'native_echo_probe_context_hold'
                if reason:
                    counts[reason] += 1
                else:
                    seen.add(key); counts['reserve_views'] += 1; parents[parent] += 1
                    lengths.append(probe['max_rendered_length'])
                    view_id = digest(['lb-reserve-view-v1',c['revision'],parent,c['offset'],c['end'],c['id']])
                    payload = dict(id=view_id,source_view_id=view_id,text=c['text'],language='lb',
                        source_document_id=parent,parent_document_id=parent,title=document.get('title'),
                        source=c['source'],revision=c['revision'],config=c['config'],source_file=path,
                        source_sha256=sha,source_record_sha256=digest(document),document_url=c['url'],
                        offset=c['offset'],end=c['end'],text_sha256=c['id'],
                        original_seed_id=original[parent]['source_id'],
                        original_window=[original[parent]['start'],original[parent]['end']],
                        license='cc-by-sa-3.0',source_card_licenses=license_evidence['hf_card_licenses'],
                        attribution_required=True,share_alike_required=True,
                        generation_and_review_required=True,admission_authorized=False,
                        distinct_document=False,max_total_views_per_parent_per_family=3)
                    encoded = json.dumps(payload,ensure_ascii=False)
                    output.write(encoded+'\n')
                    out.execute('INSERT INTO seeds VALUES(?,?,?,?)',('lb',counts['reserve_views'],view_id,encoded))
                ledger.write(json.dumps(dict(study_id=c['id'],parent_document_id=parent,
                    disposition=reason or 'validated_unadmitted_reserve',student_probe=probe),ensure_ascii=False)+'\n')
        out.commit()
        require(out.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'SQLite integrity')
    finally: out.close()
    manifest = dict(schema='lb-seed-reserve-v1',counts=dict(counts),study_candidates=len(candidates),
        original_lb_documents=len(original),reserve_parent_documents=len(parents),new_unique_documents=0,
        additional_views_per_parent_histogram=dict(Counter(parents.values())),pins=pins,
        output_pins={p.name:file_hash(p) for p in root.iterdir() if p.is_file()},
        native_probe=dict(basis='Full raw training template; user=source, assistant=source; diagnostic only',
            rows=len(lengths),max_rendered_tokens=max(lengths,default=0),limit=4096,
            future_generated_conversations_still_require_validation=True),
        duplicate_scope='Existing LB native seeds plus reserve, exact and whitespace-normalized text',
        disjoint_offsets_verified=True,extractor_reproduced=True,originals_modified=False,
        production_roots_changed=False,admission_authorized=False,gpu_calls=0,
        pending='Native/semantic screening and near-duplicate review; explicit successor admission only')
    write_json(root/'manifest.json',manifest)
    write_json(root/'receipt.json',dict(ready=True,counts={'lb':counts['reserve_views']},
        sha256=file_hash(root/'seeds.sqlite'),manifest_sha256=file_hash(root/'manifest.json'),
        admission_authorized=False,reserve_only=True,sufficient_for_full_targets=False))
    return {k:manifest[k] for k in ('counts','original_lb_documents','reserve_parent_documents','native_probe')}


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--study',type=Path,default=Path('data/dfm13/wave4/lb-seed-capacity-20261003'))
    p.add_argument('--base',type=Path,default=Path('data/dfm13/wave4/seeds'))
    p.add_argument('--metadata',type=Path,default=Path('data/sampled_dfm12_xl_epoch11_noidentity/metadata.json'))
    a=p.parse_args(); print(json.dumps(build(a.root,a.study,a.base,a.metadata),indent=2))
