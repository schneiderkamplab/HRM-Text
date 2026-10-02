"""Opt-in six-language source/attempt expansion; sealed campaign files stay intact.

Call migration only while all campaign/controller locks are held and workers have
drained. The SQLite backup and receipt preserve the pre-expansion history.
"""
import json
import os
from pathlib import Path
import re
import sqlite3
import time

from . import joint_synthetic_campaign as joint
from .io import digest, file_hash, load, write_json

VERSION = 'joint-source-expansion-v1'
LANGUAGES = ('cs', 'ca', 'is', 'pt_pt', 'et', 'fo')
MULTIPLIER = 24
METADATA_KEY = 'joint_source_expansion_v1'
LIMIT_SQL = "target * CASE WHEN language IN ('cs','ca','is','pt_pt','et','fo') THEN 24 ELSE 6 END"
POLICY = dict(version=VERSION, languages=list(LANGUAGES), candidate_multiplier=MULTIPLIER,
              other_candidate_multiplier=6, lift_original_fo_waivers=True,
              max_candidates_per_source=32, preserve_history=True, quality_gates_unchanged=True)


def require_opt_in(root, enabled):
    with sqlite3.connect((Path(root) / 'jobs.sqlite').resolve().as_uri()+'?mode=ro', uri=True) as db:
        migrated = db.execute('SELECT 1 FROM metadata WHERE key=?', (METADATA_KEY,)).fetchone()
    if migrated and not enabled:
        raise ValueError('Migrated campaign requires explicit --source-expansion')


def limit(language, target):
    return target * (MULTIPLIER if language in LANGUAGES else 6)


def verify_ledger(controller, db, manifest, config):
    expected = {(q['language'], q['family']): q['accepted_target'] for q in
                controller.milestone_targets(config, manifest.get('milestone', 'quarter'),
                                             manifest.get('milestone_divisor'))}
    groups = db.execute('SELECT language,family,target,accepted,active,attempts FROM groups').fetchall()
    if {(g[0], g[1]): g[2] for g in groups} != expected:
        raise ValueError('Ledger targets disagree with sealed milestone')
    migrated = db.execute('SELECT value FROM metadata WHERE key=?', (METADATA_KEY,)).fetchone()
    for language, _, target, accepted, active, attempts in groups:
        ceiling = limit(language, target) if migrated else 6 * target
        if min(accepted, active, attempts) < 0 or accepted + active > target or attempts > ceiling:
            raise ValueError('Expanded ledger quota invariant violated')
    if not db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone():
        raise ValueError('Missing SQLite campaign seal')
    if migrated:
        receipt = json.loads(migrated[0])
        if receipt['policy'] != POLICY:
            raise ValueError('Source expansion policy drift')
        schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='groups'").fetchone()[0]
        if digest(schema) != receipt['new_schema_sha256']:
            raise ValueError('Expanded groups schema drift')


def private_controllers():
    original = joint.european._private_module('multilingual_quarter')
    european = joint.european.isolated_controller()
    for controller in (original, european):
        controller.verify_ledger = lambda db, manifest, config, c=controller: verify_ledger(c, db, manifest, config)
    return original, european


def migrate(ledger, root):
    """Rebuild only groups, atomically; retain every row, index and trigger."""
    root = Path(root)
    db = ledger.db
    existing = db.execute('SELECT value FROM metadata WHERE key=?', (METADATA_KEY,)).fetchone()
    receipt_path = root / 'source-expansion-v1.json'
    if existing:
        receipt = json.loads(existing[0])
        if receipt['policy'] != POLICY or file_hash(Path(receipt['backup'])) != receipt['backup_sha256']:
            raise ValueError('Source expansion receipt/backup drift')
        if receipt_path.exists() and load(receipt_path) != receipt:
            raise ValueError('External source expansion receipt drift')
        schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='groups'").fetchone()[0]
        if digest(schema) != receipt['new_schema_sha256']:
            raise ValueError('Expanded groups schema drift')
        write_json(receipt_path, receipt)
        return receipt
    if db.execute('SELECT 1 FROM groups WHERE active != 0').fetchone() or db.execute(
            "SELECT 1 FROM jobs WHERE status='running' LIMIT 1").fetchone():
        raise ValueError('Source expansion requires a fully drained ledger')
    schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='groups'").fetchone()[0]
    if schema.count('CHECK(attempts <= 6*target)') != 1:
        raise ValueError('Unrecognized groups schema; no automatic migration')
    if db.execute('PRAGMA foreign_key_list(groups)').fetchone():
        raise ValueError('Unexpected foreign keys in groups')
    objects = db.execute("SELECT sql FROM sqlite_master WHERE tbl_name='groups' AND type IN ('index','trigger') AND sql IS NOT NULL").fetchall()
    rows = [dict(row) for row in db.execute('SELECT * FROM groups ORDER BY language,family')]
    backup = root / 'jobs.source-expansion-v1.backup.sqlite'
    # Exclusive creation prevents replacing a previous operator/crash backup.
    with backup.open('xb'):
        pass
    with sqlite3.connect(backup) as destination:
        db.backup(destination)
    receipt = dict(policy=POLICY, backup=str(backup.resolve()), backup_sha256=file_hash(backup),
                   previous_groups=rows, previous_schema=schema, time=time.time())
    new_schema = schema.replace('CHECK(attempts <= 6*target)', f'CHECK(attempts <= {LIMIT_SQL})')
    temporary_schema = re.sub(r'^CREATE TABLE\s+(?:"groups"|groups)', 'CREATE TABLE groups_expansion_new', new_schema, count=1, flags=re.I)
    if temporary_schema == new_schema:
        raise ValueError('Unrecognized groups table declaration')
    with ledger.transaction():
        db.execute(temporary_schema)
        db.execute('INSERT INTO groups_expansion_new SELECT * FROM groups')
        db.execute('DROP TABLE groups')
        db.execute('ALTER TABLE groups_expansion_new RENAME TO groups')
        for (sql,) in objects:
            db.execute(sql)
        if rows != [dict(row) for row in db.execute('SELECT * FROM groups ORDER BY language,family')]:
            raise ValueError('Migration changed historical groups')
        final_schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='groups'").fetchone()[0]
        receipt['new_schema_sha256'] = digest(final_schema)
        db.execute('INSERT INTO metadata VALUES (?,?)', (METADATA_KEY, json.dumps(receipt, sort_keys=True)))
    write_json(receipt_path, receipt)
    return receipt


def ledger_class(controller):
    class ExpandedLedger(controller.Ledger):
        def reserve(self, provider, unavailable, root):
            now = time.time()
            groups = self.db.execute(f'''SELECT * FROM groups WHERE accepted+active < target
                AND attempts < {LIMIT_SQL} AND retry_at <= ?
                ORDER BY CAST(attempts AS REAL)/target, language,family''', (now,)).fetchall()
            for group in groups:
                language, family, slot = group['language'], group['family'], group['next_slot']
                try:
                    spec = provider.next_spec(language, family, slot)
                except unavailable as exc:
                    self.db.execute('UPDATE groups SET retry_at=?,blocked=? WHERE language=? AND family=?',
                                    (now+5, 'seed_shortage: '+str(exc), language, family))
                    continue
                if not isinstance(spec, dict) or (spec.get('language_code'), spec.get('family'), spec.get('slot')) != (language, family, slot):
                    raise ValueError('Provider returned wrong slot identity')
                if type(spec.get('contract_version')) is not int or spec['contract_version'] != 4:
                    raise ValueError('Provider must return contract-v4 spec')
                key = controller.pilot.slot_key(spec)
                directory = controller.work_root(root, key)
                with self.transaction():
                    updated = self.db.execute(f'''UPDATE groups SET active=active+1,attempts=attempts+1,
                        next_slot=next_slot+1,blocked=NULL,retry_at=0 WHERE language=? AND family=?
                        AND accepted+active < target AND attempts < {LIMIT_SQL} AND next_slot=?''',
                        (language, family, slot)).rowcount
                    if updated != 1:
                        raise RuntimeError('Reservation race')
                    self.db.execute('INSERT INTO jobs(id,language,family,slot,status,origin,spec_json,workdir) VALUES(?,?,?,?,?,?,?,?)',
                        (key, language, family, slot, 'running', 'production', json.dumps(spec, ensure_ascii=False), str(directory)))
                write_json(directory / 'specifications' / f'{key}.json', dict(spec=spec, spec_sha256=digest(spec)))
                return dict(id=key, spec=spec, workdir=directory)
            return None

        def report(self, root, phase):
            groups = [dict(row) for row in self.db.execute('SELECT * FROM groups ORDER BY language,family')]
            result = dict(version=controller.VERSION, pid=os.getpid(), phase=phase, time=time.time(),
                          target=sum(g['target'] for g in groups), accepted=sum(g['accepted'] for g in groups),
                          active=sum(g['active'] for g in groups), candidates=sum(g['attempts'] for g in groups),
                          groups=groups, **controller.POLICY)
            result['remaining'] = result['target'] - result['accepted']
            result['candidate_limit'] = sum(limit(g['language'], g['target']) for g in result['groups'])
            result['budget_exhausted_groups'] = sum(g['accepted'] < g['target'] and
                g['attempts'] >= limit(g['language'], g['target']) and not g['active'] for g in result['groups'])
            result['source_expansion'] = POLICY
            write_json(Path(root) / 'progress.json', result)
            return result
    return ExpandedLedger


class ExpandedCampaign(joint.Campaign):
    def waived(self, group):
        return False

    def has_remaining(self):
        return self.ledger.db.execute(f'SELECT 1 FROM groups WHERE accepted < target AND attempts < {LIMIT_SQL} LIMIT 1').fetchone() is not None
