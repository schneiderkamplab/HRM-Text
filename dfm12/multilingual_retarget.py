"""Explicit offline quarter-to-tenth migration; never launch or stop processes."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sqlite3

from . import multilingual_quarter as quarter
from .io import file_hash, load, lock, write_json

VERSION = 'multilingual-offline-retarget-tenth-v1'


def idle(db):
    if db.execute('SELECT 1 FROM groups WHERE active != 0 LIMIT 1').fetchone():
        raise ValueError('Active reservations: drain controller before retarget')
    if db.execute("SELECT 1 FROM jobs WHERE status='running' LIMIT 1").fetchone():
        raise ValueError('Running jobs: drain controller before retarget')


def verify_old_pins(root, old, proof):
    controller = str(Path(quarter.__file__).resolve())
    expected = old['implementation_pins'].get(controller)
    if not expected or proof.get('quarter_implementation_sha256') != expected or proof.get('manifest') != old:
        raise ValueError('Pre-change verification proof does not bind original controller')
    if old.get('version') != quarter.VERSION or old.get('policy') != quarter.POLICY:
        raise ValueError('Original policy mismatch')
    if old.get('target') != 962500 or old.get('milestone','quarter') != 'quarter':
        raise ValueError('Only explicit quarter-to-tenth migration supported')
    if old.get('candidate_multiplier') != 6:
        raise ValueError('Candidate guard mismatch')
    checked = copy.deepcopy(old)
    checked['implementation_pins'][controller] = file_hash(controller)
    quarter.v6.verify_pins(root, checked)
    for path, expected in load(root/'pilot-import.json')['evidence_pins'].items():
        if file_hash(path) != expected:
            raise ValueError('Historical pilot evidence drift')


def _archive(source, destination):
    if destination.exists():
        if file_hash(source) != file_hash(destination):
            raise ValueError('Archive collision: '+str(destination))
    else:
        shutil.copy2(source,destination)


def prepare_journal(root, proof_path, db):
    proof = load(proof_path)
    old = load(root/'manifest.json')
    old_sha = file_hash(root/'manifest.json')
    if proof.get('manifest_sha256') != old_sha or load(root/'seal.json')['manifest_sha256'] != old_sha:
        raise ValueError('Original manifest/seal/proof mismatch')
    seal = db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()
    if not seal or seal[0] != old_sha:
        raise ValueError('Original SQLite seal mismatch')
    verify_old_pins(root,old,proof)
    config = load(root/'config.json')
    quarter.verify_ledger(db,old,config)
    quotas = quarter.milestone_targets(config,'tenth',divisor=10)
    targets = {(q['language'],q['family']):q['accepted_target'] for q in quotas}
    for language,family,accepted,active,attempts in db.execute('SELECT language,family,accepted,active,attempts FROM groups'):
        target = targets[(language,family)]
        if accepted+active > target or attempts > 6*target:
            raise ValueError('Existing accepted/active/attempts exceed new quota')
    directory = root/'retarget-tenth-v1'
    directory.mkdir(exist_ok=True)
    _archive(root/'manifest.json',directory/'old-manifest.json')
    _archive(root/'seal.json',directory/'old-seal.json')
    _archive(proof_path,directory/'pre-change-proof.json')
    new = copy.deepcopy(old)
    new.update(milestone='tenth',milestone_divisor=10,target=385000)
    new['implementation_pins'][str(Path(quarter.__file__).resolve())] = file_hash(quarter.__file__)
    staged = directory/'new-manifest.json'
    if staged.exists() and load(staged) != new:
        raise ValueError('Staged manifest drift')
    if not staged.exists():
        write_json(staged,new)
    journal = dict(version=VERSION,old_sha256=old_sha,new_sha256=file_hash(staged),
        config_sha256=file_hash(root/'config.json'),proof_sha256=file_hash(proof_path),
        implementation_sha256=file_hash(__file__),controller_sha256=file_hash(quarter.__file__),
        quotas=quotas,source_milestone='quarter',destination_milestone='tenth',
        target=385000,estimated_training_tokens=sum(q['estimated_training_tokens'] for q in quotas))
    write_json(directory/'journal.json',journal)
    return journal


def apply_ledger(db, root, journal):
    """Commit all quotas plus the new seal together; filesystem follows safely."""
    db.execute('BEGIN IMMEDIATE')
    try:
        idle(db)
        current = db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()[0]
        if current == journal['new_sha256']:
            expected = {(q['language'],q['family']):q['accepted_target'] for q in journal['quotas']}
            actual = {(r[0],r[1]):r[2] for r in db.execute('SELECT language,family,target FROM groups')}
            if actual != expected:
                raise ValueError('Committed retarget ledger drift')
            marker = db.execute("SELECT value FROM metadata WHERE key='retarget:tenth:v1'").fetchone()
            if not marker or json.loads(marker[0]) != journal:
                raise ValueError('Retarget transaction marker mismatch')
            db.execute('COMMIT')
            return
        if current != journal['old_sha256']:
            raise ValueError('Unknown SQLite seal during retarget')
        for quota in journal['quotas']:
            target = quota['accepted_target']
            updated = db.execute('''UPDATE groups SET target=? WHERE language=? AND family=?
                AND active=0 AND accepted<=? AND attempts<=?''',
                (target,quota['language'],quota['family'],target,6*target)).rowcount
            if updated != 1:
                raise ValueError('Existing accepted/active/attempts exceed new quota or group missing')
        db.execute("UPDATE metadata SET value=? WHERE key='manifest_sha256'",(journal['new_sha256'],))
        db.execute("INSERT INTO metadata VALUES('retarget:tenth:v1',?)",(json.dumps(journal),))
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise


def migrate(root, proof_path=None):
    root = Path(root).resolve()
    proof_path = Path(proof_path).resolve() if proof_path else root/'pre-tenth-verification.json'
    if not (root/'jobs.sqlite').is_file():
        raise ValueError('Existing production root required')
    with lock(root/'controller.lock'):
        db = sqlite3.connect(root/'jobs.sqlite',isolation_level=None)
        db.execute('PRAGMA synchronous=FULL')
        try:
            idle(db)
            directory = root/'retarget-tenth-v1'
            path = directory/'journal.json'
            journal = load(path) if path.exists() else prepare_journal(root,proof_path,db)
            if journal.get('version') != VERSION or file_hash(__file__) != journal['implementation_sha256']:
                raise ValueError('Migration implementation drift')
            if file_hash(quarter.__file__) != journal['controller_sha256']:
                raise ValueError('Controller changed during migration')
            if file_hash(root/'config.json') != journal['config_sha256']:
                raise ValueError('Provider config must remain unchanged')
            if file_hash(directory/'pre-change-proof.json') != journal['proof_sha256']:
                raise ValueError('Archived proof drift')
            if file_hash(directory/'old-manifest.json') != journal['old_sha256']:
                raise ValueError('Archived manifest drift')
            if load(directory/'old-seal.json')['manifest_sha256'] != journal['old_sha256']:
                raise ValueError('Archived seal drift')
            if file_hash(directory/'new-manifest.json') != journal['new_sha256']:
                raise ValueError('Staged manifest drift')
            old,new = load(directory/'old-manifest.json'),load(directory/'new-manifest.json')
            expected = copy.deepcopy(old)
            expected.update(milestone='tenth',milestone_divisor=10,target=385000)
            expected['implementation_pins'][str(Path(quarter.__file__).resolve())] = journal['controller_sha256']
            if new != expected or journal['quotas'] != quarter.milestone_targets(load(root/'config.json'),'tenth',10):
                raise ValueError('Unauthorized retarget manifest or quota change')
            if file_hash(root/'manifest.json') not in (journal['old_sha256'],journal['new_sha256']):
                raise ValueError('Unexpected live manifest')
            if load(root/'seal.json')['manifest_sha256'] not in (journal['old_sha256'],journal['new_sha256']):
                raise ValueError('Unexpected live seal')
            verify_old_pins(root,old,load(directory/'pre-change-proof.json'))
            apply_ledger(db,root,journal)
            # A crash here leaves verification closed until this command resumes.
            write_json(root/'manifest.json',new)
            write_json(root/'seal.json',{'manifest_sha256':journal['new_sha256']})
            quarter.verify(root)
            ledger = quarter.Ledger(root/'jobs.sqlite')
            try:
                ledger.report(root,'retargeted')
            finally:
                ledger.close()
            receipt = dict(journal,status='complete',config_unchanged=True,
                identities_unchanged=True,cursors_unchanged=True,processes_launched=False)
            write_json(directory/'completion.json',receipt)
            return receipt
        finally:
            db.close()


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--proof',type=Path)
    parser.add_argument('--apply',action='store_true',required=True)
    args = parser.parse_args()
    print(json.dumps(migrate(args.root,args.proof),indent=2))


if __name__ == '__main__':
    main()
