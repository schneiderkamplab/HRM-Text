"""Recover ordered per-source rows exclusively from verified HF export shards."""
import argparse
from collections import OrderedDict
import fcntl
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.acquire_dfm10_hf import DEFAULT, safe_file, save, sha
from scripts.dfm10_export_scope import inherited


def restore(row):
    """Restore consumed fields; retain export provenance separately, never as data."""
    result = dict(row.get('metadata') or {})
    for key in ('messages', 'condition', 'tools', 'target_message_index'):
        if key in row:
            result[key] = row[key]
    return result


def unpack(receipt, work):
    source = Path(receipt['download_path'])
    if not source.resolve().is_relative_to((work / 'acquisitions').resolve()):
        raise ValueError('Input outside isolated acquisitions')
    manifest = source / 'metadata/manifest.json'
    if sha(manifest) != receipt['manifest_sha256']:
        raise ValueError('Remote manifest changed')
    identity = hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()
    target = work / 'unpacked' / source.name
    if (target / 'receipt.json').exists():
        if json.loads((target / 'receipt.json').read_text())['input_identity'] != identity:
            raise ValueError('Unpack receipt changed')
        return
    stage = target.with_name(target.name + '.partial')
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    files, handles = {}, OrderedDict()
    try:
        for entry in receipt['files']:
            path = safe_file(source, entry['file'])
            if path.stat().st_size != entry['bytes'] or sha(path) != entry['sha256']:
                raise ValueError('Unverified HF payload')
            with gzip.open(path, 'rt', encoding='utf-8') as inp:
                for line in inp:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    provenance = row['source']
                    rel, number = provenance['source_file'], provenance['source_row']
                    if not isinstance(number, int) or number < 1:
                        raise ValueError('Invalid row identity')
                    if rel not in files:
                        # Validate each source path once, not once per data row.
                        safe_file(stage, rel)
                        files[rel] = {'file': hashlib.sha256(rel.encode()).hexdigest()+'.jsonl', 'rows': 0, 'last_source_row': 0}
                    record = files[rel]
                    if number <= record['last_source_row']:
                        raise ValueError(f'Duplicate or reordered source row: {rel}:{number}')
                    record['rows'] += 1
                    record['last_source_row'] = number
                    if rel not in handles:
                        if len(handles) >= 32:
                            handles.popitem(last=False)[1].close()
                        handles[rel] = (stage / record['file']).open('a', encoding='utf-8')
                    handles.move_to_end(rel)
                    handles[rel].write(json.dumps(restore(row), ensure_ascii=False)+'\n')
    finally:
        for handle in handles.values():
            handle.close()
    expected_rows = json.loads(manifest.read_text()).get('rows')
    if expected_rows is not None and sum(x['rows'] for x in files.values()) != expected_rows:
        raise ValueError('Export row count differs from remote manifest')
    for item in files.values():
        item['sha256'] = sha(stage / item['file'])
    save(stage / 'receipt.json', {'input_identity': identity, 'repo_id': receipt['repo_id'], 'revision': receipt['revision'], 'source_root': json.loads(manifest.read_text())['source_root'], 'sources': files})
    stage.rename(target)
    print('Unpacked', receipt['repo_id'], len(files), 'source files', flush=True)


def run(work, follow):
    with (work / 'unpack.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        from scripts.fetch_dfm10_opus_rebuild import available
        use_ready_opus = available(work)
        while True:
            progress = json.loads((work / 'acquisition-progress.json').read_text())
            for receipt in progress['repositories']:
                if inherited(receipt['repo_id']):
                    continue
                if use_ready_opus and receipt['repo_id'] == 'schneiderkamplab/dfm10-opus-da-en-repaired':
                    continue
                unpack(receipt, work)
            from scripts.map_dfm10_hf import build
            build(work)
            if progress['complete'] or not follow:
                break
            time.sleep(20)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, default=DEFAULT)
    p.add_argument('--follow', action='store_true')
    args = p.parse_args()
    run(args.work.resolve(), args.follow)
