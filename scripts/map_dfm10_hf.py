"""Map historical DFM10 task identities to freshly acquired HF source rows."""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.acquire_dfm10_hf import DEFAULT, save, sha
from scripts.dfm10_export_scope import inherited


def recover_tidsskrift_gold(source, target):
    """Invert the frozen builder's appended author-abstract subset, in order."""
    rows=[]
    with source.open() as inp:
        for line in inp:
            row=json.loads(line)
            if row.get('row_origin') == 'gold_author_abstract':
                row.pop('row_origin')
                row.pop('training_tokens', None)
                rows.append(row)
    if len(rows) != 9 or len({r['source_id'] for r in rows}) != 9:
        raise ValueError('Tidsskrift author-abstract subset differs from historical nine-row inventory')
    tmp=target.with_suffix('.tmp')
    with tmp.open('w') as out:
        for row in rows:
            out.write(json.dumps(row,ensure_ascii=False)+'\n')
    tmp.replace(target)
    return len(rows)


def build(work=DEFAULT):
    index = {}
    published_roots = {}
    for path in sorted((work / 'unpacked').glob('*/receipt.json')):
        rec = json.loads(path.read_text())
        if inherited(rec['repo_id']):
            continue
        published_roots[rec['source_root']] = dict(repo_id=rec['repo_id'], revision=rec['revision'], provenance=str(path))
        for rel, entry in rec['sources'].items():
            key = str(Path(rec['source_root']) / rel)
            index.setdefault(key, []).append({'path': str(path.parent / entry['file']), 'sha256': entry['sha256'], 'repo_id': rec['repo_id'], 'revision': rec['revision'], 'source_file': rel, 'rows': entry['rows'], 'format': 'restored_jsonl'})
    # The HF SFT export includes the nine original author abstracts appended
    # unchanged by dfm10_tidsskrift_grounded_model.py's build stage.
    tidsskrift = 'data/dfm10_tidsskrift_open_sft_source/tidsskrift_open_sft.jsonl'
    if tidsskrift in index:
        original=index[tidsskrift][0]
        target=work/'tidsskrift-author-abstracts.jsonl'
        receipt_path=work/'tidsskrift-author-abstracts-receipt.json'
        if not receipt_path.exists():
            source=Path(original['path'])
            if sha(source)!=original['sha256']:
                raise ValueError('Tidsskrift HF source changed')
            count=recover_tidsskrift_gold(source,target)
            save(receipt_path,{'source':original,'rows':count,'sha256':sha(target),'selection':'row_origin == gold_author_abstract; preserve export order'})
        receipt=json.loads(receipt_path.read_text())
        if receipt['source']!=original or sha(target)!=receipt['sha256']:
            raise ValueError('Tidsskrift subset receipt changed')
        key='data/dfm10_tidsskrift_sources/tidsskrift_open_article_summaries.jsonl'
        index[key]=[dict(original,path=str(target),sha256=receipt['sha256'],rows=9,provenance=str(receipt_path))]
    # Historical expanded Mimir tasks consumed export shards directly.
    for receipt_path in (work / 'acquisitions').glob('*dfm10-mimir-grounded-expanded-sft--*/acquisition-receipt.json'):
        rec = json.loads(receipt_path.read_text())
        for entry in rec['files']:
            suffix = Path(entry['file']).name.removeprefix('train-')
            key = 'data/dfm10_mimir_grounded_expanded_sources/mimir_grounded_expanded_sft__part-' + suffix
            index[key] = [{'path': str(receipt_path.parent / entry['file']), 'sha256': entry['sha256'], 'format': 'original', 'repo_id': rec['repo_id'], 'revision': rec['revision']}]
    # DOLCI's historical byte-based split used compact UTF-8 JSON lines.
    dolci = 'data/converted_sources/dolci_tool_use_repaired/dolci_instruct_sft_tool_use/data/train-00005-of-00006.jsonl'
    if dolci in index:
        original = index[dolci][0]
        stage = work / 'dolci-split'
        stage.mkdir(exist_ok=True)
        receipt_path = stage / 'receipt.json'
        if not receipt_path.exists():
            files=[]; handle=None; size=0
            try:
                with open(original['path']) as inp:
                    for line in inp:
                        raw=(json.dumps(json.loads(line), ensure_ascii=False, separators=(',', ':'))+'\n').encode()
                        if handle is None or size and size+len(raw)>256*1024*1024:
                            if handle: handle.close()
                            path=stage/f'train-00005-of-00006.part-{len(files):03d}.jsonl'
                            files.append(path); handle=path.open('wb'); size=0
                        handle.write(raw); size+=len(raw)
            finally:
                if handle: handle.close()
            save(receipt_path, {'source_sha256': original['sha256'], 'files': [{'path':str(p),'sha256':sha(p)} for p in files]})
        split=json.loads(receipt_path.read_text())
        if split['source_sha256'] != original['sha256']:
            raise ValueError('DOLCI split input changed')
        for entry in split['files']:
            key='data/dfm10_dolci_tool_use_repaired_sources/dolci_tool_use_repaired/dolci_instruct_sft_tool_use/data/'+Path(entry['path']).name
            index[key]=[dict(original, **entry, format='original', provenance=str(receipt_path))]

    upstream = work / 'upstream/converted'
    mappings, missing, ambiguous = [], [], []
    cfg = json.loads((ROOT / 'config/data/dfm10_hf_rebuild.json').read_text())
    converted = work / 'upstream/conversion-receipt.json'
    ups = json.loads(converted.read_text()) if converted.exists() else {}
    upstream_tasks = {'data__all_sft_splits.parquet': 'charter/all_sft_splits.parquet', **{t:t for t in ('alexandra_dacoref__train.jsonl', 'alexandra_nordjylland_original__train.jsonl', 'elrc_medical_en_da__train.parquet', 'nhs_synthetic_clinical_notes__train.parquet')}}
    # Explicitly fetched rebuild-ready inputs override export regrouping on a
    # future run. The current run does not fetch its own future publication.
    ready_path = work / 'rebuild-ready/opus_da_en_repaired/fetch-receipt.json'
    ready = json.loads(ready_path.read_text()) if ready_path.exists() else None
    ready_tasks = {}
    if ready:
        if ready.get('status') != 'downloaded_sha256_verified':
            raise ValueError('Rebuild-ready OPUS acquisition is unverified')
        ready_tasks = {entry['task']: entry for entry in ready['files']}
        if len(ready_tasks) != 64:
            raise ValueError('Rebuild-ready OPUS inventory differs')
    for task in cfg['tasks']:
        candidates = index.get(task['source'], [])
        if task['component'] == 'opus_da_en_repaired' and ready:
            entry = ready_tasks[task['task']]
            candidates = [{'path': str(ready_path.parent / entry['path']), 'sha256': entry['sha256'], 'format': 'original', 'repo_id': ready['repo_id'], 'revision': ready['revision']}]

        if task['task'] in upstream_tasks:
            rel = upstream_tasks[task['task']]
            if rel in ups.get('outputs', {}):
                candidates = [{'path': str(upstream / rel), 'sha256': ups['outputs'][rel], 'format': 'original', 'provenance': str(converted)}]
        if task['component'] == 'dbc_repaired':
            candidates = [{'path': str(ROOT / task['source']), 'sha256': task['sha256'], 'format': 'original', 'agreement_exception': 'DBC'}]
        # Empty task directories carry no training payload. Preserve their shape
        # only when this source root has a complete HF export and all historical
        # comparison arrays are empty; never infer missing nonempty text.
        if not candidates and str(Path(task['source']).parent) in published_roots:
            import numpy as np
            reference = ROOT / 'data/tokenized_dfm10' / task['task']
            fields = ('tokens', 'inst_start', 'inst_len', 'resp_start', 'resp_len')
            if all((reference / (f+'.npy')).exists() and np.load(reference / (f+'.npy'), mmap_mode='r').size == 0 for f in fields):
                empty = work / 'empty-hf-task.jsonl'
                if not empty.exists(): empty.write_text('')
                candidates = [dict(published_roots[str(Path(task['source']).parent)], path=str(empty), sha256='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', format='restored_jsonl', empty_task=True)]
        if len(candidates) == 1:
            mappings.append({'task': task['task'], 'component': task['component'], 'native': task['native'], 'input': candidates[0]})
        elif candidates:
            ambiguous.append({'task': task['task'], 'candidates': candidates})
        else:
            missing.append(task)
    report = {'status': 'mapped' if not missing and not ambiguous else 'incomplete', 'mapped': mappings, 'missing': missing, 'ambiguous': ambiguous}
    save(work / 'task-map.json', report)
    print('Mapped',len(mappings),'missing',len(missing),'ambiguous',len(ambiguous))
    return report


if __name__ == '__main__':
    build()
