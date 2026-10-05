"""Offline whole-language W4 partitioning; never launches or changes its source."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3

from .io import file_hash, load, lock, write_json


def assignment(rows, workers=8):
    languages = {}
    for language, target, accepted in rows:
        if not 0 <= accepted <= target:
            raise ValueError('Invalid quota')
        languages[language] = languages.get(language, 0) + target - accepted
    if len(languages) < workers:
        raise ValueError('Fewer languages than workers')
    bins = [[] for _ in range(workers)]
    loads = [0] * workers
    for language in sorted(languages, key=lambda k: (-languages[k], k)):
        index = min(range(workers), key=lambda i: (loads[i], len(bins[i]), i))
        bins[index].append(language)
        loads[index] += languages[language]
    return [dict(worker=i, languages=sorted(langs), remaining=loads[i],
                 endpoint=f'http://127.0.0.1:{8800+i}/v1') for i, langs in enumerate(bins)]


class FingerprintRegistry:
    """One atomic claim per candidate; no quota, source or job writes here."""
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=30, isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS fingerprints '
                        '(fingerprint TEXT PRIMARY KEY, owner TEXT NOT NULL)')

    def claim(self, fingerprint, owner):
        if not fingerprint or not owner or owner in ('prior-history', 'pilot-history'):
            raise ValueError('Concrete candidate identity required')
        self.db.execute('INSERT OR IGNORE INTO fingerprints VALUES (?,?)', (fingerprint, owner))
        row = self.db.execute('SELECT owner FROM fingerprints WHERE fingerprint=?', (fingerprint,)).fetchone()
        return row[0] == owner

    def close(self):
        self.db.close()


def copy_table(source, dest, table, where='', args=()):
    sql = source.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not sql:
        raise ValueError('Missing table: '+table)
    dest.execute(sql[0])
    cursor = source.execute('SELECT * FROM '+table+where, args)
    placeholders = ','.join('?' for _ in cursor.description)
    while rows := cursor.fetchmany(1000):
        dest.executemany('INSERT INTO '+table+' VALUES ('+placeholders+')', rows)


def verify_output(root):
    receipt = load(root/'prepared.json')
    if receipt.get('launch_authorized') is not False:
        raise ValueError('Unexpected launch authority')
    for name, sha in receipt['files'].items():
        if file_hash(root/name) != sha:
            raise ValueError('Prepared snapshot drift: '+name)
    return receipt


def prepare(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root or root in output.parents or output in root.parents:
        raise ValueError('Independent output root required')
    if output.exists():
        result = verify_output(output)
        if result['source_root'] != str(root):
            raise ValueError('Output belongs to another source')
        return result
    staging = output.with_name(output.name+'.preparing')
    # Partial preparation is retained for diagnosis, never mistaken for launchable state.
    with lock(root/'controller.lock'):
        from .wave4_compact_handoff import verify_independent_launch
        verify_independent_launch(root)
        return partition_locked(root, output, staging)


def partition_locked(root, output, staging, expected_target=770000):
    """Caller owns controller lock and verified pins; fixture-testable CPU core."""
    with sqlite3.connect((root/'jobs.sqlite').as_uri()+'?mode=ro', uri=True) as jobs, \
         sqlite3.connect((root/'spec-selections.sqlite').as_uri()+'?mode=ro', uri=True) as sources:
        if jobs.execute('SELECT coalesce(sum(active),0) FROM groups').fetchone()[0] or jobs.execute(
                "SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]:
            raise ValueError('Controller must be fully drained')
        bad = jobs.execute('''SELECT count(*) FROM groups g WHERE accepted !=
            (SELECT count(*) FROM jobs j WHERE j.language=g.language AND j.family=g.family AND j.status='accepted')''').fetchone()[0]
        if bad:
            raise ValueError('Accepted ledger totals disagree')
        rows = jobs.execute('SELECT language,target,accepted FROM groups').fetchall()
        if sum(r[1] for r in rows) != expected_target:
            raise ValueError('Unexpected campaign target')
        shards = assignment(rows)
        staging.mkdir(parents=True, exist_ok=False)
        write_json(staging/'journal.json', dict(state='preparing', source_root=str(root)))
        registry = FingerprintRegistry(staging/'fingerprints.sqlite')
        try:
            registry.db.execute('BEGIN IMMEDIATE')
            fingerprints = jobs.execute('SELECT fingerprint,owner FROM fingerprints')
            while batch := fingerprints.fetchmany(1000):
                registry.db.executemany('INSERT INTO fingerprints VALUES (?,?)', batch)
            registry.db.execute('COMMIT')
            registry.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        finally:
            registry.close()
        for shard in shards:
            directory = staging/f"shard-{shard['worker']}"
            directory.mkdir()
            manifest = load(root/'manifest.json')
            for name in {'manifest.json', 'seal.json', *manifest.get('input_pins', {})}:
                relative = Path(name)
                if relative.is_absolute() or '..' in relative.parts:
                    raise ValueError('Unsafe input pin path')
                target = directory/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root/relative, target)
            langs = shard['languages']
            marks = ','.join('?' for _ in langs)
            with sqlite3.connect(directory/'jobs.sqlite') as dest:
                for table in ('groups', 'jobs'):
                    copy_table(jobs, dest, table, ' WHERE language IN ('+marks+')', langs)
                copy_table(jobs, dest, 'metadata')
                # Local finish() checks remain valid; all future claims must use registry first.
                copy_table(jobs, dest, 'fingerprints', ' WHERE owner IN (SELECT id FROM jobs WHERE language IN ('+marks+'))', langs)
                dest.execute('CREATE INDEX jobs_status ON jobs(status)')
            with sqlite3.connect(directory/'spec-selections.sqlite') as dest:
                copy_table(sources, dest, 'metadata')
                copy_table(sources, dest, 'selections', " WHERE json_extract(spec,'$.language_code') IN ("+marks+')', langs)
                for table in ('cursors', 'used_sources'):
                    copy_table(sources, dest, table, " WHERE substr(scope,1,instr(scope,'/')-1) IN ("+marks+')', langs)
            write_json(directory/'ownership.json', dict(**shard, campaign_root=str(root),
                registry='../fingerprints.sqlite', launch_authorized=False))
        preserved = dict(accepted=0, target=0, attempts=0, jobs=0)
        for shard in shards:
            with sqlite3.connect(staging/f"shard-{shard['worker']}"/'jobs.sqlite') as db:
                a,t,n = db.execute('SELECT sum(accepted),sum(target),sum(attempts) FROM groups').fetchone()
                preserved['accepted'] += a
                preserved['target'] += t
                preserved['attempts'] += n
                preserved['jobs'] += db.execute('SELECT count(*) FROM jobs').fetchone()[0]
        original = dict(zip(('accepted','target','attempts'), jobs.execute(
            'SELECT sum(accepted),sum(target),sum(attempts) FROM groups').fetchone()))
        original['jobs'] = jobs.execute('SELECT count(*) FROM jobs').fetchone()[0]
        if preserved != original:
            raise ValueError('Shard accounting does not preserve original totals')
        source_totals = {}
        for table in ('selections', 'cursors', 'used_sources'):
            expected = sources.execute('SELECT count(*) FROM '+table).fetchone()[0]
            actual = 0
            for shard in shards:
                with sqlite3.connect(staging/f"shard-{shard['worker']}"/'spec-selections.sqlite') as db:
                    actual += db.execute('SELECT count(*) FROM '+table).fetchone()[0]
            if actual != expected:
                raise ValueError('Unassigned or duplicated source state: '+table)
            source_totals[table] = actual
        files = {str(p.relative_to(staging)): file_hash(p) for p in staging.rglob('*') if p.is_file() and p.name != 'journal.json'}
        receipt = dict(source_root=str(root), source_manifest_sha256=file_hash(root/'manifest.json'),
                       shards=shards, files=files, launch_authorized=False,
                       preserved_totals=preserved, expected_target=expected_target,
                       preserved_source_totals=source_totals,
                       snapshot_verification_only=True, automatic_resume=False,
                       accepted=sum(r[2] for r in rows), target=sum(r[1] for r in rows),
                       source_job_count=jobs.execute('SELECT count(*) FROM jobs').fetchone()[0])
        write_json(staging/'prepared.json', receipt)
        write_json(staging/'journal.json', dict(state='complete', launch_authorized=False))
        os.rename(staging, output)
        return verify_output(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.root, args.output), indent=2))
