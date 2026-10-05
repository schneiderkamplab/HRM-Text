"""Queue existing compact W4 controller after proven Baltic audit completion."""
import argparse
import asyncio
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from types import FunctionType

from . import baltic_compact_successor as baltic
from . import wave4_synthetic_campaign as base
from . import wave_compact_review as compact
from .generation_constraints import apply_request
from .io import digest, file_hash, load, lock, write_json


def controller(owner=None):
    c = compact.install(base.controller())
    original = c.v6.generation_request
    c.v6.generation_request = lambda *a, **k: apply_request(original(*a, **k))
    # Reuse the tested private128 runner bytecode with W4's private globals.
    runner = baltic.controller().execute
    c.execute = FunctionType(runner.__code__, c.__dict__, runner.__name__, runner.__defaults__)
    from . import wave4_async_runtime as runtime
    runtime.widen(c.execute, 128)
    c.verify = lambda root: verify(root, c)
    return runtime.install(c, owner) if owner is not None else c


def verify(root, c=None):
    m = base.verify(root, c or controller())
    if (m.get('successor') != 'wave4-compact-after-baltic-v1'
            or m['max_concurrency_per_server'] != 768
            or m.get('io_runtime_module') != 'dfm12.wave4_async_runtime'
            or m.get('admission_spacing_seconds') != 0):
        raise ValueError('W4 successor policy mismatch')
    return m


def prepare(root, baltic_root):
    baltic_proof_controller(baltic_root)
    base.prepare(root, Path('data/dfm13/wave4/seeds'), base.european.TOKENIZER_DIR)
    m = load(root / 'manifest.json')
    history = {}
    for prior in sorted(Path('data/dfm13/wave4').glob('synthetic*')):
        if prior.resolve() == root.resolve() or not (prior / 'manifest.json').exists():
            continue
        with sqlite3.connect((prior / 'jobs.sqlite').resolve().as_uri() + '?mode=ro', uri=True) as db:
            counts = dict(db.execute('SELECT status,count(*) FROM jobs GROUP BY status'))
        # Existing populated history requires explicit source/cursor/dedup import,
        # not silent reset or implicit approval. Current staged ledgers are empty.
        if counts:
            raise ValueError('Populated W4 history requires explicit migration: ' + str(prior))
        history[str(prior.resolve())] = dict(manifest_sha256=file_hash(prior/'manifest.json'), counts=counts)
    for path in (Path(__file__), Path(baltic.__file__), Path(compact.__file__), Path('dfm12/generation_constraints.py'),
                 Path('dfm12/wave4_async_runtime.py'), Path('dfm12/baltic_async_io.py')):
        m['implementation_pins'][str(path.resolve())] = file_hash(path)
    m.update(successor='wave4-compact-after-baltic-v1', max_concurrency_per_server=768,
        default_concurrency_per_server=768, calibration_required_before_bulk=False,
        io_runtime_module='dfm12.wave4_async_runtime', admission_spacing_seconds=0,
        prerequisite=str(baltic_root.resolve()), preserved_staged_history=history,
        authorization='User2026-10-04:770K W4 after successful Baltic generation and audit;768/server26B, zero fixed spacing and asynchronous I/O',
        repair_policy='repair verdicts are unaccepted holds; no implicit repair or approval; fresh audit required for any credited repaired target')
    write_json(root/'manifest.json', m)
    sha = file_hash(root/'manifest.json')
    write_json(root/'seal.json', dict(manifest_sha256=sha))
    with sqlite3.connect(root/'jobs.sqlite') as db:
        db.execute("UPDATE metadata SET value=? WHERE key='manifest_sha256'", (sha,))
    verify(root)
    queue = dict(baltic=str(baltic_root.resolve()), wave4=str(root.resolve()),
        baltic_manifest_sha256=file_hash(baltic_root/'manifest.json'), wave4_manifest_sha256=sha,
        handoff_implementation_sha256=file_hash(__file__), state='waiting', launch_attempts=0)
    write_json(root/'handoff.json', queue)
    return queue


def readiness(groups, running, phase):
    exhausted = [dict(language=g[0], family=g[1], target=g[2], accepted=g[3], attempts=g[5])
                 for g in groups if g[3] < g[2] and g[5] >= 6*g[2]]
    if exhausted:
        return dict(state='blocked_attempt_budget', exhausted=exhausted)
    if phase in ('blocked', 'interrupted_or_failed', 'drained', 'approved_groups_finished'):
        return dict(state='blocked_baltic_terminal', phase=phase)
    if not groups or running or any(g[3] != g[2] or g[4] for g in groups):
        return dict(state='waiting', accepted=sum(g[3] for g in groups), active=sum(g[4] for g in groups))
    if phase != 'complete':
        return dict(state='waiting_final_complete_receipt')
    return dict(state='ready_for_evidence_check')


def inspect_baltic(root):
    with sqlite3.connect((root/'jobs.sqlite').resolve().as_uri()+'?mode=ro', uri=True) as db:
        db.execute('BEGIN')
        groups = db.execute('SELECT language,family,target,accepted,active,attempts FROM groups').fetchall()
        running = db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]
    return readiness(groups, running, load(root/'progress.json')['phase'])


def baltic_proof_controller(root):
    if baltic_client_module(root) == 'dfm12.baltic_concurrency768':
        from .baltic_concurrency768 import controller as concurrency768_controller
        c = concurrency768_controller()
        c.verify(root)
        return c
    if baltic_client_module(root) == 'dfm12.baltic_zero_spacing':
        from .baltic_zero_spacing import controller as zero_controller
        c = zero_controller()
        c.verify(root)
        return c
    if baltic_client_module(root) == 'dfm12.baltic_io_runtime':
        from .baltic_io_runtime import controller as io_controller
        c = io_controller()
        c.verify(root)
        return c
    if baltic_client_module(root) == 'dfm12.baltic_concurrency384':
        from .baltic_concurrency384 import controller as concurrency_controller
        c = concurrency_controller()
        c.verify(root)
        return c
    adapter = load(root/'manifest.json').get('technical_review_adapter')
    if adapter is None:
        c = baltic.controller()
        baltic.verify(root, c)
        return c
    if adapter != 'dfm12.compact_keep_rationale':
        raise ValueError('Unknown Baltic technical review adapter')
    from .compact_keep_recovery import controller as recovery_controller
    c = recovery_controller()
    c.verify(root)
    return c


def baltic_client_module(root):
    manifest = load(root/'manifest.json')
    io_runtime = manifest.get('io_runtime_module')
    zero_runtime = manifest.get('zero_spacing_runtime_module')
    concurrency768 = manifest.get('concurrency768_runtime_module')
    if concurrency768 is not None:
        if (concurrency768 != 'dfm12.baltic_concurrency768'
                or manifest.get('effective_concurrency_per_server') != 768
                or zero_runtime != 'dfm12.baltic_zero_spacing'
                or manifest.get('admission_spacing_seconds') != 0
                or io_runtime != 'dfm12.baltic_io_runtime'
                or manifest.get('runtime_module') != 'dfm12.baltic_concurrency384'
                or manifest.get('runtime_concurrency_per_server') != 384
                or manifest.get('technical_review_adapter') != 'dfm12.compact_keep_rationale'):
            raise ValueError('Unknown Baltic768 runtime policy')
        return concurrency768
    if zero_runtime is not None:
        if (zero_runtime != 'dfm12.baltic_zero_spacing'
                or manifest.get('admission_spacing_seconds') != 0
                or io_runtime != 'dfm12.baltic_io_runtime'
                or manifest.get('runtime_module') != 'dfm12.baltic_concurrency384'
                or manifest.get('runtime_concurrency_per_server') != 384
                or manifest.get('technical_review_adapter') != 'dfm12.compact_keep_rationale'):
            raise ValueError('Unknown Baltic zero-spacing runtime policy')
        return zero_runtime
    if io_runtime is not None:
        if (io_runtime != 'dfm12.baltic_io_runtime'
                or manifest.get('runtime_module') != 'dfm12.baltic_concurrency384'
                or manifest.get('runtime_concurrency_per_server') != 384
                or manifest.get('technical_review_adapter') != 'dfm12.compact_keep_rationale'):
            raise ValueError('Unknown Baltic I/O runtime policy')
        return io_runtime
    runtime = manifest.get('runtime_module')
    if runtime is not None:
        if (runtime != 'dfm12.baltic_concurrency384'
                or manifest.get('runtime_concurrency_per_server') != 384
                or manifest.get('technical_review_adapter') != 'dfm12.compact_keep_rationale'):
            raise ValueError('Unknown Baltic runtime policy')
        return runtime
    adapter = manifest.get('technical_review_adapter')
    if adapter is None:
        return 'dfm12.baltic_compact_successor'
    if adapter != 'dfm12.compact_keep_rationale':
        raise ValueError('Unknown Baltic technical review adapter')
    return 'dfm12.compact_keep_recovery'


def audit_completion(root, output):
    """Recheck every quota-crediting raw generation/review before handoff."""
    c = baltic_proof_controller(root)
    if inspect_baltic(root)['state'] != 'ready_for_evidence_check':
        raise ValueError('Baltic not successful and quiescent')
    counts = {}
    with sqlite3.connect((root/'jobs.sqlite').resolve().as_uri()+'?mode=ro', uri=True) as db:
        expected = {(l,f):n for l,f,n in db.execute('SELECT language,family,target FROM groups')}
        with (output/'accepted-audit-proof.jsonl').open('x') as handle:
            for key,language,family,spec,outcome,workdir in db.execute(
                    "SELECT id,language,family,spec_json,outcome_json,workdir FROM jobs WHERE status='accepted' ORDER BY id"):
                value=json.loads(outcome)
                if value.get('effective_keep') is not True or value.get('repair_requested') is True:
                    raise ValueError('Accepted row lacks final passing verdict')
                candidate, paths = c.validate_saved_keep(Path(workdir),key,json.loads(spec),value)
                accepted = load(Path(workdir)/'accepted'/f'{key}.json')
                if any(accepted[k] != candidate[k] for k in ('messages','tools','provenance')):
                    raise ValueError('Materialized final differs from reviewed candidate')
                owner = db.execute('SELECT owner FROM fingerprints WHERE fingerprint=?', (value['fingerprint'],)).fetchone()
                if owner != (key,):
                    raise ValueError('Accepted fingerprint lacks unique owner')
                handle.write(json.dumps(dict(id=key, fingerprint=value['fingerprint'],
                    pins={str(p.resolve()):file_hash(p) for p in paths}))+'\n')
                counts[(language,family)] = counts.get((language,family),0)+1
                if sum(counts.values()) % 1000 == 0:
                    write_json(output/'handoff-status.json',dict(state='verifying_accepted_audits',
                        verified=sum(counts.values()),total=140000,time=time.time()))
    if counts != expected:
        raise ValueError('Accepted audit count does not match every quota')
    result=dict(total=sum(counts.values()), groups={str(k):v for k,v in counts.items()},
        proof_sha256=file_hash(output/'accepted-audit-proof.jsonl'),
        baltic_manifest_sha256=file_hash(root/'manifest.json'), successful=True)
    write_json(output/'baltic-completion-verified.json',result)
    return result


def verify_independent_launch(root):
    """Explicit user-authorized GPU handoff; raw proof still gates publication."""
    verify(root)
    config = load(root/'handoff.json')
    parent = Path(config['baltic'])
    receipt = load(root/'independent-launch-authorization.json')
    if (receipt.get('authorization') != 'User2026-10-04:start770K_now_defer_raw_proof_to_publication'
            or receipt.get('baltic_publication_authorized') is not False
            or receipt['baltic_manifest_sha256'] != file_hash(parent/'manifest.json')
            or receipt['wave4_manifest_sha256'] != file_hash(root/'manifest.json')):
        raise ValueError('Explicit independent launch authorization/pins required')
    baltic_proof_controller(parent)
    if inspect_baltic(parent)['state'] != 'ready_for_evidence_check':
        raise ValueError('Baltic not complete and quiescent')
    with sqlite3.connect((parent/'jobs.sqlite').resolve().as_uri()+'?mode=ro', uri=True) as db:
        db.execute('BEGIN')
        accepted = dict(((l,f),n) for l,f,n in db.execute(
            "SELECT language,family,count(*) FROM jobs WHERE status='accepted' GROUP BY language,family"))
        targets = dict(((l,f),n) for l,f,n in db.execute('SELECT language,family,target FROM groups'))
        if accepted != targets or sum(accepted.values()) != 140000:
            raise ValueError('Accepted ledger counts differ from completed quotas')
        invalid = db.execute("SELECT count(*) FROM jobs j LEFT JOIN fingerprints f ON f.fingerprint=j.fingerprint "
            "WHERE j.status='accepted' AND (f.owner IS NULL OR f.owner!=j.id OR "
            "json_extract(j.outcome_json,'$.effective_keep') IS NOT 1 OR "
            "json_extract(j.outcome_json,'$.repair_requested') IS 1)").fetchone()[0]
        if invalid:
            raise ValueError('Accepted ledger lacks passing audit or fingerprint ownership')
    return parent


def watch(root, interval=30):
    with lock(root/'handoff.lock'):
        config=load(root/'handoff.json'); parent=Path(config['baltic'])
        if (config['handoff_implementation_sha256'] != file_hash(__file__)
                or config['wave4_manifest_sha256'] != file_hash(root/'manifest.json')):
            raise ValueError('Handoff pin drift')
        if (root/'launch-intent.json').exists():
            raise ValueError('Existing launch intent: inspect exact child; never duplicate')
        verify(root)
        missing_client = 0
        while True:
            if file_hash(parent/'manifest.json') != config['baltic_manifest_sha256']:
                raise ValueError('Baltic manifest changed; explicit rearm required')
            state=inspect_baltic(parent)
            write_json(root/'handoff-status.json',dict(time=time.time(),**state))
            if state['state'].startswith('blocked'):
                write_json(root/'handoff-blocked.json',dict(time=time.time(),**state,
                    action='Diagnose Baltic failure/cap; no W4 launch, no quality relaxation'))
                return
            if state['state']=='ready_for_evidence_check':
                break
            import psutil
            runtime = load(parent/'runtime.json')
            try:
                process = psutil.Process(runtime['pid'])
                alive = (process.status() != psutil.STATUS_ZOMBIE
                         and baltic_client_module(parent) in process.cmdline())
            except (psutil.Error, KeyError, TypeError):
                alive = False
            missing_client = 0 if alive else missing_client + 1
            if missing_client >= 3:
                write_json(root/'handoff-blocked.json',dict(state='blocked_baltic_client_missing',
                    time=time.time(),last_runtime=runtime,action='Inspect Baltic; no automatic restart or W4 launch'))
                return
            time.sleep(interval)
        # This lock proves the Baltic client has released ownership and prevents
        # a concurrent restart during final audit verification and W4 launch.
        with lock(parent/'controller.lock'):
            audit_completion(parent,root)
            verify(root)
            command=[sys.executable,'-u','-m','dfm12.wave4_compact_handoff','run','--root',str(root)]
            write_json(root/'launch-intent.json',dict(command=command,time=time.time(),attempt=1))
            with (root/'runner.log').open('ab',buffering=0) as log:
                child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            import psutil
            write_json(root/'launch.json',dict(pid=child.pid,create_time=psutil.Process(child.pid).create_time(),
                start_ticks=Path(f'/proc/{child.pid}/stat').read_text().split()[21],command=command))
            write_json(root/'handoff-status.json',dict(state='launched',pid=child.pid,time=time.time()))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','watch','run','verify','run-independent','verify-publication'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--baltic-root',type=Path,default=Path('data/dfm13/baltic/synthetic-compact-26b-20261004-v1'))
    a=p.parse_args()
    if a.command=='prepare':print(prepare(a.root,a.baltic_root))
    elif a.command=='verify':print(verify(a.root)['target'])
    elif a.command=='verify-publication':
        parent = Path(load(a.root/'handoff.json')['baltic'])
        with lock(parent/'controller.lock'):
            audit_completion(parent, a.root)
    elif a.command=='watch':
        try:watch(a.root)
        except Exception as exc:
            write_json(a.root/'handoff-blocked.json',dict(state='blocked_operational',error=repr(exc),time=time.time()))
            raise
    else:
        if a.command == 'run-independent':
            verify_independent_launch(a.root)
        else:
            config=load(a.root/'handoff.json')
            proof=load(a.root/'baltic-completion-verified.json')
            if (proof.get('successful') is not True or proof['total']!=140000
                    or proof['proof_sha256']!=file_hash(a.root/'accepted-audit-proof.jsonl')
                    or proof['baltic_manifest_sha256']!=config['baltic_manifest_sha256']):
                raise ValueError('Verified Baltic completion proof required')
        from .baltic_async_io import Owner
        owner = Owner()
        try:
            c=controller(owner)
            asyncio.run(c.execute(a.root,endpoints=[f'http://127.0.0.1:{port}/v1' for port in range(8800,8808)],
                                  concurrency=768,timeout=600,max_kv_cache_utilization=.90))
        finally:
            owner.close()


if __name__=='__main__':main()
