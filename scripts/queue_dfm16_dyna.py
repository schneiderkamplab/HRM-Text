"""Wait for free GPUs, audit new Dyna data, tokenize accepted rows, rebuild DFM16."""
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
import ctypes
import errno
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from dfm12.io import atomic, digest, file_hash, load, lock, rows, write_json
from dfm12.european_campaign import available
from dfm14.prepare_gpu import validate_candidate
from scripts.prepare_dfm16_dyna import publish_audit_manifest

REPO = Path(__file__).resolve().parents[1]
DATA = REPO/'data/dfm16/dyna-v1'
MODEL = Path('/work/dfm/.home/.cache/huggingface/hub/models--google--gemma-4-26B-A4B-it/snapshots/4d7ae4984b7db7de8f8457170b3f1a419ee76d52')
ENVIRONMENT = Path('/home/ucloud/miniforge3/envs/audit')


def prepare(work):
    root = work/'inputs'
    signature = dict(grounding=file_hash(DATA/'grounding/manifest.json'),
                     instructions=file_hash(DATA/'dynaword-no-bt/conversion.json'))
    if (root/'inputs.json').exists():
        if load(root/'inputs.json') != signature:
            raise ValueError('Changed queued audit inputs')
        for chunk in load(root/'manifest.json')['chunks']:
            if file_hash(root/chunk['input']) != chunk['sha256']:
                raise ValueError('Changed queued audit chunk')
        return root
    pending, chunks, seen = [], [], set()

    def append(record):
        validate_candidate(record)
        key = digest(record['messages'])
        if key in seen:
            return
        seen.add(key)
        record['audit_id'] = digest(['dfm16-dyna-v1', key])
        pending.append(record)
        if len(pending) >= 256:
            flush()

    def flush():
        if not pending:
            return
        filename = f'chunks/{len(chunks):05}.jsonl'
        with atomic(root/filename) as out:
            for record in pending:
                out.write(json.dumps(record, ensure_ascii=False)+'\n')
        chunks.append(dict(job_id=f'dyna-{len(chunks):05}', input=filename,
            rows=len(pending), task='dyna-instructions-and-transforms', sha256=file_hash(root/filename)))
        pending.clear()

    for chunk in load(DATA/'grounding/manifest.json')['chunks']:
        path = DATA/'grounding'/chunk['input']
        if file_hash(path) != chunk['sha256']:
            raise ValueError('Grounding checksum mismatch')
        for record in rows(path):
            append(record)
    from dfm12.prepare import Renderer
    meta = load(REPO/'data/dfm15/native-reasoning-v2/sampled_dfm15/metadata.json')['tokenizer_info']
    renderer = Renderer(meta, max_length=4097)
    conversion = load(DATA/'dynaword-no-bt/conversion.json')
    for name, checksum in conversion['output_hashes'].items():
        path = DATA/'dynaword-no-bt'/name
        if file_hash(path) != checksum:
            raise ValueError('Instruction checksum mismatch')
        for record in rows(path):
            record.update(task='instruction', admission_authorized=False, training_ready=False,
                          rendered_tokens=renderer.count(record['messages']))
            append(record)
    flush()
    publish_audit_manifest(root, chunks)
    write_json(root/'inputs.json', signature)
    return root


def finalize(work, workers):
    from scripts.prepare_dfm16_decisions import tokenize_source
    from audit_pipeline.dfm14 import Audit
    root, audited = work/'inputs', work/'audit'
    meta = load(REPO/'data/dfm15/native-reasoning-v2/sampled_dfm15/metadata.json')['tokenizer_info']
    by_source, counts = defaultdict(list), Counter()
    manifest = load(root/'manifest.json')
    for chunk in manifest['chunks']:
        folder = audited/chunk['job_id']
        receipt = load(folder/'receipt.json')
        if (receipt['input_sha256'] != chunk['sha256'] or receipt['model'] != Audit.model
                or receipt['results_sha256'] != file_hash(folder/'results.jsonl')):
            raise ValueError('Audit receipt mismatch')
        results = list(rows(folder/'results.jsonl'))
        reviews = {record['audit_id']: record for record in results}
        inputs = list(rows(root/chunk['input']))
        if len(reviews) != len(results) or set(reviews) != {r['audit_id'] for r in inputs}:
            raise ValueError('Incomplete or duplicate review journal')
        for record in inputs:
            review = reviews[record['audit_id']]
            if review['status'] != 'reviewed':
                raise ValueError('Unresolved audit failures; refusing partial sampling')
            verdict = review['review']['decision']
            if verdict not in ('accept', 'reject'):
                raise ValueError('Unexpected audit verdict')
            counts[verdict] += 1
            if verdict == 'accept':
                provenance = record['provenance']
                repo = provenance.get('repo_id') or provenance['repo']
                by_source[repo].append(record)
    if not by_source:
        raise ValueError('No accepted new data')
    prepared = []
    for repo, records in sorted(by_source.items()):
        out = work/'accepted'/repo.replace('/', '__')
        identity = digest(records)
        if (out/'conversion.json').exists():
            if load(out/'conversion.json')['accepted_sha256'] != identity:
                raise ValueError('Accepted inputs changed')
        else:
            with ExitStack() as stack:
                handles = [stack.enter_context(atomic(out/'input/direct'/f'{i:03}.jsonl'))
                           for i in range(min(64, len(records)))]
                for i, record in enumerate(records):
                    value = dict(messages=record['messages'], provenance=record['provenance'],
                                 audit_id=record['audit_id'])
                    handles[i % len(handles)].write(json.dumps(value, ensure_ascii=False)+'\n')
            write_json(out/'conversion.json', dict(repo_id=repo, accepted_sha256=identity,
                                                  counts=dict(direct=len(records))))
        tokenize_source(out, meta, workers)
        write_json(out/'prepared.json', load(out/'prepared.json') | dict(repo_id=repo, audit_accepted=True))
        prepared.append(out/'prepared.json')
    write_json(work/'accepted-summary.json', dict(counts=dict(counts),
        sources=[load(path) for path in prepared], laya='excluded_pending_gated_access'))
    return prepared


def exchange(a, b):
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(a), -100, os.fsencode(b), 2):
        raise OSError(ctypes.get_errno(), 'Atomic directory exchange failed; verified replacement retained')


def publish(work, replacement):
    target = REPO/'data/sampled_dfm16'
    backup = target.with_name(target.name+'_before_dyna_20261027')
    with lock(target.with_suffix('.lock')):
        intent = work/'publication-intent.json'
        # Recover a power loss between the two renames on filesystems without
        # RENAME_EXCHANGE. Never discard the preserved old dataset.
        if intent.exists() and not target.exists():
            if not backup.exists():
                raise RuntimeError('Missing publication backup; manual inspection required')
            if replacement.exists() and load(replacement/'metadata.json').get('dfm16_dyna_campaign') == str(work):
                verified = load(replacement/'ready.json')
                if verified != load(replacement/'validated.json') or verified['metadata_sha256'] != file_hash(replacement/'metadata.json'):
                    backup.rename(target)
                    raise ValueError('Restored previous dataset after replacement hash mismatch')
                replacement.rename(target)
            else:
                backup.rename(target)
                raise RuntimeError('Restored previous dataset; replacement missing')
        # A durable run marker makes recovery after the exchange unambiguous.
        if load(target/'metadata.json').get('dfm16_dyna_campaign') == str(work):
            write_json(work/'published.json', dict(target=str(target),
                previous=str(backup if backup.exists() else replacement)))
            return
        receipt = load(replacement/'ready.json')
        if receipt != load(replacement/'validated.json'):
            raise ValueError('Replacement validation mismatch')
        if receipt['metadata_sha256'] != file_hash(replacement/'metadata.json'):
            raise ValueError('Replacement metadata hash mismatch')
        meta = load(replacement/'metadata.json')
        meta['tokenizer_info']['chat_template_path'] = str(target/'chat_template.jinja')
        meta['dfm16_dyna_campaign'] = str(work)
        write_json(replacement/'metadata.json', meta)
        receipt['metadata_sha256'] = file_hash(replacement/'metadata.json')
        write_json(replacement/'validated.json', receipt)
        write_json(replacement/'ready.json', receipt)
        previous = replacement
        try:
            exchange(target, replacement)
        except OSError as exc:
            if exc.errno not in (errno.EINVAL, errno.ENOSYS, errno.EOPNOTSUPP):
                raise
            if backup.exists():
                raise FileExistsError('Existing publication backup; refusing to overwrite')
            write_json(intent, dict(target=str(target), replacement=str(replacement), backup=str(backup)))
            target.rename(backup)
            try:
                replacement.rename(target)
            except BaseException:
                backup.rename(target)
                raise
            previous = backup
        write_json(work/'published.json', dict(target=str(target), previous=str(previous)))


def run(work, workers, sample=False):
    os.chdir(REPO)
    work = work.resolve()
    os.environ['PATH'] = '/home/ucloud/miniforge3/envs/hrm/bin:' + os.environ.get('PATH', '')
    def state(phase, **details):
        value = dict(phase=phase, time=time.time(), pid=os.getpid(), **details)
        write_json(work/'status.json', value)
        print(json.dumps(value), flush=True)
    def stop(*_):
        raise InterruptedError('DFM16 queue stopped')
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with lock(work/'.controller.lock'):
        try:
            if (work/'publication-intent.json').exists() and not (work/'published.json').exists():
                publish(work, REPO/'data/sampled_dfm16_dyna_verified')
            if (work/'published.json').exists():
                subprocess.run([sys.executable, '-m', 'scripts.report_dfm16_mix'], check=True)
                state('complete')
                return
            state('preparing_audit_inputs')
            inputs = prepare(work)
            if not (work/'audit-complete.json').exists():
                free_checks = 0
                while free_checks < 2:
                    free, devices = available()
                    free_checks = free_checks+1 if free else 0
                    state('waiting_for_free_gpus', consecutive_free_checks=free_checks, devices=devices)
                    if free_checks < 2:
                        time.sleep(30)
                servers = work/f'servers-{time.time_ns()}'
                command = [sys.executable, '-u', '-m', 'scripts.serve_dfm13_26b_isolated',
                    '--root', str(servers), '--model-path', str(MODEL), '--environment', str(ENVIRONMENT)]
                with (work/'servers.log').open('a') as log:
                    server = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                              stdin=subprocess.DEVNULL, start_new_session=True)
                audit = None
                try:
                    state('starting_servers', server_root=str(servers), supervisor=server.pid)
                    deadline = time.monotonic()+7500
                    while True:
                        if server.poll() is not None:
                            raise RuntimeError('Owned server startup failed')
                        if (servers/'status.json').exists() and load(servers/'status.json')['phase'] == 'ready':
                            break
                        if time.monotonic() > deadline:
                            raise TimeoutError('Server startup deadline')
                        time.sleep(10)
                    state('auditing', concurrency_per_server=256)
                    with (work/'audit.log').open('a') as log:
                        audit = subprocess.Popen([sys.executable, '-u', '-m', 'audit_pipeline', 'audit',
                            '--root', str(inputs), '--output', str(work/'audit'), '--concurrency', '256'],
                            stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
                    while audit.poll() is None:
                        if server.poll() is not None:
                            raise RuntimeError('Owned server failed during audit')
                        time.sleep(5)
                    if audit.returncode or load(work/'audit/pipeline/state.json')['phase'] != 'complete':
                        raise RuntimeError('Audit failed or interrupted')
                    write_json(work/'audit-complete.json', dict(manifest_sha256=file_hash(inputs/'manifest.json')))
                finally:
                    try:
                        if audit is not None and audit.poll() is None:
                            audit.terminate()
                            audit.wait(timeout=180)
                    finally:
                        servers.mkdir(exist_ok=True)
                        (servers/'stop.request').touch()
                        server.wait(timeout=300)
                if server.returncode:
                    raise RuntimeError('Server lifecycle failed; inspect owned cleanup before proceeding')
                for gpu in range(8):
                    if load(servers/f'gpu{gpu}/cleanup.json')['survivors']:
                        raise RuntimeError('Owned GPU server survived cleanup')
            if load(work/'audit-complete.json')['manifest_sha256'] != file_hash(inputs/'manifest.json'):
                raise ValueError('Audit completion refers to different inputs')
            state('tokenizing_accepted_rows', workers=workers)
            prepared = finalize(work, workers)
            if not sample:
                state('complete_without_sampling', prepared=[str(p) for p in prepared])
                return
            replacement = REPO/'data/sampled_dfm16_dyna_verified'
            if load(REPO/'data/sampled_dfm16/metadata.json').get('dfm16_dyna_campaign') != str(work):
                intent = dict(replacement=str(replacement),
                    base_sha256=file_hash(REPO/'incoming/mimir-xl-20261015/data/sampled_dfm15/validated.json'),
                    prepared={str(path): file_hash(path) for path in prepared})
                intent_path = work/'sampling-intent.json'
                if intent_path.exists():
                    if load(intent_path) != intent:
                        raise ValueError('Sampling inputs changed')
                else:
                    if replacement.exists() or replacement.with_name(replacement.name+'.building').exists():
                        raise FileExistsError('Unowned replacement/build directory')
                    write_json(intent_path, intent)
                if not (replacement/'ready.json').exists():
                    state('sampling_full_dfm16', replacement=str(replacement))
                    command = [sys.executable, '-u', '-m', 'scripts.sample_dfm16', '--output', str(replacement)]
                    for path in prepared:
                        command += ['--additional-source', str(path)]
                    subprocess.run(command, check=True)
            state('publishing_verified_replacement')
            publish(work, replacement)
            subprocess.run([sys.executable, '-m', 'scripts.report_dfm16_mix'], check=True)
            state('complete', target=str(REPO/'data/sampled_dfm16'))
        except BaseException as exc:
            state('failed', error=repr(exc))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=REPO/'logs/dfm16/dyna-audit-sample-20261027')
    parser.add_argument('--workers', type=int, default=64)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--sample', action='store_true', help='Explicitly authorize rebuilding sampled epochs')
    args = parser.parse_args()
    if not 1 <= args.workers <= 64:
        parser.error('workers must be 1..64')
    if args.prepare_only:
        os.chdir(REPO)
        with lock(args.work/'.controller.lock'):
            print(prepare(args.work.resolve()))
    else:
        run(args.work, args.workers, args.sample)
