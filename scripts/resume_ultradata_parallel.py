"""Resume a serial UltraData prefix using independently restartable file workers."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import os
from pathlib import Path
import sqlite3
from dfm12.io import atomic, load, rows, write_json, lock, file_hash
from scripts.prepare_dfm16_expansion import prepare_source, selected_files, ROOT
from scripts.prepare_dfm16_dyna import publish_audit_manifest

REPO = 'openbmb/UltraData-SFT-2605'
SLUG = REPO.replace('/', '__')


def work(args):
    root, index, entry = args
    part = root/'parallel-ultradata'/f'{index:04}'
    download = part/'downloads'/SLUG
    download.mkdir(parents=True, exist_ok=True)
    original = root/'downloads'/SLUG
    if not (download/'snapshot').exists():
        (download/'snapshot').symlink_to((original/'snapshot').resolve(), target_is_directory=True)
    pin = load(original/'source.json')
    pin['files'] = [entry]
    write_json(download/'source.json', pin)
    write_json(download/'status.json', {'phase': 'downloaded'})
    return index, prepare_source({'repo_id': REPO}, part)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=32)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    for key in ('TOKENIZERS_PARALLELISM',):
        os.environ[key] = 'false'
    for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'RAYON_NUM_THREADS'):
        os.environ[key] = '1'
    root = args.root
    out = root/'converted'/SLUG
    with lock(out/'.prepare.lock'):
        if (out/'conversion.json').exists():
            return
        checkpoint = out/'parallel-resume.json'
        if not checkpoint.exists():
            chunks = sorted((out/'chunks').glob('*.jsonl'))
            last = list(rows(chunks[-1]))[-1]['provenance']
            write_json(checkpoint, dict(prefix_chunks=[str(p.relative_to(out)) for p in chunks],
                last_provenance=last, serial_status=load(out/'status.json'),
                note='Preserve complete chunks; replay boundary file and deduplicate against prefix.'))
        saved = load(checkpoint)
        download = root/'downloads'/SLUG
        pin = load(download/'source.json')
        entries = {e['path']: e for e in pin['files']}
        files = selected_files(download, REPO)
        names = [str(p.relative_to(download/'snapshot')) for p in files]
        start = names.index(saved['last_provenance']['file'])
        jobs = [(root, i, entries[name]) for i, name in enumerate(names) if i >= start]
        completed = 0
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(work, job) for job in jobs]
            for future in as_completed(futures):
                index, result = future.result()
                completed += 1
                write_json(out/'parallel-status.json', dict(phase='converting', workers=args.workers,
                    files_done=completed, files_total=len(jobs), latest_file=names[index]))
                print(completed, '/', len(jobs), names[index], result['counts'], flush=True)
        # One owner performs global deduplication, in source order, after workers finish.
        db = sqlite3.connect(out/'parallel-seen.sqlite')
        db.execute('DROP TABLE IF EXISTS seen')
        db.execute('CREATE TABLE seen (id TEXT PRIMARY KEY)')
        chunks, total, duplicates = [], 0, 0
        def register(path, count):
            chunks.append(dict(job_id=f'input-{len(chunks):06}', input=str(path.relative_to(out)),
                rows=count, task='instruction', sha256=file_hash(path)))
        for name in saved['prefix_chunks']:
            path = out/name
            count = 0
            for row in rows(path):
                db.execute('INSERT INTO seen VALUES (?)', (row['id'],))
                count += 1
            total += count
            register(path, count)
        db.commit()
        for _, index, _ in jobs:
            part = root/'parallel-ultradata'/f'{index:04}'/'converted'/SLUG
            for chunk in load(part/'manifest.json')['chunks']:
                target = out/'parallel-chunks'/f'{index:04}-{Path(chunk["input"]).name}'
                count = 0
                with atomic(target) as stream:
                    for row in rows(part/chunk['input']):
                        if not db.execute('INSERT OR IGNORE INTO seen VALUES (?)', (row['id'],)).rowcount:
                            duplicates += 1
                            continue
                        stream.write(json.dumps(row, ensure_ascii=False)+'\n')
                        count += 1
                if count:
                    register(target, count)
                    total += count
            db.commit()
        db.close()
        publish_audit_manifest(out, chunks)
        result = dict(repo_id=REPO, phase='converted_pending_audit_and_generation',
            counts=dict(audit_candidates=total, replay_and_cross_file_duplicates=duplicates),
            training_ready=False, chunks=len(chunks), revision=pin['revision'],
            accounting='Per-file receipts plus preserved serial prefix; boundary replay is not new input.')
        write_json(out/'conversion.json', result)
        write_json(out/'status.json', result)


if __name__ == '__main__':
    main()
