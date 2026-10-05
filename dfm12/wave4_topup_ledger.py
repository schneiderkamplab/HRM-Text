"""Private final-top-up ledger policy with absolute original-target ceilings."""
import json
from pathlib import Path
import time

def migrate_groups(db, policies):
    """Offline transaction: preserve counters and replace the old 6x CHECK."""
    if db.in_transaction:
        raise ValueError('Migration needs its own transaction')
    old = [dict(r) for r in db.execute('SELECT * FROM groups')]
    by_key = {(r['language'],r['family']):r for r in policies}
    if set(by_key) != {(r['language'],r['family']) for r in old}:
        raise ValueError('Policy coverage mismatch')
    if any(r['active'] for r in old) or db.execute("SELECT 1 FROM jobs WHERE status='running' LIMIT 1").fetchone():
        raise ValueError('Active predecessor cannot migrate')
    with db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('ALTER TABLE groups RENAME TO groups_before_topup')
        db.execute('''CREATE TABLE groups (
            language TEXT, family TEXT, target INTEGER NOT NULL,
            accepted INTEGER NOT NULL, active INTEGER NOT NULL,
            attempts INTEGER NOT NULL, next_slot INTEGER NOT NULL,
            retry_at REAL NOT NULL, blocked TEXT,
            original_target INTEGER NOT NULL, attempt_limit INTEGER NOT NULL,
            accepted_floor INTEGER NOT NULL,
            PRIMARY KEY(language,family), CHECK(accepted>=accepted_floor AND active>=0),
            CHECK(accepted+active<=target), CHECK(attempts<=attempt_limit),
            CHECK(attempt_limit<=12*original_target))''')
        for row in old:
            policy=by_key[(row['language'],row['family'])]
            if policy['accepted_floor']!=row['accepted'] or policy['attempts']!=row['attempts']:
                raise ValueError('Policy snapshot drift')
            # Source shortages are reevaluated against the sealed additive pool.
            row.update(target=policy['target'],original_target=policy['original_target'],
                attempt_limit=policy['attempt_limit'],accepted_floor=policy['accepted_floor'],
                blocked=None,retry_at=0)
            columns=list(row)
            db.execute('INSERT INTO groups ('+','.join(columns)+') VALUES ('+
                ','.join('?' for _ in columns)+')',[row[k] for k in columns])
        db.execute('DROP TABLE groups_before_topup')


def install(c, owner, allowed):
    """Keep existing finish/materialization/dedup while replacing allocation caps."""
    base=c.Ledger
    allowed=frozenset(map(tuple,allowed))
    class Ledger(base):
        def remaining_groups(self):
            return [r for r in self.db.execute('''SELECT * FROM groups
                WHERE accepted<target AND attempts<attempt_limit AND blocked IS NULL''')
                if (r['language'],r['family']) in allowed]

        def publish(self):
            owner.remaining_hint=any((r['language'],r['family']) in allowed
                and not r['blocked'] and r['accepted']<r['target']
                and r['attempts']<r['attempt_limit'] for r in self.group_snapshot.values())

        def reserve(self,provider,unavailable,root):
            groups=self.db.execute('''SELECT * FROM groups WHERE accepted+active<target
                AND attempts<attempt_limit AND blocked IS NULL
                ORDER BY CAST(attempts AS REAL)/original_target,language,family''').fetchall()
            for group in groups:
                language,family,slot=group['language'],group['family'],group['next_slot']
                if (language,family) not in allowed:
                    continue
                try:
                    spec=provider.next_spec(language,family,slot)
                except unavailable as exc:
                    self.db.execute('UPDATE groups SET blocked=? WHERE language=? AND family=?',
                        ('seed_shortage: '+str(exc),language,family))
                    continue
                if (not isinstance(spec,dict) or
                        (spec.get('language_code'),spec.get('family'),spec.get('slot'))!=(language,family,slot)
                        or type(spec.get('contract_version')) is not int or spec['contract_version']!=4):
                    raise ValueError('Provider identity/contract mismatch')
                key=c.pilot.slot_key(spec)
                directory=c.work_root(root,key)
                with self.transaction():
                    updated=self.db.execute('''UPDATE groups SET active=active+1,attempts=attempts+1,
                        next_slot=next_slot+1 WHERE language=? AND family=? AND next_slot=?
                        AND accepted+active<target AND attempts<attempt_limit''',
                        (language,family,slot)).rowcount
                    if updated!=1:
                        raise RuntimeError('Top-up reservation race')
                    self.db.execute('INSERT INTO jobs(id,language,family,slot,status,origin,spec_json,workdir) VALUES(?,?,?,?,?,?,?,?)',
                        (key,language,family,slot,'running','production',json.dumps(spec,ensure_ascii=False),str(directory)))
                self.allocated_groups[key]=(language,family)
                self.refresh()
                # The inherited Owner.call writes this spec durably on the disk
                # pool before any generation request, outside the ledger batch.
                return dict(id=key,spec=spec,workdir=directory)
            self.refresh()
            return None

        def report(self,root,phase):
            groups=[dict(r) for r in self.db.execute('SELECT * FROM groups ORDER BY language,family')]
            report=dict(version='wave4-final-topup-v1',phase=phase,time=time.time(),groups=groups,
                target=sum(r['target'] for r in groups),accepted=sum(r['accepted'] for r in groups),
                active=sum(r['active'] for r in groups),candidates=sum(r['attempts'] for r in groups),
                candidate_limit=sum(r['attempt_limit'] for r in groups),**c.POLICY)
            report['remaining']=report['target']-report['accepted']
            report['approved_remaining']=sum(r['target']-r['accepted'] for r in groups
                if (r['language'],r['family']) in allowed)
            report['budget_exhausted_groups']=sum(r['accepted']<r['target'] and
                r['attempts']>=r['attempt_limit'] and not r['active'] for r in groups)
            c.write_json(Path(root)/'progress.json',report)
            return report
    c.Ledger=Ledger
    return c
