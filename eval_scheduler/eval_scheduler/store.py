"""Local-disk authoritative scheduler state; TSV is an export, not a second writer.

Each operation owns a connection/transaction (safe across threads/processes).
Claims return ``{id: Claim(job, token)}``. Job.attempt remains the Runner's retry
counter; a separate persisted token fences every execution. Running rows may
only be changed by finish(), never by definition import or update_jobs().
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import fields
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any, Iterable, Mapping, NamedTuple
import uuid

from .model import Action, Job, JobStatus, write_plan


class Claim(NamedTuple):
    job: Job
    token: str


RUNTIME_FIELDS = frozenset({"status", "attempt", "log_dir"})
JOB_FIELDS = frozenset(f.name for f in fields(Job))

# A pending success-mode descendant of a failed/skipped job cannot succeed.
# DONE/RUNNING/terminal-mode/optional jobs stop that propagation, as in runtime.
READY_SQL = """
WITH RECURSIVE impossible(job_id) AS (
    SELECT job_id FROM jobs
    WHERE status IN ('failed','skipped') AND optional=0
    UNION
    SELECT j.job_id FROM impossible i
    CROSS JOIN dependencies d ON d.dependency=i.job_id
    CROSS JOIN jobs j ON j.job_id=d.job_id
    WHERE j.status='pending' AND j.deps_mode='success' AND j.optional=0
)
SELECT j.* FROM {candidates}
WHERE {candidate_filter} j.status='pending'
AND NOT (
    json_extract(j.definition, '$.action')='train_until_step'
    AND COALESCE(json_extract(json_extract(j.definition, '$.metadata_json'), '$.user_training_pause'), 0)=1
)
AND NOT EXISTS (
    SELECT 1 FROM dependencies d JOIN jobs parent ON parent.job_id=d.dependency
    WHERE d.job_id=j.job_id AND parent.optional=0 AND (
        (j.deps_mode='success' AND parent.status<>'done') OR
        (j.deps_mode='terminal' AND parent.status NOT IN ('done','failed','skipped')
         AND NOT EXISTS (SELECT 1 FROM impossible i WHERE i.job_id=parent.job_id))
    )
)
ORDER BY j.position LIMIT :limit
"""


def _validate_job(job: Job) -> None:
    if not isinstance(job, Job) or not isinstance(job.job_id, str) or not job.job_id.strip():
        raise ValueError("A Job with a nonempty job_id is required")
    Action(job.action)
    JobStatus(job.status)
    if job.deps_mode not in {"success", "terminal"}:
        raise ValueError(f"Unsupported dependency mode: {job.deps_mode}")
    if type(job.attempt) is not int or job.attempt < 0:
        raise ValueError("attempt must be a nonnegative integer")
    if len(set(job.deps)) != len(job.deps) or any(not isinstance(d, str) or not d for d in job.deps):
        raise ValueError("Dependencies must be unique nonempty IDs")
    # Exercise the model's existing capability/resource checks.
    job.resolved_execution_scope
    job.resolved_capability
    job.resolved_gpu_count
    json.dumps(job.metadata, allow_nan=False)
    json.dumps(job.to_row(), allow_nan=False)


def _validate_graph(jobs: list[Job]) -> None:
    from .preflight import check_artifact_isolation
    collisions = check_artifact_isolation(jobs, Path.cwd())
    if collisions:
        raise ValueError("\n".join(collisions[:10]))
    by_id = {j.job_id: j for j in jobs}
    if len(by_id) != len(jobs):
        raise ValueError("Duplicate job IDs")
    for job in jobs:
        _validate_job(job)
        missing = {dep for dep in job.deps if dep not in by_id}
        if missing:
            raise ValueError(f"{job.job_id}: missing dependencies {sorted(missing)}")
    # Kahn's algorithm avoids recursion limits on long checkpoint campaigns.
    indegree = {j.job_id: len(j.deps) for j in jobs}
    children: dict[str, list[str]] = {key: [] for key in by_id}
    for job in jobs:
        for dep in job.deps:
            children[dep].append(job.job_id)
    queue = [key for key, n in indegree.items() if n == 0]
    visited = 0
    while queue:
        visited += 1
        for child in children[queue.pop()]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if visited != len(jobs):
        raise ValueError("Dependency cycle")


def _definition(job: Job) -> str:
    row = job.to_row()
    for name in RUNTIME_FIELDS:
        row.pop(name)
    return json.dumps(row, sort_keys=True, separators=(",", ":"))


def _job(row: sqlite3.Row) -> Job:
    value = json.loads(row["definition"])
    value.update(status=row["status"], attempt=str(row["attempt"]), log_dir=row["log_dir"])
    return Job.from_row(value)


def require_local_storage(path: Path):
    """SQLite WAL requires local shared-memory semantics, not a network mount."""
    mounts = Path('/proc/self/mountinfo')
    if not mounts.exists():
        raise ValueError('Cannot verify SQLite filesystem type')
    matches = []
    for line in mounts.read_text().splitlines():
        left, right = line.split(' - ', 1)
        mount = left.split()[4]
        for code, char in (('\\040', ' '), ('\\011', '\t'), ('\\012', '\n'), ('\\134', '\\')):
            mount = mount.replace(code, char)
        if path.is_relative_to(Path(mount)):
            matches.append((len(mount), right.split()[0]))
    if not matches:
        raise ValueError('Cannot identify SQLite filesystem type')
    kind = max(matches)[1]
    if kind in {'nfs', 'nfs4', 'cifs', 'smb3', 'ceph', 'wekafs', 'lustre', 'glusterfs', 'fuse.sshfs', 'tmpfs', 'ramfs'}:
        raise ValueError(f'SQLite authority needs durable local storage, not {kind}: {path}')


class SQLiteJobStore:
    """Use a local filesystem path, not shared/NFS storage (SQLite WAL constraint).

    import_jobs replaces the definition set atomically. On existing IDs it
    preserves status/attempt/log_dir by default, regardless of stale TSV state.
    update_jobs applies explicit patches to nonrunning jobs; mixed definition and
    status/attempt patches are rejected to avoid accidental retry resets.
    finish consumes an active token once, permits DONE/FAILED/SKIPPED/PENDING,
    and returns False without mutation for stale, unknown or duplicate tokens.
    """

    def __init__(self, path: str | Path):
        if str(path) == ":memory:":
            raise ValueError("A durable local file path is required")
        self.path = Path(path).resolve()
        require_local_storage(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            if db.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() != "wal":
                raise RuntimeError("SQLite WAL unavailable")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2):
                raise ValueError(f"Unsupported job-store schema version: {version}")
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS jobs(
                    job_id TEXT PRIMARY KEY, position INTEGER NOT NULL,
                    definition TEXT NOT NULL, deps_mode TEXT NOT NULL,
                    optional INTEGER NOT NULL CHECK(optional IN (0,1)),
                    status TEXT NOT NULL CHECK(status IN ('pending','running','done','failed','skipped')),
                    attempt INTEGER NOT NULL CHECK(attempt>=0), log_dir TEXT NOT NULL,
                    token TEXT, CHECK((status='running') = (token IS NOT NULL))
                );
                CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status,position);
                CREATE TABLE IF NOT EXISTS dependencies(
                    job_id TEXT NOT NULL REFERENCES jobs(job_id) DEFERRABLE INITIALLY DEFERRED,
                    dependency TEXT NOT NULL REFERENCES jobs(job_id) DEFERRABLE INITIALLY DEFERRED,
                    PRIMARY KEY(job_id,dependency)
                );
                CREATE INDEX IF NOT EXISTS dependencies_parent ON dependencies(dependency,job_id);
                CREATE TABLE IF NOT EXISTS administration(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    locked INTEGER NOT NULL CHECK(locked IN (0,1))
                );
                INSERT OR IGNORE INTO administration VALUES (1,0);
                PRAGMA user_version=2;
                COMMIT;
            """)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA synchronous=FULL")
            yield db
        finally:
            db.close()

    @contextmanager
    def _transaction(self, write: bool = False):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    @staticmethod
    def _rows(db):
        return db.execute("SELECT * FROM jobs ORDER BY position").fetchall()

    @staticmethod
    def _write_definition(db, job: Job, position: int):
        db.execute("UPDATE jobs SET definition=?,position=?,deps_mode=?,optional=? WHERE job_id=?",
                   (_definition(job), position, job.deps_mode,
                    int(job.action == Action.EVAL_EUROEVAL and job.name.startswith("valeu-")), job.job_id))
        db.execute("DELETE FROM dependencies WHERE job_id=?", (job.job_id,))
        db.executemany("INSERT INTO dependencies VALUES (?,?)", [(job.job_id, d) for d in job.deps])

    def import_jobs(self, jobs: Iterable[Job], preserve_runtime: bool = True,
                    *, require_admin_lock: bool = False) -> None:
        """Replace definitions, optionally requiring the fence in this transaction.

        A required but cleared fence raises ValueError without changing jobs.
        BEGIN IMMEDIATE prevents a concurrent unlock until import commits.
        """
        jobs = list(jobs)
        _validate_graph(jobs)
        with self._transaction(write=True) as db:
            if require_admin_lock and not db.execute(
                    "SELECT locked FROM administration WHERE singleton=1").fetchone()[0]:
                raise ValueError("import_jobs requires an active admin lock")
            old = {r["job_id"]: r for r in self._rows(db)}
            incoming = {j.job_id: j for j in jobs}
            for key, row in old.items():
                if row["status"] == JobStatus.RUNNING:
                    new = incoming.get(key)
                    previous = _job(row)
                    if new is None or _definition(new) != row["definition"]:
                        raise ValueError(f"Cannot edit/remove running job: {key}")
                    if not preserve_runtime and (new.status != previous.status or new.attempt != previous.attempt or new.log_dir != previous.log_dir):
                        raise ValueError(f"Cannot replace running state: {key}")
            for key in old.keys() - incoming.keys():
                db.execute("DELETE FROM dependencies WHERE job_id=?", (key,))
                db.execute("DELETE FROM jobs WHERE job_id=?", (key,))
            for position, job in enumerate(jobs):
                row = old.get(job.job_id)
                if row is not None and preserve_runtime:
                    job = job.with_updates(status=JobStatus(row["status"]), attempt=row["attempt"], log_dir=row["log_dir"])
                token = (row["token"] if row is not None else None)
                if job.status == JobStatus.RUNNING:
                    token = token or uuid.uuid4().hex
                else:
                    token = None
                if row is None:
                    db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)", (
                        job.job_id, position, _definition(job), job.deps_mode,
                        int(job.action == Action.EVAL_EUROEVAL and job.name.startswith("valeu-")),
                        str(job.status), job.attempt, job.log_dir, token))
                    db.executemany("INSERT INTO dependencies VALUES (?,?)", [(job.job_id,d) for d in job.deps])
                else:
                    if row["definition"] != _definition(job):
                        self._write_definition(db, job, position)
                    elif row["position"] != position:
                        db.execute("UPDATE jobs SET position=? WHERE job_id=?", (position, job.job_id))
                    if (row["status"], row["attempt"], row["log_dir"], row["token"]) != (str(job.status), job.attempt, job.log_dir, token):
                        db.execute("UPDATE jobs SET status=?,attempt=?,log_dir=?,token=? WHERE job_id=?",
                                   (str(job.status),job.attempt,job.log_dir,token,job.job_id))

    def load_jobs(self) -> list[Job]:
        with self._transaction() as db:
            return [_job(row) for row in self._rows(db)]

    def split_postprocessing(self) -> int:
        """Atomically split pending inference/CPU phases before claiming work.

        Keep the original ID on publication so existing merge/average edges
        still wait for usable results. Reuse the legacy plan transformation.
        """
        from .plan import split_euroeval_postprocessing
        with self._transaction(write=True) as db:
            rows = self._rows(db)
            if any(row['status'] == JobStatus.RUNNING for row in rows):
                raise ValueError('Cannot split phases with running claims')
            if db.execute('SELECT locked FROM administration WHERE singleton=1').fetchone()[0]:
                return 0
            old = {row['job_id']: _job(row) for row in rows}
            jobs = split_euroeval_postprocessing(list(old.values()))
            added = len(jobs) - len(old)
            if not added:
                return 0
            _validate_graph(jobs)
            # Insert all new IDs before installing dependency edges.
            for position, job in enumerate(jobs):
                if job.job_id not in old:
                    db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)', (
                        job.job_id, position, _definition(job), job.deps_mode, 0,
                        str(job.status), job.attempt, job.log_dir, None))
            for position, job in enumerate(jobs):
                previous = old.get(job.job_id)
                if previous != job:
                    self._write_definition(db, job, position)
                    db.execute('UPDATE jobs SET attempt=? WHERE job_id=?', (job.attempt, job.job_id))
                else:
                    db.execute('UPDATE jobs SET position=? WHERE job_id=?', (position, job.job_id))
            return added

    def update_jobs(self, updates: Mapping[str, Mapping[str, Any]]) -> dict[str, Job]:
        with self._transaction(write=True) as db:
            changes = {}
            definitions_changed = False
            for key, patch in updates.items():
                if set(patch) - (JOB_FIELDS - {"job_id"}):
                    raise ValueError(f"Unknown/immutable update fields: {key}")
                row = db.execute("SELECT * FROM jobs WHERE job_id=?", (key,)).fetchone()
                if row is None:
                    raise KeyError(key)
                before = _job(row)
                patch = dict(patch)
                if "status" in patch:
                    patch["status"] = JobStatus(patch["status"])
                if "action" in patch:
                    patch["action"] = Action(patch["action"])
                job = before.with_updates(**patch)
                _validate_job(job)
                changed_definition = bool(set(patch) - RUNTIME_FIELDS) and _definition(job) != row["definition"]
                if changed_definition and set(patch) & {"status", "attempt"}:
                    raise ValueError("Edit definitions separately from runtime state")
                if before.status == JobStatus.RUNNING and job != before:
                    raise ValueError(f"Use finish with the active token: {key}")
                if before.status != JobStatus.RUNNING and job.status == JobStatus.RUNNING:
                    raise ValueError("Use claim_jobs to enter RUNNING")
                if changed_definition:
                    self._write_definition(db, job, row["position"])
                    definitions_changed = True
                if (job.status,job.attempt,job.log_dir) != (before.status,before.attempt,before.log_dir):
                    db.execute("UPDATE jobs SET status=?,attempt=?,log_dir=? WHERE job_id=?",
                               (str(job.status),job.attempt,job.log_dir,key))
                changes[key] = job
            if definitions_changed:
                _validate_graph([_job(r) for r in self._rows(db)])
            # A barrier may have completed because failed ancestry made future
            # evals unreachable. Administrative recovery can make them runnable
            # again; cached barrier completion must not bypass that work.
            self._rearm_terminal_barriers(db)
            return changes

    @staticmethod
    def _rearm_terminal_barriers(db):
        query = READY_SQL.format(candidates='jobs j', candidate_filter="j.deps_mode='terminal' AND ")
        query = query.replace("j.status='pending'\nAND NOT (",
                              "j.status='done'\nAND NOT (")
        while True:
            satisfied = {r['job_id'] for r in db.execute(query, {'limit': -1})}
            stale = [r['job_id'] for r in db.execute(
                "SELECT job_id FROM jobs WHERE status='done' AND deps_mode='terminal' "
                "AND json_extract(definition, '$.action')='terminal_barrier'")
                if r['job_id'] not in satisfied]
            if not stale:
                return
            db.executemany("UPDATE jobs SET status='pending',attempt=0 WHERE job_id=?",
                           [(key,) for key in stale])

    def get_admin_lock(self) -> bool:
        """Persistent claim fence, not a lease; existing claims can still finish."""
        with self._transaction() as db:
            return bool(db.execute("SELECT locked FROM administration WHERE singleton=1").fetchone()[0])

    def finalize_eval_epoch(self, job_ids, epoch, pending_flags=(), *, train_step=None):
        """Publish cursor-derived epoch without resetting concurrent wait claims.

        Only checkpoint waits may already be running: evaluation clients must
        not have started with an unfinalized epoch. No execution field changes.
        """
        allowed_flags = {'dfm13_cursor_epoch_pending', 'dfm14_cursor_epoch_pending'}
        if not math.isfinite(epoch) or epoch < 0 or set(pending_flags) - allowed_flags:
            raise ValueError('Invalid epoch finalization')
        if train_step is not None and (type(train_step) is not int or train_step < 0):
            raise ValueError('Invalid training step finalization')
        with self._transaction(write=True) as db:
            for job_id in job_ids:
                row = db.execute('SELECT * FROM jobs WHERE job_id=?', (job_id,)).fetchone()
                if row is None:
                    raise KeyError(job_id)
                job = _job(row)
                if job.status == JobStatus.RUNNING and job.action != Action.WAIT_CHECKPOINT:
                    raise ValueError(f'Evaluation already started before epoch finalization: {job_id}')
                metadata = {**job.metadata, 'eval_epoch': epoch,
                            **{name: False for name in pending_flags}}
                if train_step is not None:
                    metadata['eval_step'] = train_step
                self._write_definition(db, job.with_updates(metadata=metadata), row['position'])

    def set_admin_lock(self, locked: bool) -> None:
        """Serialize with claims: after True commits no subsequent claim can win.

        This does not revoke claims committed before the fence, nor prohibit
        administrative imports/updates. Clearing it is an explicit operation.
        """
        if type(locked) is not bool:
            raise ValueError("locked must be bool")
        with self._transaction(write=True) as db:
            db.execute("UPDATE administration SET locked=? WHERE singleton=1", (int(locked),))

    def ready_jobs(self, limit: int | None = None) -> list[Job]:
        if limit is not None and (type(limit) is not int or limit < 0):
            raise ValueError("limit must be a nonnegative integer or None")
        with self._transaction() as db:
            if db.execute("SELECT locked FROM administration WHERE singleton=1").fetchone()[0]:
                return []
            sql = READY_SQL.format(candidates="jobs j", candidate_filter="")
            return [_job(row) for row in db.execute(sql, {"limit": -1 if limit is None else limit})]

    def claim_jobs(self, ids: Iterable[str]) -> dict[str, Claim]:
        requested = set(ids)
        if not requested:
            return {}
        with self._transaction(write=True) as db:
            if db.execute("SELECT locked FROM administration WHERE singleton=1").fetchone()[0]:
                return {}
            # CROSS JOIN forces indexed job lookups from the bounded request set;
            # the temporary table also avoids SQLite's SQL-variable limit.
            db.execute("CREATE TEMP TABLE requested(job_id TEXT PRIMARY KEY)")
            db.executemany("INSERT INTO requested VALUES (?)", ((key,) for key in requested))
            sql = READY_SQL.format(candidates="requested r CROSS JOIN jobs j",
                                   candidate_filter="j.job_id=r.job_id AND")
            ready = db.execute(sql, {"limit": -1}).fetchall()
            claimed = {}
            for row in ready:
                token = uuid.uuid4().hex
                db.execute("UPDATE jobs SET status='running',token=? WHERE job_id=? AND status='pending'",
                           (token,row["job_id"]))
                claimed[row["job_id"]] = Claim(_job(row).with_updates(status=JobStatus.RUNNING), token)
            return claimed

    def attempt_token(self, job_id: str) -> str | None:
        """Recover a persisted claim token after coordinator reopen, not a new claim."""
        with self._transaction() as db:
            row = db.execute("SELECT token FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            return row[0]

    def finish(self, job_id: str, token: str, updates: Mapping[str, Any]) -> bool:
        with self._transaction(write=True) as db:
            row = db.execute("SELECT * FROM jobs WHERE job_id=? AND status='running' AND token=?",
                             (job_id,token)).fetchone()
            if row is None:
                return False
            if set(updates) - RUNTIME_FIELDS or "status" not in updates:
                raise ValueError("finish requires status and only runtime fields")
            updates = dict(updates, status=JobStatus(updates["status"]))
            job = _job(row).with_updates(**updates)
            _validate_job(job)
            if job.status == JobStatus.RUNNING:
                raise ValueError("finish must release the running claim")
            db.execute("UPDATE jobs SET status=?,attempt=?,log_dir=?,token=NULL WHERE job_id=?",
                       (str(job.status),job.attempt,job.log_dir,job_id))
            return True

    def export_tsv(self, path: str | Path) -> None:
        """Atomically export a consistent Job snapshot in the existing TSV format."""
        path = Path(path).resolve()
        if path in {self.path, Path(str(self.path)+'-wal'), Path(str(self.path)+'-shm')}:
            raise ValueError("Cannot export over the store")
        jobs = self.load_jobs()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
        os.close(fd)
        temp = Path(name)
        try:
            write_plan(temp, jobs)
            with temp.open('rb') as f:
                os.fsync(f.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def backup(self, path: str | Path):
        """Atomically replace a consistent standalone backup, including committed WAL."""
        path = Path(path).resolve()
        if path in {self.path, Path(str(self.path)+'-wal'), Path(str(self.path)+'-shm')}:
            raise ValueError('Cannot back up over the authority')
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
        os.close(fd)
        temp = Path(name)
        try:
            with self._connect() as source, closing(sqlite3.connect(temp)) as destination:
                source.backup(destination)
                if destination.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise ValueError('Backup integrity check failed')
            with temp.open('rb') as handle:
                os.fsync(handle.fileno())
            os.replace(temp, path)
            fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            temp.unlink(missing_ok=True)
            temp.with_suffix(temp.suffix+'.tmp').unlink(missing_ok=True)
