"""Explicit SQLite administration; never run evaluation or write W&B history."""
from __future__ import annotations

import csv
import json
import os
import tempfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

import typer

from .locking import PlanLock
from .model import Action, FIELDNAMES, Job, JobStatus

database_app = typer.Typer(help="Opt-in authoritative SQLite plan management.")


def read_import(path: Path) -> list[Job]:
    """Do not treat a missing/malformed TSV as an empty migration."""
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != FIELDNAMES:
            raise ValueError('Expected the current scheduler TSV columns in order')
        rows = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError('Malformed TSV row')
    jobs = [Job.from_row(row) for row in rows]
    validate_graph(jobs)
    return jobs


def validate_graph(jobs: list[Job]) -> None:
    ids = {job.job_id for job in jobs}
    if len(ids) != len(jobs) or any(not key for key in ids):
        raise ValueError('Duplicate or empty job IDs')
    indegree = {key: 0 for key in ids}
    children = {key: [] for key in ids}
    for job in jobs:
        if job.deps_mode not in ('success', 'terminal'):
            raise ValueError('Unknown dependency mode')
        if len(set(job.deps)) != len(job.deps):
            raise ValueError('Duplicate dependencies')
        for dep in job.deps:
            if dep not in ids:
                raise ValueError(f'{job.job_id}: missing dependency {dep}')
            indegree[job.job_id] += 1
            children[dep].append(job.job_id)
    ready = [key for key, count in indegree.items() if count == 0]
    visited = 0
    while ready:
        key = ready.pop(); visited += 1
        for child in children[key]:
            indegree[child] -= 1
            if indegree[child] == 0: ready.append(child)
    if visited != len(ids):
        raise ValueError('Dependency cycle')


def runner_command_matches(argv: list[str], cwd: Path, plan_dir: Path) -> bool:
    scheduler = any('eval_scheduler' in arg or Path(arg).name == 'hrm-eval-scheduler' for arg in argv)
    if not scheduler or not any(word in argv for word in ('run', 'coordinator', 'worker')):
        return False
    for i, arg in enumerate(argv):
        value = arg.split('=', 1)[1] if arg.startswith('--plan-dir=') else (
            argv[i+1] if arg == '--plan-dir' and i+1 < len(argv) else None)
        if value is not None and (cwd / value).resolve() == plan_dir.resolve():
            return True
    return False


def assert_runner_stopped(plan_dir: Path, proc_root: Path = Path('/proc')) -> None:
    """Legacy Runner has no lifetime lock; inspect processes as well as PlanLock.

    Migration still requires operational exclusion of remote runners and new
    legacy launches. A local process snapshot cannot fence another machine.
    """
    if not proc_root.is_dir():
        raise ValueError('Cannot verify local runner inactivity without /proc')
    for entry in proc_root.iterdir():
        if not entry.name.isdecimal() or int(entry.name) == os.getpid(): continue
        try:
            argv = [x.decode() for x in (entry/'cmdline').read_bytes().split(b'\0') if x]
            if not any('eval_scheduler' in arg or Path(arg).name == 'hrm-eval-scheduler' for arg in argv):
                continue
            cwd = (entry/'cwd').resolve(strict=True)
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (PermissionError, UnicodeError) as exc:
            raise ValueError(f'Cannot verify runner PID {entry.name}') from exc
        if runner_command_matches(argv, cwd, plan_dir):
            raise ValueError(f'Active scheduler PID {entry.name}; stop/drain before migration')


def read_definition_patch(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError('Duplicate patch key: '+key)
            result[key] = value
        return result
    patch = json.loads(path.read_text(), object_pairs_hook=unique)
    allowed = set(Job.__dataclass_fields__) - {'job_id', 'status', 'attempt', 'log_dir'}
    if not isinstance(patch, dict) or not patch or set(patch) - allowed:
        raise ValueError('Edit accepts definition fields only, never job_id/status/attempt/log_dir')
    if 'action' in patch: patch['action'] = Action(patch['action'])
    if 'deps' in patch:
        if not isinstance(patch['deps'], list) or any(not isinstance(d,str) for d in patch['deps']):
            raise ValueError('deps must be a JSON array of job IDs')
        patch['deps'] = tuple(patch['deps'])
    if 'metadata' in patch and not isinstance(patch['metadata'], dict):
        raise ValueError('metadata must be an object (replaces this job definition field)')
    return patch


@contextmanager
def command_errors():
    try:
        yield
    except (ValueError, KeyError, OSError) as exc:
        typer.echo(f'Error: {exc}', err=True)
        raise typer.Exit(1) from exc


def open_existing(database: Path):
    from .store import SQLiteJobStore
    if not database.is_file(): raise ValueError('Database does not exist; use explicit import first')
    return SQLiteJobStore(database)


def check_database_marker(plan_dir: Path, database: Path) -> bool:
    marker = plan_dir/'database.json'
    if not marker.exists(): return False
    data = json.loads(marker.read_text())
    if not isinstance(data, dict) or set(data) != {'database'} or not isinstance(data['database'], str):
        raise ValueError('Malformed database.json authority marker')
    target = Path(data['database'])
    if not target.is_absolute() or target.resolve() != database.resolve():
        raise ValueError('Plan already names a different authoritative database')
    return True


def publish_database_marker(plan_dir: Path, database: Path) -> None:
    """Caller holds PlanLock; publish only after the import transaction commits."""
    if check_database_marker(plan_dir, database): return
    fd, name = tempfile.mkstemp(prefix='.database-', suffix='.json.tmp', dir=plan_dir)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump({'database':str(database.resolve())}, handle)
            handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
        os.replace(name, plan_dir/'database.json')
        directory = os.open(plan_dir, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


@database_app.command('import')
def import_database(
    source: Path = typer.Option(..., help='TSV definitions and initial runtime state.'),
    database: Path = typer.Option(..., help='Authoritative local SQLite file.'),
    plan_dir: Path = typer.Option(..., help='Legacy plan directory whose runners must be stopped.'),
    runners_stopped: bool = typer.Option(False, help='Confirm all local AND remote runners are stopped; no new legacy launches.'),
) -> None:
    """Atomically import definitions; existing IDs retain newer runtime state."""
    from .store import SQLiteJobStore
    with command_errors():
        if not plan_dir.is_dir(): raise ValueError('Plan directory does not exist')
        if source.resolve() == database.resolve(): raise ValueError('Source cannot be the database')
        with PlanLock(plan_dir, exclusive=True, blocking=False):
            migrated = check_database_marker(plan_dir, database)
            if not migrated:
                if not runners_stopped: raise ValueError('Initial migration requires --runners-stopped confirmation')
                assert_runner_stopped(plan_dir)
            jobs = read_import(source)
            if not migrated and any(j.status == JobStatus.RUNNING for j in jobs):
                raise ValueError('TSV contains running jobs; reconcile stopped attempts explicitly before import')
            store = open_existing(database) if migrated else SQLiteJobStore(database)
            if migrated:
                if not store.get_admin_lock(): raise ValueError('Definition import requires database lock first')
                store.import_jobs(jobs, preserve_runtime=True, require_admin_lock=True)
            else:
                store.import_jobs(jobs, preserve_runtime=True)
            publish_database_marker(plan_dir, database)
        typer.echo(json.dumps({'database':str(database.resolve()), 'imported':len(jobs),
                               'preserve_runtime':True}))


@database_app.command('export')
def export_database(database: Path = typer.Option(...), output: Path = typer.Option(...)) -> None:
    """Write a TSV snapshot, never change the authoritative store."""
    with command_errors():
        open_existing(database).export_tsv(output)
        typer.echo(str(output.resolve()))


@database_app.command('status')
def database_status(database: Path = typer.Option(...)) -> None:
    with command_errors():
        store = open_existing(database)
        jobs = store.load_jobs()
        counts = Counter(str(job.status) for job in jobs)
        typer.echo(json.dumps({'database':str(database.resolve()),'jobs':len(jobs),
            'counts':{str(s):counts[str(s)] for s in JobStatus},
            'running':[j.job_id for j in jobs if j.status == JobStatus.RUNNING],
            'dispatch_locked':store.get_admin_lock()},sort_keys=True))


@database_app.command('preflight')
def preflight_database(plan_dir: Path = typer.Option(None),
                       database: Path = typer.Option(None),
                       gpus: str = typer.Option('0,1,2,3,4,5,6,7'),
                       all_rows: bool = typer.Option(False, '--all')) -> None:
    """Validate pending definitions and availability without running anything.

    Exactly one of --plan-dir (legacy TSV) or --database (authoritative SQLite
    store) must be given. Availability checks resolve relative paths against
    the current working directory, which must be the repository root the
    runner would use.
    """
    from .database_runner import DatabaseRunner
    from .model import read_plan
    from .preflight import check_job
    from .shared_pool import SharedServerPool
    with command_errors():
        if (plan_dir is None) == (database is None):
            raise ValueError('Provide exactly one of --plan-dir or --database')
        gpu_ids = [int(value) for value in gpus.split(',')]
        if database is not None:
            from .store import SQLiteJobStore
            store = SQLiteJobStore(database)
            plan_dir = database.parent
            jobs = store.load_jobs()
            statuses = None if all_rows else {JobStatus.PENDING}
            checked = [job for job in jobs if statuses is None or job.status in statuses]
        else:
            jobs = read_plan(plan_dir/'plan.tsv')
            if not jobs:
                raise ValueError('Empty or missing plan')
            checked = [job for job in jobs if all_rows or job.status == JobStatus.PENDING]
        validate_graph(jobs)
        pool = SharedServerPool(plan_dir, gpu_ids)
        try:
            runner = DatabaseRunner(plan_dir, None, gpu_ids, pool)
            failures = []
            for job in checked:
                issues = []
                try:
                    runner._validate(job)
                except (ValueError, KeyError, RuntimeError) as exc:
                    issues.append(f'definition: {exc}')
                issues.extend(check_job(job))
                if issues:
                    failures.append({'job_id': job.job_id, 'issues': issues})
            typer.echo(json.dumps({'pending': len(checked), 'failures': failures,
                'scope': 'definition and availability checks only; no scripts run, '
                'real-model parity and free-GPU checks separate'}))
            if failures:
                raise typer.Exit(1)
        finally:
            pool.shutdown()


@database_app.command('backup')
def backup_database(database: Path = typer.Option(...), output: Path = typer.Option(...)) -> None:
    """Consistent SQLite backup including committed WAL transactions."""
    with command_errors():
        if not database.is_file() or output.exists():
            raise ValueError('Existing source and new backup path required')
        output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents overwriting a concurrently created backup.
        with output.open('x'):
            pass
        try:
            open_existing(database).backup(output)
        except BaseException:
            output.unlink(missing_ok=True)
            raise
        typer.echo(str(output.resolve()))


@database_app.command('edit')
def edit_database(database: Path = typer.Option(...), job_id: str = typer.Option(...),
                  patch: Path = typer.Option(..., help='JSON object of explicit definition fields.')) -> None:
    """Change definitions transactionally; never replay stale TSV runtime state."""
    with command_errors():
        changes = open_existing(database).update_jobs({job_id:read_definition_patch(patch)})
        typer.echo(json.dumps(changes[job_id].to_row(),sort_keys=True))


@database_app.command('reset')
def reset_database(database: Path = typer.Option(...), job_id: list[str] = typer.Option(...),
                   yes: bool = typer.Option(False, help='Confirm reset to pending/attempt0; running claims cannot be reset.')) -> None:
    with command_errors():
        if not yes: raise ValueError('Reset requires --yes')
        if len(set(job_id)) != len(job_id): raise ValueError('Duplicate job IDs')
        changes = open_existing(database).update_jobs({key:{'status':JobStatus.PENDING,'attempt':0} for key in job_id})
        typer.echo(json.dumps({'reset':list(changes)}))


def set_dispatch_lock(database: Path, locked: bool, reason: str) -> None:
    store = open_existing(database)
    # The store must fence claim_jobs in the same transaction as its lock check;
    # an external file flag alone cannot safely implement this command.
    store.set_admin_lock(locked)
    typer.echo(json.dumps({'database':str(database.resolve()),'dispatch_locked':locked,'reason':reason}))


@database_app.command('lock')
def lock_database(database: Path = typer.Option(...), reason: str = typer.Option('Administrative dispatch pause')) -> None:
    """Stop new claims; permit already-running jobs to finish."""
    with command_errors():
        set_dispatch_lock(database, True, reason)


@database_app.command('unlock')
def unlock_database(database: Path = typer.Option(...)) -> None:
    with command_errors():
        set_dispatch_lock(database, False, '')


RECOVERY_GUIDANCE = """Manual crashed-claim recovery (no automatic restart):
1. Lock dispatch with database lock. Keep it locked throughout reconciliation.
2. Stop the owning runner and verify its recorded PID/process identity is gone.
   Independently verify every owned worker/server/request for the claim has
   stopped, including remote workers. A dead runner does NOT prove worker exit.
   Do not signal unrelated processes; do not replay unknown outstanding work.
3. Acquire LOCK_EX|LOCK_NB on the exact absolute database path + '.runner.lock'
   using fcntl.flock, and hold the file open for the entire recovery operation.
   If acquisition fails, do not recover. This fences new DatabaseRunner starts.
4. With the operator-recorded expected token, use the store's atomic compare:

   store = SQLiteJobStore(absolute_database_path)
   assert store.get_admin_lock()
   recovered = store.finish(job_id, expected_token, {'status': JobStatus.FAILED})

   A False result means stale/unknown/already-finished token: inspect, do not
   fetch a fresh token and blindly retry. Record the evidence and result.
5. Release the lifetime flock only after recovery is recorded. FAILED does not
   restart work. Explicit database reset --job-id ID --yes may later authorize
   a retry; unlocking dispatch is a separate deliberate operation.

Inspect owners/jobs/<token> and owners/servers process receipts (PID, boot ID,
process start ticks) alongside runtime.json. These identify spawned parents,
not proof that every descendant is gone. Verify child processes and GPU work
independently. There is no automated recover command or automatic orphan kill.
reset never resets RUNNING claims.
"""


@database_app.command('recovery-help')
def recovery_help() -> None:
    """Print the token-fenced manual recovery procedure; mutate nothing."""
    typer.echo(RECOVERY_GUIDANCE)
