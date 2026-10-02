"""Offline, journaled replacement of exactly the quarter controller pin."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sqlite3

from . import multilingual_quarter as quarter
from .io import digest, file_hash, load, lock, write_json

VERSION = 'multilingual-controller-upgrade-v1'
DIRECTORY = 'controller-upgrade-concurrency64-v1'
MARKER = 'controller-upgrade:concurrency64:v1'


def idle(db):
    if db.execute('SELECT 1 FROM groups WHERE active != 0 LIMIT 1').fetchone():
        raise ValueError('Active reservations: drain controller first')
    if db.execute("SELECT 1 FROM jobs WHERE status='running' LIMIT 1").fetchone():
        raise ValueError('Running jobs: drain controller first')


def state(root, db):
    result = dict(groups=[list(r) for r in db.execute('SELECT * FROM groups ORDER BY language,family')],
        jobs=[list(r) for r in db.execute('SELECT status,count(*) FROM jobs GROUP BY status')],
        config_sha256=file_hash(root/'config.json'))
    path = root/'spec-selections.sqlite'
    result['source_cursors'] = None
    if path.exists():
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as source:
            result['source_cursors'] = [list(r) for r in source.execute('SELECT * FROM cursors ORDER BY scope')]
    return result


def verify_old(root, old, proof):
    controller = str(Path(quarter.__file__).resolve())
    expected = old['implementation_pins'].get(controller)
    if not expected or proof.get('quarter_implementation_sha256') != expected or proof.get('manifest') != old:
        raise ValueError('Proof does not bind original controller pin and manifest')
    if old.get('version') != quarter.VERSION or old.get('policy') != quarter.POLICY or old.get('candidate_multiplier') != 6:
        raise ValueError('Original policy mismatch')
    checked = copy.deepcopy(old)
    checked['implementation_pins'][controller] = file_hash(controller)
    quarter.v6.verify_pins(root, checked)
    for path, expected in load(root/'pilot-import.json')['evidence_pins'].items():
        if file_hash(path) != expected:
            raise ValueError('Imported pilot evidence drift')


def archive(source, destination):
    if destination.exists():
        if file_hash(source) != file_hash(destination):
            raise ValueError('Archive collision: '+str(destination))
    else:
        shutil.copy2(source,destination)


def prepare_journal(root, proof_path, db):
    idle(db)
    old, proof = load(root/'manifest.json'), load(proof_path)
    old_sha = file_hash(root/'manifest.json')
    if proof.get('manifest_sha256') != old_sha or load(root/'seal.json').get('manifest_sha256') != old_sha:
        raise ValueError('Original proof/manifest/seal mismatch')
    row = db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()
    if not row or row[0] != old_sha:
        raise ValueError('Original SQLite seal mismatch')
    verify_old(root,old,proof)
    quarter.verify_ledger(db,old,load(root/'config.json'))
    directory = root/DIRECTORY
    directory.mkdir(exist_ok=True)
    for source, name in [(root/'manifest.json','old-manifest.json'),(root/'seal.json','old-seal.json'),
                         (proof_path,'pre-change-proof.json')]:
        archive(source,directory/name)
    new = copy.deepcopy(old)
    new['implementation_pins'][str(Path(quarter.__file__).resolve())] = file_hash(quarter.__file__)
    if new == old:
        raise ValueError('Controller pin is unchanged; no upgrade needed')
    staged = directory/'new-manifest.json'
    if staged.exists() and load(staged) != new:
        raise ValueError('Staged manifest drift')
    if not staged.exists():
        write_json(staged,new)
    journal = dict(version=VERSION,old_sha256=old_sha,new_sha256=file_hash(staged),
        proof_sha256=file_hash(proof_path),implementation_sha256=file_hash(__file__),
        controller_sha256=file_hash(quarter.__file__),preserved=state(root,db))
    write_json(directory/'journal.json',journal)
    return journal


def apply_ledger(root, db, journal):
    db.execute('BEGIN IMMEDIATE')
    try:
        idle(db)
        if state(root,db) != journal['preserved']:
            raise ValueError('Accepted counts, targets, jobs, source cursors or config changed')
        current = db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()[0]
        marker = db.execute('SELECT value FROM metadata WHERE key=?',(MARKER,)).fetchone()
        if current == journal['new_sha256']:
            if not marker or json.loads(marker[0]) != journal:
                raise ValueError('Committed upgrade marker mismatch')
        elif current == journal['old_sha256'] and marker is None:
            db.execute("UPDATE metadata SET value=? WHERE key='manifest_sha256'",(journal['new_sha256'],))
            db.execute('INSERT INTO metadata VALUES(?,?)',(MARKER,json.dumps(journal)))
        else:
            raise ValueError('Unknown SQLite upgrade state')
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise


def migrate(root, proof_path):
    root, proof_path = Path(root).resolve(), Path(proof_path).resolve()
    if not (root/'jobs.sqlite').is_file():
        raise ValueError('Existing production root required')
    with lock(root/'controller.lock'):
        db = sqlite3.connect(root/'jobs.sqlite',isolation_level=None)
        db.execute('PRAGMA synchronous=FULL')
        try:
            idle(db)
            directory = root/DIRECTORY
            path = directory/'journal.json'
            journal = load(path) if path.exists() else prepare_journal(root,proof_path,db)
            if journal.get('version') != VERSION or file_hash(__file__) != journal['implementation_sha256']:
                raise ValueError('Upgrade implementation drift')
            if file_hash(quarter.__file__) != journal['controller_sha256']:
                raise ValueError('Controller changed during upgrade')
            for path, sha in [(directory/'old-manifest.json',journal['old_sha256']),
                              (directory/'new-manifest.json',journal['new_sha256']),
                              (directory/'pre-change-proof.json',journal['proof_sha256']),
                              (proof_path,journal['proof_sha256'])]:
                if file_hash(path) != sha:
                    raise ValueError('Archived/staged/proof file drift: '+str(path))
            old, new = load(directory/'old-manifest.json'), load(directory/'new-manifest.json')
            proof = load(directory/'pre-change-proof.json')
            if proof.get('manifest_sha256') != journal['old_sha256'] or load(directory/'old-seal.json') != {'manifest_sha256':journal['old_sha256']}:
                raise ValueError('Archived proof/seal mismatch')
            expected = copy.deepcopy(old)
            expected['implementation_pins'][str(Path(quarter.__file__).resolve())] = journal['controller_sha256']
            if new != expected:
                raise ValueError('Only the quarter implementation pin may change')
            if file_hash(root/'manifest.json') not in (journal['old_sha256'],journal['new_sha256']):
                raise ValueError('Unexpected live manifest')
            if load(root/'seal.json') not in ({'manifest_sha256':journal['old_sha256']}, {'manifest_sha256':journal['new_sha256']}):
                raise ValueError('Unexpected live seal')
            verify_old(root,old,proof)
            quarter.verify_ledger(db,old,load(root/'config.json'))
            apply_ledger(root,db,journal)
            write_json(root/'manifest.json',new)
            write_json(root/'seal.json',{'manifest_sha256':journal['new_sha256']})
            quarter.verify(root)
            receipt = dict(version=VERSION,status='complete',old_sha256=journal['old_sha256'],
                new_sha256=journal['new_sha256'],journal_sha256=file_hash(directory/'journal.json'),
                preserved_sha256=digest(journal['preserved']),only_controller_pin_changed=True,
                processes_launched=False)
            write_json(directory/'completion.json',receipt)
            return receipt
        finally:
            db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--proof',type=Path,required=True)
    parser.add_argument('--apply',action='store_true',required=True)
    args = parser.parse_args()
    print(json.dumps(migrate(args.root,args.proof),indent=2))


if __name__ == '__main__':
    main()
