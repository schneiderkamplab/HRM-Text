"""Prepare immutable, license-separated BLKT packages; never publish or admit."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile

from .io import digest, file_hash, load, rows, write_json
from .records import validate_messages
from .wave_release import TRANSFORM_TASKS

REPO = 'VSSA-SDSA/LT_AI_BLKT'
REVISION = '4fa6c3894fd9f1f9f8db773ae844e126fa61f61d'
COMPONENT = 'transform-baltic_lt_blkt'
LICENSE_SHA = 'a8c692dbecb19e4822165afaa118247341067133156cfadd6668047b2ae55008'
RECEIPT_SHA = '215a052f388dc9034201437f6851b63d2632bed2a36dbe81ee75a45880e593b8'
CC_SHA = '28a9529c7d0bb4dc51f4bf5c116a3d16ef247a052f7591466768ddf563fd1cf5'
BUCKETS = {'NewGenLTU OpenRAIL-D': 'newgenltu', 'CC BY-SA 4.0': 'cc-by-sa-4.0'}
TERMINAL = {'accepted', 'accepted_repair', 'rejected', 'repair_rejected',
            'excluded_unreviewed', 'excluded_invalid_repair'}
CC_URL = 'https://creativecommons.org/licenses/by-sa/4.0/legalcode.en'


def checked(path, expected):
    if file_hash(path) != expected:
        raise ValueError(f'Hash mismatch: {path}')
    return Path(path)


def completed_snapshot(root):
    """Caller holds the existing repair lock; SQLite is opened read-only."""
    ledger = root / 'release' / COMPONENT
    status = load(ledger / 'status.json')
    seal = load(root / 'audit-ready' / COMPONENT / 'receipt.json')
    if (status.get('export_ready') is not True or status.get('terminal') is not True
            or status.get('component') != COMPONENT or seal.get('component') != COMPONENT):
        raise ValueError('Completed BLKT repair/audit ledger required')
    checked(seal['path'], seal['sha256'])
    if status['input_sha256'] != seal['sha256']:
        raise ValueError('Ledger input pin mismatch')
    originals = {}
    for row in rows(seal['path']):
        if row['id'] in originals:
            raise ValueError('Duplicate sealed ID')
        originals[row['id']] = row
    with sqlite3.connect((ledger / 'ledger.sqlite').resolve().as_uri() + '?mode=ro', uri=True) as db:
        records = db.execute('SELECT id,record,status,review FROM rows ORDER BY id').fetchall()
    counts = dict(Counter(r[2] for r in records))
    if (counts != status['counts'] or set(counts) - TERMINAL
            or len(records) != seal['counts']['ready']
            or status['input_rows'] != len(records)
            or {r[0] for r in records} != set(originals)):
        raise ValueError('Incomplete or inconsistent ledger population')
    accepted = []
    for key, raw, state, review in records:
        if state not in {'accepted', 'accepted_repair'}:
            continue
        row, audit = json.loads(raw), json.loads(review)
        original = originals[key]
        if row['id'] != key or audit.get('keep') is not True:
            raise ValueError('Missing exact positive review')
        if state == 'accepted' and row != original:
            raise ValueError('Unrepaired record changed')
        for field in ('provenance', 'task', 'language', 'component'):
            if row.get(field) != original.get(field):
                raise ValueError('Repair changed source identity')
        validate_messages(row['messages'])
        if (row['language'] != 'lt' or row['component'] != COMPONENT
                or row['task'] not in TRANSFORM_TASKS or row.get('tools')
                or row.get('reverse_messages') or row['messages'][-1]['role'] != 'assistant'
                or row['messages'][:-1] != original['messages'][:-1]):
            raise ValueError('Unexpected BLKT record contract')
        accepted.append((row, state, audit))
    if not accepted:
        raise ValueError('No accepted BLKT rows')
    return accepted, status, seal


def source_attributions(root, accepted):
    import pyarrow.parquet as pq
    receipt_path = root / 'receipts' / 'baltic_lt_blkt.json'
    checked(receipt_path, RECEIPT_SHA)
    receipt = load(receipt_path)
    if (receipt['repo'], receipt['revision']) != (REPO, REVISION):
        raise ValueError('Wrong BLKT source revision')
    pins = {str(Path(f['path']).resolve()): f['sha256'] for f in receipt['files']}
    license_path = root / 'downloads' / 'baltic_lt_blkt' / 'LICENSE.txt'
    checked(license_path, LICENSE_SHA)
    if pins.get(str(license_path.resolve())) != LICENSE_SHA:
        raise ValueError('License receipt mismatch')
    card = root / 'downloads' / 'baltic_lt_blkt' / 'README.md'
    checked(card, pins[str(card.resolve())])
    wanted = defaultdict(dict)
    for row, _, _ in accepted:
        p = row['provenance']
        path = str(Path(p['file']).resolve())
        if (p.get('source') != 'baltic_lt_blkt' or p.get('license') not in BUCKETS
                or path not in pins or p.get('file_sha256') != pins[path]
                or type(p.get('row')) is not int or p['row'] < 0):
            raise ValueError('Unknown source/license/ordinal')
        wanted[path].setdefault(p['row'], []).append(row)
    attribution = {}
    columns = ['id', 'url', 'license', 'source_name', 'source_id', 'document_type',
               'title', 'author', 'publication_date', 'source_file']
    for path, ordinals in wanted.items():
        checked(path, pins[path])
        offset = 0
        for batch in pq.ParquetFile(path).iter_batches(batch_size=4096, columns=columns):
            for i, raw in enumerate(batch.to_pylist(), offset):
                for row in ordinals.get(i, []):
                    p = row['provenance']
                    for field in ('url', 'license', 'source_name', 'source_id', 'document_type'):
                        if p.get(field) != raw[field]:
                            raise ValueError('Source row attribution mismatch: ' + field)
                    if (p['source_document_id'] != raw['id'] or not raw['id']
                            or not raw['source_id'] or not raw['source_name']):
                        raise ValueError('Missing document attribution')
                    attribution[row['id']] = dict(raw, repo=REPO, revision=REVISION,
                        file_sha256=pins[path], row=i, upstream_url_missing=not bool(raw['url']))
            offset += batch.num_rows
    if len(attribution) != len(accepted):
        raise ValueError('Source ordinal missing')
    return attribution, license_path, receipt_path


def prepare(root, output, cc_license, cc_sha256):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(root):
        raise ValueError('Use a fresh output directory outside the source root')
    # Open only an existing lock: never create or modify live release state.
    ledger = root / 'release' / COMPONENT
    if not (ledger / '.lock').is_file():
        raise ValueError('Completed release ledger absent; no preparation performed')
    with (ledger / '.lock').open('rb') as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        accepted, status, seal = completed_snapshot(root)
        attribution, license_path, receipt_path = source_attributions(root, accepted)
        if cc_sha256 != CC_SHA:
            raise ValueError('Hash mismatch: expected pinned official CC BY-SA legal text')
        cc_license = checked(cc_license, cc_sha256)
        cc_text = cc_license.read_text()
        if not all(s in cc_text for s in ('Attribution-ShareAlike 4.0 International',
                                          'Section 3', 'Section 8')):
            raise ValueError('Full CC BY-SA 4.0 legal text required')
        inputs = [ledger / 'status.json', root / 'audit-ready' / COMPONENT / 'receipt.json',
                  Path(seal['path']), receipt_path, license_path, cc_license, Path(__file__)]
        pins = {str(p.resolve()): file_hash(p) for p in inputs}
        output.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.' + output.name + '-', dir=output.parent))
        try:
            packages = []
            grouped = defaultdict(list)
            for row, state, audit in accepted:
                grouped[(row['task'], BUCKETS[row['provenance']['license']])].append((row, state, audit))
            date = datetime.now(timezone.utc).date().isoformat()
            for (task, bucket), items in sorted(grouped.items()):
                folder = stage / (task + '--' + bucket)
                (folder / 'data').mkdir(parents=True)
                shutil.copyfile(license_path if bucket == 'newgenltu' else cc_license, folder / 'LICENSE.txt')
                with (folder / 'data/train.jsonl').open('w') as out, (folder / 'attribution.jsonl').open('w') as attr:
                    for row, state, audit in items:
                        # Preserve the candidate payload; authorization is not manufactured here.
                        exported = dict(row, admission_authorized=False,
                            target_message_index=len(row['messages']) - 1,
                            export_preparation=dict(quality_status=state, audit=audit,
                                record_sha256=digest(row), license_bucket=bucket))
                        out.write(json.dumps(exported, ensure_ascii=False) + '\n')
                        attr.write(json.dumps(dict(candidate_id=row['id'], **attribution[row['id']]),
                                              ensure_ascii=False, default=str) + '\n')
                notice = (f'Derived from {REPO} revision {REVISION}. Prepared {date}.\n'
                    f'Modifications: source window selection, {task}, automated quality selection; '
                    'accepted repairs, if any, are identified per row. Original records are not overwritten.\n'
                    'Original author/title/source URL and row identifiers: attribution.jsonl. '
                    'Retain original attribution and notices. Automated review is not certified gold.\n')
                if bucket == 'newgenltu':
                    notice += ('NewGenLTU Open RAIL-D conditions, including Attachment A, apply. '
                        'Recipients must receive this license and its restrictions as downstream conditions. '
                        'Use limited by section 5(v); model privacy/output safeguards remain required.\n')
                else:
                    notice += (f'CC BY-SA 4.0: {CC_URL}. Adaptations retain ShareAlike; no additional '
                        'Open RAIL restrictions are imposed on this partition. Collection/row-term '
                        'interaction must be resolved before publication if ambiguous.\n')
                (folder / 'NOTICE.txt').write_text(notice)
                (folder / 'README.md').write_text('# BLKT ' + task + ' / ' + bucket + '\n\n' + notice +
                    '\nLocal publication preparation only; admission=false, uploaded=false. '
                    'No tokenization or truncation performed. Preserve native messages and supervise '
                    'target_message_index only. No exhaustive decontamination claim.\n')
                files = {str(p.relative_to(folder)): file_hash(p) for p in sorted(folder.rglob('*')) if p.is_file()}
                manifest = dict(task=task, license_bucket=bucket, rows=len(items), files=files,
                    repo=REPO, revision=REVISION, uploaded=False, admission_authorized=False,
                    publication_ready=False, source_license_sha256=LICENSE_SHA,
                    license_url=CC_URL if bucket != 'newgenltu' else
                    f'https://huggingface.co/datasets/{REPO}/blob/{REVISION}/LICENSE.txt',
                    rendered_tokens=sum(r['rendered_tokens'] for r, _, _ in items))
                write_json(folder / 'manifest.json', manifest)
                packages.append(dict(path=folder.name, manifest_sha256=file_hash(folder / 'manifest.json'), **manifest))
            for path, sha in pins.items():
                checked(path, sha)
            result = dict(schema='blkt-publication-preparation-v1', component=COMPONENT,
                packages=packages, accepted_rows=len(accepted), ledger_counts=status['counts'],
                input_sha256=seal['sha256'], inputs=pins, uploaded=False, admission_authorized=False,
                ledger_snapshot_sha256=digest([(r, s, a) for r, s, a in accepted]),
                remaining_constraints=['Scoped downstream license compliance and model privacy safeguards',
                    'Resolve collection/CC row-term interaction before publication where ambiguous',
                    'Explicit publisher integration and destination selection; no upload in this module'])
            write_json(stage / 'manifest.json', result)
            stage.rename(output)
            return result
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/dfm13/baltic'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cc-by-sa-license', type=Path, required=True)
    parser.add_argument('--cc-by-sa-sha256', required=True)
    args = parser.parse_args()
    result = prepare(args.root, args.output, args.cc_by_sa_license, args.cc_by_sa_sha256)
    print(json.dumps(dict(accepted_rows=result['accepted_rows'], packages=len(result['packages']))))


if __name__ == '__main__':
    main()
