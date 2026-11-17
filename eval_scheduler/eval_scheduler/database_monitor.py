"""Read-only database scheduler monitoring, independent of TSV and GPU ownership.

Runner/monitor interface (atomic JSON replacement by the runner):
  database.json: {"database": "/absolute/jobs.sqlite"}
  runtime.json: {"schema_version": 1, "updated_at": <Unix seconds>,
    "database": "/absolute/jobs.sqlite", "shared": {"accepting": true,
      "capacity_per_gpu": 1024, "queued": 0, "slots": {
        "0": {"active": 2, "queued": 0, "capacity": 1024, "job_ids": ["a", "b"]}}},
    "active_jobs": {"a": {"gpus": [0], "phase": "client", "started_at": <Unix seconds>}},
    "cpu": <CpuBudget.snapshot()>, "training": {"job_id": "train", "gpus": [0,1]}}

Only database status is authoritative. The optional snapshot is asynchronous
telemetry, not a transaction with SQLite. Unknown counters stay unknown; stale
or mismatched snapshots never constitute evidence that a job/process is live.
No store constructor, schema creation, process inspection, signaling or writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import shutil
from pathlib import Path
import sqlite3
import time
from typing import Any

from .store import READY_SQL
from .model import Job


def _json(path: Path) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    value = json.loads(path.read_text(), object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object")
    return value


def _path(base: Path, value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else base / path).resolve()


def _count(value):
    return value if type(value) is int and value >= 0 else None


def _ids(value):
    return list(dict.fromkeys(str(x) for x in value)) if isinstance(value, list) else []


def _safe(value) -> str:
    return ''.join(c if c.isprintable() else ' ' for c in str(value))


def _short(value, width=64):
    text = _safe(value)
    return text if len(text)<=width else text[:width-3]+'...'


def _list(values, limit=3):
    return ', '.join(_short(v,48) for v in values[:limit]) + (f' (+{len(values)-limit} more)' if len(values)>limit else '')


def read_status(plan_dir: Path, *, database: Path | None = None,
                snapshot_path: Path | None = None, gpus: list[int] | None = None,
                now: float | None = None, stale_after: float = 30,
                max_jobs: int = 500, progress_limit: int = 12) -> dict[str, Any]:
    """Read one bounded SQLite transaction plus a separately timestamped snapshot.

    Explicit database permits monitoring without a marker. Relative marker
    paths are resolved against plan_dir, never the shell working directory.
    Missing databases fail without creating them. Telemetry failure is reported
    as a warning while database status remains available.
    """
    if type(max_jobs) is not int or max_jobs < 1:
        raise ValueError("max_jobs must be positive")
    if type(progress_limit) is not int or not 0<=progress_limit<=256:
        raise ValueError('progress_limit must be between 0 and 256')
    if not math.isfinite(stale_after) or stale_after < 0:
        raise ValueError("stale_after must be finite and nonnegative")
    plan_dir = Path(plan_dir).resolve()
    marker = _json(plan_dir / 'database.json') if database is None else {}
    database = _path(plan_dir, str(database or marker['database']))
    default_snapshot = 'runtime.json' if (plan_dir/'runtime.json').exists() or not (plan_dir/'database_snapshot.json').exists() else 'database_snapshot.json'
    snapshot_path = _path(plan_dir, str(snapshot_path or marker.get('snapshot_path', default_snapshot)))
    now = time.time() if now is None else now
    warnings = []
    db = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=2)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (1,2):
            raise ValueError("Unsupported scheduler database schema")
        counts = {s: 0 for s in ('pending','running','done','failed','skipped')}
        counts.update({r[0]: r[1] for r in db.execute('SELECT status,COUNT(*) FROM jobs GROUP BY status')})
        ready_sql = READY_SQL.format(candidates='jobs j',candidate_filter='')
        params = dict(limit=-1,detail_limit=max_jobs)
        dependency_ready = db.execute('SELECT COUNT(*) FROM (' + ready_sql + ')',params).fetchone()[0]
        dispatch_locked = bool(db.execute('SELECT locked FROM administration WHERE singleton=1').fetchone()[0]) if version==2 else False
        ready_count = 0 if dispatch_locked else dependency_ready
        ready = [] if dispatch_locked else [r[0] for r in db.execute(
            'SELECT job_id FROM (' + ready_sql + ') LIMIT :detail_limit',params)]
        def job_row(row):
            return dict(json.loads(row['definition']), status=row['status'],
                        attempt=str(row['attempt']), log_dir=row['log_dir'])
        ready_rows = [] if dispatch_locked else db.execute(
            'SELECT * FROM (' + ready_sql + ') LIMIT :detail_limit', params).fetchall()
        ready_details = [job_row(row) for row in ready_rows]
        blocked_rows = db.execute(
            "SELECT * FROM jobs WHERE status='pending' AND job_id NOT IN "
            '(SELECT job_id FROM (' + ready_sql + ')) ORDER BY position LIMIT :detail_limit',
            params).fetchall()
        blocked_details = []
        for row in blocked_rows:
            deps = db.execute(
                'SELECT p.job_id,p.status FROM dependencies d JOIN jobs p ON p.job_id=d.dependency '
                "WHERE d.job_id=? AND p.optional=0 AND p.status<>'done'", (row['job_id'],)).fetchall()
            blocked_details.append((job_row(row), [f'{d[0]}:{d[1]}' for d in deps]))
        rows = db.execute("SELECT job_id,status,definition,attempt,log_dir FROM jobs "
                          "WHERE status='running' ORDER BY position LIMIT ?", (max_jobs,)).fetchall()
        active = {}; definitions = {}
        for row in rows:
            definition = json.loads(row['definition'])
            definitions[row['job_id']] = dict(definition,status=row['status'],attempt=str(row['attempt']),log_dir=row['log_dir'])
            active[row['job_id']] = dict(job_id=row['job_id'],status=row['status'],
                action=definition.get('action','unknown'),name=definition.get('name',''),
                family=definition.get('family',''),attempt=row['attempt'],log_dir=row['log_dir'])
    finally:
        db.close()
    truncated = max(0, counts['running'] - len(active))
    if truncated:
        warnings.append(f"Active job details truncated: {truncated} additional running jobs")
    telemetry = {}; age = None; stale = True
    try:
        telemetry = _json(snapshot_path)
        if telemetry.get('schema_version', 1) != 1:
            raise ValueError('Unsupported snapshot schema')
        if telemetry.get('database') and _path(plan_dir, telemetry['database']) != database:
            raise ValueError('Snapshot belongs to another database')
        timestamp = telemetry.get('updated_at')
        if type(timestamp) not in (int,float) or not math.isfinite(timestamp):
            raise ValueError('Snapshot lacks a finite Unix updated_at timestamp')
        age = now - timestamp
        stale = age < -5 or age > stale_after
        if stale:
            warnings.append('Runtime snapshot stale or clock-skewed; counters are last reported, not live')
    except (OSError,ValueError,TypeError) as exc:
        warnings.append(f"Runtime snapshot unavailable: {type(exc).__name__}: {exc}")
        telemetry = {}
    shared = telemetry.get('shared', {})
    shared = shared if isinstance(shared,dict) else {}
    slots = shared.get('slots', {})
    slots = slots if isinstance(slots,dict) else {}
    assignments = telemetry.get('active_jobs', {})
    assignments = assignments if isinstance(assignments,dict) else {}
    gpu_ids = {str(g) for g in (gpus or [])} | set(slots)
    for job_id, entry in assignments.items():
        if job_id in active and isinstance(entry,dict):
            gpu_ids.update(_ids(entry.get('gpus')))
    training = [j for j,v in active.items() if v['action']=='train_until_step']
    train_info = telemetry.get('training', {})
    if isinstance(train_info,dict) and train_info.get('job_id') in training:
        gpu_ids.update(_ids(train_info.get('gpus')))
    per_gpu = {}
    assigned = set()
    for gpu in sorted(gpu_ids):
        slot = slots.get(gpu, {})
        slot = slot if isinstance(slot,dict) else {}
        candidates = _ids(slot.get('job_ids'))
        candidates += [j for j,e in assignments.items() if isinstance(e,dict) and gpu in _ids(e.get('gpus'))]
        jobs = sorted(set(candidates) & active.keys())
        assigned.update(jobs)
        per_gpu[gpu] = dict(job_ids=jobs,client_jobs=[j for j in jobs if j not in training],
            job_mapping_known='job_ids' in slot or any(isinstance(e,dict) and gpu in _ids(e.get('gpus')) for e in assignments.values()),
            active=_count(slot.get('active')),queued=_count(slot.get('queued')),
            capacity=_count(slot.get('capacity',shared.get('capacity_per_gpu'))),
            provisioning=slot.get('provisioning'),training=training)
    cpu = telemetry.get('cpu', {})
    cpu = cpu if isinstance(cpu,dict) else {}
    cpu_jobs = [j for j,e in assignments.items() if j in active and isinstance(e,dict)
                and e.get('phase') in ('cpu','prepare','preparation')]
    # Log inspection happens after the short database transaction, once per job,
    # not once per GPU. Training is always prioritized in the bounded detail view.
    from .monitor import job_progress, progress_eta, fmt_seconds
    progress_jobs = list(dict.fromkeys(training+list(active)))[:progress_limit]
    for job_id in progress_jobs:
        info = active[job_id]
        info.update(progress='unknown',eta='unknown',elapsed='unknown',fraction=None)
        assignment = assignments.get(job_id,{})
        start = assignment.get('started_at') if isinstance(assignment,dict) else None
        elapsed = now-start if type(start) in (int,float) and math.isfinite(start) and start<=now else None
        if elapsed is not None:info['elapsed']=fmt_seconds(elapsed)
        if not info['log_dir']:
            definition = definitions[job_id]
            metadata = json.loads(definition.get('metadata_json') or '{}')
            cooperative = metadata.get('cooperative_training') or {}
            if definition.get('action') != 'train_until_step' or not cooperative.get('control_root'):
                continue  # Never inspect an implicit working directory.
        try:
            progress = job_progress(Job.from_row(definitions[job_id]))
            info.update(progress=progress.text,fraction=progress.fraction)
            if progress.eta_seconds is not None or elapsed is not None:
                info['eta']=progress_eta(progress,elapsed or 0)
        except (OSError,ValueError,TypeError,KeyError) as exc:
            info['progress']='unavailable ('+type(exc).__name__+')'
    return dict(database=str(database),snapshot_path=str(snapshot_path),now=now,
        counts=counts,total=sum(counts.values()),ready_count=ready_count,ready=ready,
        blocked_pending=counts['pending']-dependency_ready,dispatch_locked=dispatch_locked,
        dependency_ready=dependency_ready,active_jobs=active,
        active_details_truncated=truncated,gpus=per_gpu,training=training,cpu=cpu,cpu_jobs=cpu_jobs,
        progress_jobs=progress_jobs,definitions=definitions,
        ready_details=ready_details,blocked_details=blocked_details,
        unassigned_clients=sorted(set(active)-assigned-set(cpu_jobs)-set(training)),
        queued_requests=_count(shared.get('queued')),accepting=shared.get('accepting'),
        snapshot_age=age,snapshot_stale=stale,warnings=warnings)


collect_status = read_status


def render_text(snapshot: dict) -> str:
    def number(value):
        return '?' if value is None else str(value)
    counts = snapshot['counts']
    lines = [datetime.fromtimestamp(snapshot['now'],timezone.utc).isoformat(),
        'jobs ' + ' '.join(f'{k}={v}' for k,v in counts.items()) +
        f" ready={snapshot['ready_count']} blocked={snapshot['blocked_pending']} total={snapshot['total']} "
        f"dispatch_locked={snapshot['dispatch_locked']}",
        f"telemetry {'STALE/UNKNOWN' if snapshot['snapshot_stale'] else 'fresh'} "
        f"age={number(snapshot['snapshot_age'])}s queued_requests={number(snapshot['queued_requests'])}"]
    if snapshot['training']:
        lines.append('TRAINING ALL GPUs: ' + _list(snapshot['training']))
    for gpu,entry in snapshot['gpus'].items():
        client_count = str(len(entry['client_jobs'])) if entry['job_mapping_known'] else '?'
        if snapshot['active_details_truncated'] and entry['job_mapping_known']:
            client_count = '>='+client_count
        lines.append(f"GPU{gpu}: requests active={number(entry['active'])} queued={number(entry['queued'])} "
            f"capacity={number(entry['capacity'])}; client_jobs={client_count} "
            + _list(entry['client_jobs']) + ('; TRAINING ALL GPUs' if entry['training'] else ''))
    cpu = snapshot['cpu']
    lines.append('CPU preparation ' + ' '.join(f'{k}={number(_count(cpu.get(k)))}'
        for k in ('total_cores','reserve_cores','capacity','available_cores')) +
        '; jobs=' + _list(snapshot['cpu_jobs']))
    if snapshot['unassigned_clients']:
        lines.append('Running/unassigned (not pinned to a GPU): ' + _list(snapshot['unassigned_clients']))
    for job_id in snapshot.get('progress_jobs',[]):
        info=snapshot['active_jobs'][job_id]
        lines.append(f"  {_short(job_id,40)} {_short(info['family']+':'+info['name'],48)} "
                     f"{_short(info.get('progress','unknown'),64)} ETA {info.get('eta','unknown')}")
    lines.append('Next ready: ' + _list(snapshot['ready'],3))
    if snapshot['ready_count']>12:
        lines.append(f"... {snapshot['ready_count']-12} more ready")
    lines.extend('WARNING: '+warning for warning in snapshot['warnings'])
    return '\n'.join(_safe(line) for line in lines)


def status_text(plan_dir: Path, **kwargs) -> str:
    return render_text(read_status(plan_dir, **kwargs))


def rich_status_renderable(plan_dir: Path, **kwargs):
    from rich.console import Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from .monitor import gpu_infos, task_first_label, compact_job_id

    terminal = shutil.get_terminal_size(fallback=(120, 40))
    # Recompute both dimensions on every refresh, including after tmux resizing.
    kwargs.setdefault('max_jobs', max(256, terminal.lines))
    kwargs.setdefault('progress_limit', 256)
    snapshot = read_status(plan_dir, **kwargs)
    counts = snapshot['counts']
    summary = '  '.join([
        *(f'{key}={counts[key]}' for key in ('done', 'running')),
        f"ready={snapshot['ready_count']} blocked={snapshot['blocked_pending']}",
        f"failed={counts['failed']} skipped={counts['skipped']} total={snapshot['total']}",
    ])
    cpu = snapshot['cpu']
    footer = (datetime.fromtimestamp(snapshot['now']).astimezone().isoformat(timespec='seconds') +
              f"  CPU available/capacity={cpu.get('available_cores', '?')}/{cpu.get('capacity', '?')}")
    if snapshot['dispatch_locked']:
        summary += '  DISPATCH LOCKED'
    if snapshot['warnings']:
        footer += '  WARNING: ' + '; '.join(snapshot['warnings'])
    summary_text = Text(_safe(summary) + '\n' + _safe(footer), no_wrap=True, overflow='ellipsis')

    def table(title, columns):
        result = Table(title=title, expand=True, padding=(0, 1))
        for name, ratio in columns:
            result.add_column(name, ratio=ratio, no_wrap=True, overflow='ellipsis')
        return result

    def label(job_id):
        job = Job.from_row(snapshot['definitions'][job_id])
        return Text(_safe(f'{task_first_label(job)} | batch {job.retry_batch()} '
                          f"attempt {job.attempt} elapsed {snapshot['active_jobs'][job_id].get('elapsed', '?')} "
                          f'{compact_job_id(job_id)}'))

    def progress(job_id):
        info = snapshot['active_jobs'][job_id]
        fraction = info.get('fraction')
        prefix = f'{fraction * 100:.1f}% ' if fraction is not None else ''
        return Text(_safe(prefix + info.get('progress', 'unknown'))), info.get('eta', 'unknown')

    lanes = table('Running jobs', [('Lane', None), ('Mem', None), ('Util', None),
                                   ('Task', 4), ('Progress', 2), ('ETA', None)])
    gpu_ids = sorted(int(g) for g in snapshot['gpus'])
    infos = gpu_infos(gpu_ids)
    extra = []
    shown = set()
    for gpu in gpu_ids:
        entry = snapshot['gpus'][str(gpu)]
        info = infos[gpu]
        mem = (f'{info.used_mib / 1024:.1f}/{info.total_mib / 1024:.1f} GiB'
               if info.used_mib is not None and info.total_mib is not None else '?')
        util = f'{info.utilization}%' if info.utilization is not None else '?'
        ids = entry['training'] or entry['client_jobs']
        if ids:
            first, *others = ids
            task = label(first)
            if others:
                task = Text(f'[{len(ids)} clients] ') + task
            lanes.add_row(f'GPU{gpu}', mem, util, task, *progress(first))
            shown.add(first)
            extra.extend((f'GPU{gpu}', j) for j in others if j not in shown)
        else:
            state = ('snapshot stale/unknown' if snapshot['snapshot_stale'] else
                     'starting server' if entry['provisioning'] else
                     'idle' if entry['job_mapping_known'] else 'no assigned client')
            lanes.add_row(f'GPU{gpu}', mem, util, state, '', '')
    extra.extend(('CPU', j) for j in snapshot['active_jobs']
                 if j not in shown and j not in {item[1] for item in extra})
    # One row per GPU, then additional shared clients/CPU jobs as space permits.
    # Three tables cost 15 lines, header 3, and reserve two terminal edge lines.
    budget = max(3, terminal.lines - 21 - len(gpu_ids))
    extra_capacity = min(len(extra), max(1, budget // 2)) if extra else 0
    extra_limit = extra_capacity if len(extra) <= extra_capacity else max(0, extra_capacity - 1)
    for lane, job_id in extra[:extra_limit]:
        lanes.add_row(lane, '-', '-', label(job_id), *progress(job_id))
    if len(extra) > extra_limit:
        lanes.add_row('CPU/GPU', '-', '-', f'... {len(extra) - extra_limit} more running', '', '')
    budget -= extra_capacity
    ready_count = snapshot['ready_count']
    blocked_count = snapshot['blocked_pending']
    ready_capacity = min(max(1, ready_count), max(1, budget // 3))
    blocked_capacity = min(max(1, blocked_count), max(1, budget - ready_capacity))
    spare = budget - ready_capacity - blocked_capacity
    if spare > 0:
        ready_capacity += min(spare, max(0, ready_count - ready_capacity))

    ready = table('Next ready', [('Job', None), ('Action', None), ('Task', 4),
                                 ('Shard', None), ('Batch', None)])
    limit = ready_capacity if ready_count <= ready_capacity else max(0, ready_capacity - 1)
    ready_jobs = snapshot['ready_details'][:limit]
    for row in ready_jobs:
        job = Job.from_row(row)
        ready.add_row(compact_job_id(job.job_id, 24), job.action.value,
                      Text(_safe(task_first_label(job))),
                      f'{job.shard}/{job.shards}' if job.shard is not None else '-', str(job.retry_batch()))
    if ready_count > len(ready_jobs):
        ready.add_row(f'... {ready_count - len(ready_jobs)} more', '', '', '', '')
    if not ready_count:
        ready.add_row('none', '', '', '', '')
    blocked = table('Blocked pending', [('Job', None), ('Task', 2), ('Blocked by', 3)])
    limit = blocked_capacity if blocked_count <= blocked_capacity else max(0, blocked_capacity - 1)
    blocked_jobs = snapshot['blocked_details'][:limit]
    for row, deps in blocked_jobs:
        job = Job.from_row(row)
        blocked.add_row(compact_job_id(job.job_id, 24), Text(_safe(task_first_label(job))),
                        Text(_safe(', '.join(compact_job_id(d, 36) for d in deps[:6]))))
    if blocked_count > len(blocked_jobs):
        blocked.add_row(f'... {blocked_count - len(blocked_jobs)} more', '', '')
    if not blocked_count:
        blocked.add_row('none', '', '')
    return Group(Panel(summary_text, title='Database eval scheduler', expand=True, height=4),
                 lanes, ready, blocked)


def watch(plan_dir: Path, *, interval: float = 2, **kwargs) -> None:
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError('interval must be positive and finite')
    while True:
        print(status_text(plan_dir, **kwargs),flush=True)
        time.sleep(interval)


def rich_watch(plan_dir: Path, *, interval: float = 2, **kwargs) -> None:
    from rich.live import Live
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError('interval must be positive and finite')
    with Live(rich_status_renderable(plan_dir, **kwargs),refresh_per_second=max(.05,1/interval)) as live:
        while True:
            time.sleep(interval)
            live.update(rich_status_renderable(plan_dir, **kwargs))
