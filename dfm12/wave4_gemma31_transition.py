"""Explicit, gated 31B comparison handoff. Preparation never stops processes."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import runpy
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.request

from .io import load, write_json, file_hash, lock
from .diagnostic_server import identity, pidfd_open, pidfd_signal
from .wave31_endpoint_health import validate as validate_endpoint

MODEL = 'google/gemma-4-31B-it'
COMPARISON = Path('data/dfm13/wave4/gemma31-quality-comparison')
OLD = Path('logs/dfm13/baltic-audit-3081500/servers-compiled')


def alive(item):
    try:
        current = identity(item['pid'])
        state = Path(f"/proc/{item['pid']}/stat").read_text().rsplit(')', 1)[1].split()[0]
        return state != 'Z' and all(current[k] == item[k] for k in ('start_ticks', 'cmdline', 'session_id'))
    except (OSError, ProcessLookupError):
        return False


def model_files(path):
    config = load(path / 'config.json')
    if 'gemma4' not in config.get('model_type', '').replace('_', ''):
        raise ValueError('Not a Gemma4 configuration')
    index = load(path / 'model.safetensors.index.json')
    shards = sorted(set(index['weight_map'].values()))
    if not shards or any(not (path / s).is_file() or (path / s).stat().st_size == 0 for s in shards):
        raise ValueError('Incomplete weight shards')
    for name in ('tokenizer.json', 'tokenizer_config.json'):
        if not (path / name).is_file():
            raise ValueError('Missing tokenizer')
    return {str(path / name): file_hash(path / name) for name in
            ('config.json', 'model.safetensors.index.json', 'tokenizer_config.json')}


def terminal_database(path, deferral_authorization=None):
    with closing(sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro', uri=True)) as db:
        db.execute('BEGIN')
        counts = dict(db.execute('SELECT status,count(*) FROM jobs GROUP BY status'))
        allowed = {'done', 'failed'}
        if deferral_authorization is not None:
            from .fars_summary_deferral import authorized_jobs, load_proposal, STATUS
            authorization = Path(deferral_authorization)
            proposal, _ = load_proposal(authorization)
            if Path(proposal['queue']).resolve() != Path(path).resolve():
                raise ValueError('Deferral authorization is for another queue')
            authorized = authorized_jobs(authorization, db)
            deferred = {r[0] for r in db.execute('SELECT id FROM jobs WHERE status=?', (STATUS,))}
            if deferred != set(authorized):
                raise ValueError('Unrecognized deferred jobs; explicit hash-bound authorization required')
            allowed.add(STATUS)
    if any(status not in allowed for status in counts):
        raise ValueError(f'Nonterminal queue: {path}: {counts}')
    # deferred31B remains a distinct unfinished-work count, never a done count.
    return counts


def verify_comparison(root):
    manifest, index = load(root / 'manifest.json'), load(root / 'index.json')
    if manifest['model'] != MODEL or len(index) != 76:
        raise ValueError('Wrong comparison population/model')
    if file_hash(Path(manifest['controls'])) != manifest['controls_sha256']:
        raise ValueError('Controls changed')
    with closing(sqlite3.connect(f'file:{root.resolve()}/jobs.sqlite?mode=ro', uri=True)) as db:
        rows = {r[0]: json.loads(r[1]) for r in db.execute('SELECT id,payload FROM jobs')}
    if set(rows) != {r['job'] for r in index}:
        raise ValueError('Comparison queue/index mismatch')
    for row in index:
        if file_hash(Path(row['candidate'])) != row['candidate_sha256']:
            raise ValueError('Candidate changed')
        if rows[row['job']]['request']['model'] != MODEL:
            raise ValueError('A request targets a different model')
    return len(rows)


def readiness(contract):
    # This manifest is authored at handoff, not inferred from an empty queue while
    # upstream producers are still running. All paths/hashes are required.
    if contract.get('cpu_preparation_complete') is not True or contract.get('producers_frozen') is not True:
        raise ValueError('CPU completion and producer freeze not attested')
    for key in ('completion_receipts', 'databases', 'clients_and_producers'):
        if not contract.get(key):
            raise ValueError(f'Missing handoff inventory: {key}')
    for path, sha in contract['completion_receipts'].items():
        if file_hash(Path(path)) != sha:
            raise ValueError('Completion receipt changed')
    if any(alive(p) for p in contract['clients_and_producers']):
        raise ValueError('Owned client/producer still alive; drain first')
    authorizations = contract.get('deferred31B_authorizations', {})
    for database, directory in authorizations.items():
        if database not in contract['databases']:
            raise ValueError('Deferral authorization outside database inventory')
        for name in ('proposal.json', 'proposal-seal.json', 'receipt.json', 'receipt-seal.json'):
            path = str(Path(directory) / name)
            if contract['completion_receipts'].get(path) != file_hash(Path(path)):
                raise ValueError('Deferral evidence not pinned in handoff contract')
    return {p: terminal_database(p, authorizations.get(p)) for p in contract['databases']}


def serve(root, model_path):
    model_files(model_path)
    # Reuse the proven launcher and session-aware descendant cleanup, privately.
    import dfm12.diagnostic_server as diagnostic
    from scripts.serve_dfm13_tp8_headroom import remember, cleanup
    def owned_remember(record):
        record.setdefault('created_at', min(p['create_time'] for p in record['owned']))
        remember(record)
    def owned_cleanup(directory, record):
        owned_remember(record)
        return cleanup(directory, record)
    diagnostic.remember, diagnostic.cleanup = owned_remember, owned_cleanup
    module = runpy.run_path('scripts/serve_dfm13_shared.py')
    namespace = module['main'].__globals__
    original = namespace['command_env']
    def command_env(memory, owner):
        command, env = original(memory, owner)
        command[command.index('--model') + 1] = str(model_path.resolve())
        # Launcher inserts the old alias later. Remove it before Popen below.
        return command, env
    namespace['command_env'] = command_env
    namespace['MODEL'] = MODEL
    original_write = namespace['write_json']
    def truthful_write(path, value):
        if Path(path).name == 'endpoints.json':
            value = dict(value, source_model=MODEL, max_num_seqs=8)
        return original_write(path, value)
    namespace['write_json'] = truthful_write
    original_popen = subprocess.Popen
    def popen(command, **kwargs):
        command[:] = [v for v in command if v != 'google/gemma-4-26B-A4B-it']
        command[command.index('--max-num-seqs') + 1] = '8'
        return original_popen(command, **kwargs)
    # Only this dedicated supervisor process is patched; no imported live state.
    namespace['subprocess'] = type('ProcessAPI', (), {'Popen': staticmethod(popen),
        'DEVNULL': subprocess.DEVNULL, 'STDOUT': subprocess.STDOUT})
    sys.argv = ['serve31', '--root', str(root), '--client-concurrency', '8']
    module['main']()


def transition(root, contract_path, model_path):
    with lock(root / 'transition.lock'):
        contract = load(contract_path)
        model_pins = model_files(model_path)
        if contract.get('model') != MODEL or contract.get('model_files') != model_pins:
            raise ValueError('Verified31B model provenance/config pins required')
        verify_comparison(COMPARISON)
        queues = readiness(contract)
        old = load(OLD / 'endpoints.json')['supervisor']
        if old != contract['supervisor'] or not alive(old):
            raise ValueError('Supervisor identity changed')
        # pidfd plus exact starttime/command avoids PID reuse. Never signal children
        # separately: the coupled supervisor performs its recorded cleanup.
        fd = pidfd_open(old['pid'])
        try:
            readiness(contract)
            if not alive(old):
                raise ValueError('Supervisor exited before handoff')
            write_json(root / 'release-request.json', {'supervisor': old, 'queues': queues,
                'contract_sha256': file_hash(contract_path), 'time': time.time()})
            pidfd_signal(fd, signal.SIGTERM)
        finally:
            os.close(fd)
        deadline = time.monotonic() + 180
        while alive(old) and time.monotonic() < deadline:
            time.sleep(2)
        if alive(old):
            raise RuntimeError('Old supervisor did not stop; no escalation or new servers')
        from .european_campaign import available
        if not available()[0]:
            raise RuntimeError('GPUs not free after cleanup; no new servers')
        with (root / 'server-supervisor.log').open('x') as log:
            p = subprocess.Popen([sys.executable, '-u', '-m', 'dfm12.wave4_gemma31_transition', 'serve',
                '--root', str(root / 'servers'), '--model-path', str(model_path)],
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        write_json(root / 'launch.json', {'supervisor': identity(p.pid), 'model': MODEL,
            'production_approved': False})
        endpoints = [f'http://127.0.0.1:{8800+i}/v1' for i in range(8)]
        deadline = time.monotonic() + 7200
        while True:
            if p.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('31B startup failed/timed out; inspect logs, no automatic fallback')
            try:
                for endpoint in endpoints:
                    with urllib.request.urlopen(endpoint + '/models', timeout=3) as response:
                        document = json.load(response)
                    validate_endpoint(document, model_path)
                break
            except Exception:
                time.sleep(10)
        command = [sys.executable, '-u', '-m', 'dfm12.european_stage', '--database',
            str(COMPARISON / 'jobs.sqlite'), '--stage', 'audit', '--output', str(root / 'client'),
            '--concurrency', '8', '--max-concurrency', '8']
        for endpoint in endpoints:
            command += ['--endpoint', endpoint]
        write_json(root / 'client-command.json', command)
        subprocess.run(command, check=True)
        write_json(root / 'comparison-terminal.json', {'counts': terminal_database(COMPARISON / 'jobs.sqlite'),
            'production_approved': False, 'semantic_review_required': True})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['inspect', 'check', 'transition', 'serve'])
    p.add_argument('--root', type=Path, default=Path('logs/dfm13/wave4-gemma31-comparison'))
    p.add_argument('--contract', type=Path)
    p.add_argument('--model-path', type=Path)
    a = p.parse_args()
    if a.action == 'inspect':
        print(json.dumps({'comparison_jobs': verify_comparison(COMPARISON),
            'supervisor': load(OLD / 'endpoints.json')['supervisor'], 'process_actions': False}, indent=2))
    elif a.action == 'check':
        print(json.dumps(readiness(load(a.contract)), indent=2))
        contract = load(a.contract)
        if contract.get('model') != MODEL or contract.get('model_files') != model_files(a.model_path):
            raise ValueError('Verified31B model provenance/config pins required')
    elif a.action == 'serve':
        serve(a.root, a.model_path)
    else:
        transition(a.root, a.contract, a.model_path)


if __name__ == '__main__':
    main()
