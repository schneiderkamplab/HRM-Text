"""Offline, exactly-once credit of verified first-pilot re-audit accepts.

No controller/server lifecycle. Requires the sealed completed re-audit API;
never imports historical keep booleans directly or edits pinned quarter inputs.
"""
import argparse
from collections import Counter
import copy
import hashlib
import importlib
import json
from pathlib import Path
import sqlite3

from . import multilingual_quarter as quarter
from .io import digest, file_hash, load, lock, write_json

VERSION = 'first-pilot-quarter-import-v1'
ORIGIN = 'first-pilot-reaudit'
ADAPTER = 'dfm12.multilingual_first_pilot_reaudit'
EXPECTED_SOURCE_ROWS = 33305


def verify_context(root, audit_root, manifest, db):
    context = load(audit_root / 'quarter-context.json')
    current_sha = file_hash(root / 'manifest.json')
    if context.get('manifest_sha256') == current_sha and context.get('manifest') == manifest:
        return
    # A quota-only migration does not invalidate already prepared review inputs.
    archive = root / 'retarget-tenth-v1'
    journal = load(archive / 'journal.json')
    old = load(archive / 'old-manifest.json')
    marker = db.execute("SELECT value FROM metadata WHERE key='retarget:tenth:v1'").fetchone()
    expected = copy.deepcopy(old)
    expected.update(milestone='tenth', milestone_divisor=10, target=385000)
    controller = str(Path(quarter.__file__).resolve())
    expected['implementation_pins'][controller] = file_hash(quarter.__file__)
    if (context.get('manifest') != old
            or context.get('manifest_sha256') != journal['old_sha256']
            or file_hash(archive / 'old-manifest.json') != journal['old_sha256']
            or current_sha != journal['new_sha256']
            or file_hash(root / 'config.json') != journal['config_sha256']
            or not marker or json.loads(marker[0]) != journal
            or manifest != expected):
        raise ValueError('Re-audit prepared against an incompatible campaign context')


def completed_audit(audit_root, adapter):
    manifest = adapter.verify(audit_root)
    if manifest.get('target') != EXPECTED_SOURCE_ROWS:
        raise ValueError('Expected all 33305 historical source rows')
    groups, statuses, checksum = Counter(), Counter(), hashlib.sha256()
    with sqlite3.connect((audit_root / 'reaudit.sqlite').as_uri() + '?mode=ro', uri=True) as db:
        for key, language, family, status, encoded in db.execute(
                'SELECT id,language,family,status,receipt_json FROM jobs ORDER BY id'):
            receipt = json.loads(encoded)
            if (status in ('pending','running') or receipt.get('terminal') is not True
                    or receipt.get('id') != key or receipt.get('status') != status):
                raise ValueError('Every re-audit row must be terminal before import')
            if load(adapter.directory(audit_root,key) / 'outcomes' / f'{key}.json') != receipt:
                raise ValueError('Terminal audit receipt/database mismatch')
            groups[(language,family)] += 1
            statuses[status] += 1
            checksum.update(digest([key,language,family,status,receipt]).encode())
    if sum(statuses.values()) != EXPECTED_SOURCE_ROWS:
        raise ValueError('Incomplete re-audit inventory')
    return dict(total=EXPECTED_SOURCE_ROWS, statuses=dict(statuses), inventory_sha256=checksum.hexdigest(),
                groups=[dict(language=k[0],family=k[1],count=v) for k,v in sorted(groups.items())])


def verified_items(audit_root, adapter):
    """Recheck exact prompt binding in addition to the strict CPU validator."""
    review = importlib.import_module(quarter.v6.REVIEW_MODULE)
    for key, candidate, receipt in adapter.iter_accepted(audit_root):
        folder = adapter.directory(audit_root,key)
        paths = [folder / kind / f'{key}.json' for kind in ('candidates','accepted','original','outcomes')]
        paths += [folder / kind / f'{key}-review.json' for kind in ('requests','stages')]
        request = load(folder / 'requests' / f'{key}-review.json')
        payload = quarter.v6.review_request(adapter.review_record(candidate),review)
        payload.update(temperature=0,frequency_penalty=.5)
        expected, strict_schema = quarter.v6.compact_request(payload)
        if request['request'] != expected or request['schema'] != strict_schema:
            raise ValueError('Saved review request is not bound to pinned candidate and strict prompt')
        original = load(folder / 'original' / f'{key}.json')
        if (receipt.get('status') != 'accepted' or receipt.get('terminal') is not True
                or receipt.get('eligible_for_quarter_import') is not True
                or receipt.get('effective_keep') is not True
                or receipt.get('fingerprint') != digest({k:candidate[k] for k in ('messages','tools')})):
            raise ValueError('Re-audit acceptance identity mismatch')
        source = receipt['source']
        if digest(original) != source['record_sha256'] or original['id'] != source['original_id']:
            raise ValueError('Original source digest mismatch')
        identity = dict(language=candidate['language'],family=candidate['family'],
                        slot=candidate['provenance']['slot'],candidate_sha256=receipt['candidate_sha256'])
        yield dict(key=key,candidate=candidate,source_identity=identity,
                   evidence_pins={str(path.resolve()):file_hash(path) for path in paths})


def assert_stopped(db, root):
    if db.execute('SELECT 1 FROM groups WHERE active != 0 LIMIT 1').fetchone():
        raise ValueError('Quarter has active reservations; drain controller first')
    if db.execute("SELECT 1 FROM jobs WHERE status='running' LIMIT 1").fetchone():
        raise ValueError('Quarter has running jobs; no recovery or process mutation by importer')
    import psutil
    for process in psutil.process_iter(['pid', 'cmdline']):
        command = process.info['cmdline'] or []
        if 'dfm12.multilingual_quarter' not in command or 'run' not in command:
            continue
        if '--root' not in command:
            raise ValueError('Quarter controller process has unresolvable root')
        index = command.index('--root') + 1
        if index >= len(command):
            raise ValueError('Quarter controller process has unresolvable root')
        if Path(command[index]).resolve() == root:
            raise ValueError(f'Quarter controller still alive: {process.pid}')


def pin_check(pins):
    if not isinstance(pins, dict) or not pins:
        raise ValueError('Nonempty evidence pins required')
    for path, expected in pins.items():
        if not Path(path).is_absolute() or not isinstance(expected, str) or file_hash(path) != expected:
            raise ValueError('Evidence pin mismatch: ' + str(path))


def immutable_json(path, value):
    if path.exists():
        if load(path) != value:
            raise ValueError('Staged immutable artifact drift: ' + str(path))
    else:
        write_json(path, value)
    return file_hash(path)


def validate_identity(item):
    """Adapter must supply strict raw-review and original snapshot evidence."""
    required = {'key', 'candidate', 'source_identity', 'evidence_pins'}
    if not isinstance(item, dict) or not required <= set(item):
        raise ValueError('Invalid verified re-audit record contract')
    candidate, source = item['candidate'], item['source_identity']
    if not isinstance(item['key'], str) or not item['key']:
        raise ValueError('Missing re-audit key')
    if not isinstance(source, dict) or set(source) != {'language', 'family', 'slot', 'candidate_sha256'}:
        raise ValueError('Source identity must name original language/family/slot/candidate SHA256')
    if type(source['slot']) is not int or source['slot'] < 0:
        raise ValueError('Invalid original slot')
    if candidate.get('language') != source['language'] or candidate.get('family') != source['family']:
        raise ValueError('Candidate/source identity mismatch')
    provenance = candidate.get('provenance')
    if (not isinstance(provenance, dict) or provenance.get('slot') != source['slot']
            or provenance.get('family') != source['family']
            or provenance.get('language_code') != source['language']):
        raise ValueError('Original candidate provenance mismatch')
    pin_check(item['evidence_pins'])
    # Verify original candidate bytes, not merely a caller-supplied content hash.
    candidates = [Path(path) for path, sha in item['evidence_pins'].items()
                  if sha == source['candidate_sha256']]
    if not candidates or not any(load(path) == candidate for path in candidates):
        raise ValueError('Original source candidate not bound to pinned snapshot')
    return candidate, source, digest({key: candidate[key] for key in ('messages', 'tools')})


def _stage(root, audit_root, manifest, rows, importer_pins, audit_summary=None):
    import_id = digest(dict(version=VERSION, campaign=manifest['campaign'],
                            audit_manifest_sha256=file_hash(audit_root / 'manifest.json')))
    directory = root / 'imports' / import_id
    plans, counts, seen = [], Counter(), set()
    for item in rows:
        candidate, source, fingerprint = validate_identity(item)
        if fingerprint in seen:
            raise ValueError('Duplicate fingerprint in re-audit passing rows')
        seen.add(fingerprint)
        job_id = digest(dict(origin=ORIGIN, campaign=manifest['campaign'], source_identity=source))
        accepted = copy.deepcopy(candidate)
        accepted['id'] = quarter.candidate_id(manifest['campaign'], fingerprint)
        provenance = dict(version=VERSION, import_id=import_id, audit_root=str(audit_root),
                          audit_key=item['key'], source_identity=source,
                          evidence_pins=item['evidence_pins'], importer_pins=importer_pins)
        workdir = directory / 'work' / job_id[:2] / job_id[2:4]
        path = workdir / 'accepted' / f'{job_id}.json'
        artifact_sha = immutable_json(path, accepted)
        outcome = dict(id=job_id, terminal=True, status='valid', effective_keep=True,
                       fingerprint=fingerprint, import_provenance=provenance)
        outcome_sha = immutable_json(workdir / 'outcomes' / f'{job_id}.json', outcome)
        plans.append(dict(id=job_id, language=source['language'], family=source['family'],
            slot=source['slot'], fingerprint=fingerprint, workdir=str(workdir),
            accepted_path=str(path), accepted_sha256=artifact_sha, outcome=outcome,
            outcome_sha256=outcome_sha, evidence_pins=item['evidence_pins']))
        counts[(source['language'], source['family'])] += 1
    journal = dict(version=VERSION, import_id=import_id, campaign=manifest['campaign'],
        audit_root=str(audit_root), audit_manifest_sha256=file_hash(audit_root / 'manifest.json'),
        quarter_manifest_sha256=file_hash(root / 'manifest.json'), importer_pins=importer_pins,
        accepted=len(plans), groups=[dict(language=k[0],family=k[1],count=v) for k,v in sorted(counts.items())],
        plans=plans, state='prepared-not-credited', targets_changed=False, audit_summary=audit_summary)
    journal_path = directory / 'journal.json'
    immutable_json(journal_path, journal)
    return journal_path, journal


def _validate_plan_files(journal):
    pin_check(journal['importer_pins'])
    for plan in journal['plans']:
        pin_check(plan['evidence_pins'])
        if file_hash(plan['accepted_path']) != plan['accepted_sha256']:
            raise ValueError('Accepted artifact drift')
        path = Path(plan['workdir']) / 'outcomes' / f"{plan['id']}.json"
        if file_hash(path) != plan['outcome_sha256']:
            raise ValueError('Staged outcome drift')


def _credit(db, root, journal_path, journal):
    """One transaction owns transfer, jobs, quotas and restart receipt."""
    metadata_key = VERSION + ':' + journal['import_id']
    _validate_plan_files(journal)
    db.execute('BEGIN IMMEDIATE')
    try:
        assert_stopped(db, root)
        previous = db.execute('SELECT value FROM metadata WHERE key=?', (metadata_key,)).fetchone()
        if previous:
            receipt = json.loads(previous[0])
            if receipt['journal_sha256'] != file_hash(journal_path):
                raise ValueError('Committed import journal drift')
            for plan in journal['plans']:
                owner = db.execute('SELECT owner FROM fingerprints WHERE fingerprint=?', (plan['fingerprint'],)).fetchone()
                job = db.execute('SELECT status,origin,fingerprint,workdir,outcome_json FROM jobs WHERE id=?', (plan['id'],)).fetchone()
                if (not owner or owner[0] != plan['id'] or not job or tuple(job[:4]) !=
                        ('accepted', ORIGIN, plan['fingerprint'], plan['workdir'])
                        or json.loads(job[4]) != plan['outcome']):
                    raise ValueError('Committed import ledger drift')
            db.execute('COMMIT')
            return receipt
        for group in journal['groups']:
            values = db.execute('SELECT target,accepted,active,attempts FROM groups WHERE language=? AND family=?',
                                (group['language'], group['family'])).fetchone()
            if (not values or values[2] or values[1] + group['count'] > values[0]
                    or values[3] > 6 * values[0]):
                raise ValueError('Import would exceed quota or existing candidate allowance is invalid')
        db.execute("CREATE INDEX IF NOT EXISTS quarter_import_accepted_fingerprint ON jobs(fingerprint) WHERE status='accepted'")
        for plan in journal['plans']:
            if (db.execute('SELECT 1 FROM jobs WHERE id=?', (plan['id'],)).fetchone()
                    or db.execute("SELECT 1 FROM jobs WHERE fingerprint=? AND status='accepted'",
                                  (plan['fingerprint'],)).fetchone()):
                raise ValueError('Existing job or accepted fingerprint cannot be credited twice')
            transferred = db.execute("UPDATE fingerprints SET owner=? WHERE fingerprint=? AND owner='prior-history'",
                                     (plan['id'], plan['fingerprint'])).rowcount
            if transferred != 1:
                raise ValueError('Fingerprint is unmatched or not owned by prior-history')
            db.execute('''INSERT INTO jobs(id,language,family,slot,status,origin,fingerprint,outcome_json,workdir)
                          VALUES(?,?,?,?,?,?,?,?,?)''',
                       (plan['id'], plan['language'], plan['family'], plan['slot'], 'accepted', ORIGIN,
                        plan['fingerprint'], json.dumps(plan['outcome'], ensure_ascii=False), plan['workdir']))
        for group in journal['groups']:
            db.execute('UPDATE groups SET accepted=accepted+? WHERE language=? AND family=?',
                       (group['count'],group['language'],group['family']))
        receipt = dict(version=VERSION, state='committed', import_id=journal['import_id'],
            campaign=journal['campaign'], accepted=journal['accepted'], groups=journal['groups'],
            journal=str(journal_path), journal_sha256=file_hash(journal_path),
            quarter_manifest_sha256=journal['quarter_manifest_sha256'],
            audit_manifest_sha256=journal['audit_manifest_sha256'], importer_pins=journal['importer_pins'],
            production_attempts_charged=0, targets_changed=False,
            reaudit_candidates=journal.get('audit_summary'),
            automatic_upload=False, automatic_export=False, training_changed=False)
        db.execute('INSERT INTO metadata VALUES (?,?)', (metadata_key, json.dumps(receipt)))
        db.execute('COMMIT')
        return receipt
    except BaseException:
        db.execute('ROLLBACK')
        raise


def import_finished(root, audit_root):
    root, audit_root = Path(root).resolve(), Path(audit_root).resolve()
    if not (root / 'jobs.sqlite').is_file():
        raise ValueError('Existing quarter ledger required; importer never initializes it')
    with lock(root / 'controller.lock'), lock(audit_root / 'reaudit.lock'):
        db = sqlite3.connect(root / 'jobs.sqlite', isolation_level=None, timeout=60)
        db.execute('PRAGMA synchronous=FULL')
        try:
            assert_stopped(db, root)
            manifest = quarter.verify(root)
            sealed = db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()
            if not sealed or sealed[0] != file_hash(root / 'manifest.json'):
                raise ValueError('Quarter SQLite manifest seal mismatch')
            adapter = importlib.import_module(ADAPTER)
            if not all(callable(getattr(adapter, name, None)) for name in ('verify','iter_accepted','validate_accepted')):
                raise ValueError('Re-audit importer API not frozen/ready; no writes allowed')
            summary = completed_audit(audit_root,adapter)
            verify_context(root, audit_root, manifest, db)
            importer_pins = {str(Path(path).resolve()): file_hash(path)
                             for path in (__file__, adapter.__file__)}
            journal_path, journal = _stage(root, audit_root, manifest,
                verified_items(audit_root,adapter), importer_pins, summary)
            if journal['accepted'] != summary['statuses'].get('accepted',0):
                raise ValueError('Accepted iterator omitted terminal passing rows')
            # Recheck immutable seals after potentially long staging, before credit.
            quarter.verify(root)
            if completed_audit(audit_root,adapter) != summary:
                raise ValueError('Re-audit completion changed during import')
            if file_hash(root / 'manifest.json') != journal['quarter_manifest_sha256']:
                raise ValueError('Quarter manifest changed during import')
            if file_hash(audit_root / 'manifest.json') != journal['audit_manifest_sha256']:
                raise ValueError('Re-audit manifest changed during import')
            receipt = _credit(db, root, journal_path, journal)
            immutable_json(journal_path.parent / 'receipt.json', receipt)
            return receipt
        finally:
            db.close()


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--quarter-root', type=Path, required=True)
    parser.add_argument('--audit-root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(import_finished(args.quarter_root, args.audit_root), indent=2))


if __name__ == '__main__':
    main()
