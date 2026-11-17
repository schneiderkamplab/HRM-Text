"""Run SimpleStories after Dyna review, then ready source audits; never sample."""
import argparse
from collections import Counter
from contextlib import ExitStack
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from dfm12.io import atomic, digest, file_hash, load, lock, rows, write_json
from dfm12.european_campaign import available
from scripts.prepare_dfm16_stories import prepare_wave
from scripts.prepare_dfm16_dyna import publish_audit_manifest
from scripts.queue_dfm16_dyna import MODEL, ENVIRONMENT

ROOT = Path('data/dfm16/expansion-v1')
WORK = Path('logs/dfm16/expansion-20261027')
DYNA = Path('logs/dfm16/dyna-audit-sample-20261027')


def accepted_counts(root):
    counts = Counter()
    for path in sorted((root/'stories').glob('wave-*/audit/*/results.jsonl')):
        for result in rows(path):
            if result.get('status') == 'reviewed' and result.get('review', {}).get('decision') == 'accept':
                candidate = result['candidate']
                counts[candidate['language'], candidate['task']] += 1
    return counts


def materialize_stories(root):
    if (root/'stories/admission-hold.json').exists():
        raise RuntimeError('Old SimpleStories acceptance revoked; use quality-v2 re-audit')
    config = load('config/dfm16_expansion.json')['simple_stories']
    out = root/'accepted/simplestories'
    if (out/'conversion.json').exists():
        return out
    counts, seen, target_count = Counter(), set(), 0
    with ExitStack() as stack:
        handles = [stack.enter_context(atomic(out/'input/direct'/f'{i:03}.jsonl')) for i in range(64)]
        for path in sorted((root/'stories').glob('wave-*/audit/*/results.jsonl')):
            for result in rows(path):
                if result.get('status') != 'reviewed' or result.get('review', {}).get('decision') != 'accept':
                    continue
                candidate = result['candidate']
                key = candidate['language'], candidate['task']
                target = config['accepted_targets'][key[0]]*config['task_percentages'][key[1]]//100
                if counts[key] >= target:
                    continue
                if result['audit_id'] in seen:
                    raise ValueError('Duplicate accepted ID')
                seen.add(result['audit_id'])
                handles[len(seen) % 64].write(json.dumps(candidate, ensure_ascii=False)+'\n')
                counts[key] += 1
                target_count += sum(m['role'] == 'assistant' for m in candidate['messages'])
        for language, total in config['accepted_targets'].items():
            for task, pct in config['task_percentages'].items():
                if counts[language, task] != total*pct//100:
                    raise ValueError('Accepted target not reached')
    write_json(out/'conversion.json', dict(repo_id='local/dfm16-simplestories-pilot',
        counts=dict(direct=target_count), conversations=sum(counts.values()),
        groups={f'{a}/{b}': n for (a,b),n in counts.items()},
        repeat=1, sampling=False))
    return out


def tokenize(out, workers):
    if (out/'admission.json').exists() and not load(out/'admission.json').get('training_ready'):
        raise RuntimeError('Source is quarantined: '+str(out))
    from scripts.prepare_dfm16_decisions import tokenize_source
    meta = load('data/dfm15/native-reasoning-v2/sampled_dfm15/metadata.json')['tokenizer_info']
    tokenize_source(out, meta, workers)


def prepare_structured_answers(root):
    repo = 'nvidia/Nemotron-RL-instruction_following-structured_outputs'
    source = root/'converted'/repo.replace('/', '__')
    out = root/'generation'/repo.replace('/', '__')
    if (out/'readiness.json').exists():
        return out
    if not (source/'conversion.json').exists():
        return None
    import jsonschema
    from scripts.prepare_dfm16_expansion import normalize_messages
    chunks, pending = [], []
    invalid_schemas = []
    def flush():
        if not pending:
            return
        name = f'chunks/{len(chunks):05}.jsonl'
        with atomic(out/name) as stream:
            for record in pending:
                stream.write(json.dumps(record, ensure_ascii=False)+'\n')
        chunks.append(dict(job_id=f'answers-{len(chunks):05}', input=name,
            rows=len(pending), task='structured_answer', sha256=file_hash(out/name)))
        pending.clear()
    for record in rows(source/'generation-pending.jsonl'):
        raw = record['source']
        from scripts.dfm16_schema import checked_schema
        try:
            schema = checked_schema(json.loads(raw['schema_str']))
        except (ValueError, TypeError, jsonschema.SchemaError) as exc:
            invalid_schemas.append(dict(provenance=record['provenance'],
                error=str(exc), schema=raw['schema_str']))
            continue
        messages = normalize_messages(raw['responses_create_params']['input'])
        # Consolidate adjacent user turns without losing their order or text.
        combined = []
        for message in messages:
            if combined and message['role'] == combined[-1]['role'] == 'user':
                combined[-1]['content'] += '\n\n'+message['content']
            else:
                combined.append(message)
        key = digest(record['provenance'])
        pending.append(dict(id=key, audit_id=key, language='en', task='structured_answer',
            messages=combined, schema=schema, provenance=record['provenance']))
        if len(pending) == 128:
            flush()
    flush()
    write_json(out/'invalid-schemas.json', invalid_schemas)
    write_json(out/'tokenizer.json', load('data/dfm15/native-reasoning-v2/sampled_dfm15/metadata.json')['tokenizer_info'])
    publish_audit_manifest(out, chunks)
    return out


def finalize_audited(inputs, out):
    if (out/'conversion.json').exists():
        return out
    counts, decisions = Counter(), Counter()
    handles = {}
    with ExitStack() as stack:
        for chunk in load(inputs/'manifest.json')['chunks']:
            folder = inputs/'audit'/chunk['job_id']
            receipt = load(folder/'receipt.json')
            if receipt['input_sha256'] != chunk['sha256'] or receipt['results_sha256'] != file_hash(folder/'results.jsonl'):
                raise ValueError('Changed audited data')
            source = {r['audit_id']: r for r in rows(inputs/chunk['input'])}
            results = list(rows(folder/'results.jsonl'))
            if len(results) != len(source) or {r['audit_id'] for r in results} != set(source):
                raise ValueError('Incomplete audit result IDs')
            for result in results:
                verdict = result.get('review', {}).get('decision') if result['status'] == 'reviewed' else 'unresolved'
                decisions[verdict] += 1
                if verdict != 'accept':
                    continue
                candidate = result.get('candidate') or source[result['audit_id']]
                mode = 'thinking' if any(m.get('reasoning_content') for m in candidate['messages']) else 'direct'
                part = counts[mode] % 64
                if (mode, part) not in handles:
                    handles[mode, part] = stack.enter_context(atomic(out/'input'/mode/f'{part:03}.jsonl'))
                handles[mode, part].write(json.dumps(candidate, ensure_ascii=False)+'\n')
                counts[mode] += (1 if 'target_message_index' in candidate else
                                 sum(m['role'] == 'assistant' for m in candidate['messages']))
    write_json(out/'conversion.json', dict(counts=dict(counts), decisions=dict(decisions),
        repeat=1, audit_manifest_sha256=file_hash(inputs/'manifest.json'), sampling=False))
    return out


def run(root, work):
    root, work = root.resolve(), work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    server, client = None, None
    cpus = []
    def state(phase, **extra):
        value = dict(phase=phase, time=time.time(), pid=os.getpid(), sampling=False, **extra)
        write_json(work/'status.json', value)
        print(value, flush=True)
    def stop(*_):
        raise InterruptedError('Expansion queue stopped')
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with lock(work/'.gpu-controller.lock'):
        try:
            while not (DYNA/'audit-complete.json').exists() or not (root/'stories/wave-00/readiness.json').exists():
                state('waiting_for_dyna_audit_and_story_preparation')
                time.sleep(30)
            free_checks = 0
            while free_checks < 2:
                free, devices = available()
                free_checks = free_checks+1 if free else 0
                state('waiting_for_free_gpus', consecutive_free_checks=free_checks, devices=devices)
                if free_checks < 2:
                    time.sleep(30)
            server_root = work/f'servers-{time.time_ns()}'
            with (work/'servers.log').open('a') as stream:
                server = subprocess.Popen([sys.executable, '-u', '-m', 'scripts.serve_dfm13_26b_isolated',
                    '--root', str(server_root), '--model-path', str(MODEL), '--environment', str(ENVIRONMENT)],
                    stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            state('starting_servers', server_root=str(server_root), supervisor=server.pid)
            deadline = time.monotonic()+7500
            while not (server_root/'status.json').exists() or load(server_root/'status.json')['phase'] != 'ready':
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Owned servers failed to become ready')
                time.sleep(10)

            def invoke(kind, inputs, output):
                nonlocal client
                if server.poll() is not None:
                    raise RuntimeError('Owned server exited')
                with (work/f'{kind}.log').open('a') as stream:
                    client = subprocess.Popen([sys.executable, '-u', '-m', 'audit_pipeline', kind,
                        '--root', str(inputs), '--output', str(output), '--concurrency', '256'],
                        stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
                while client.poll() is None:
                    if server.poll() is not None:
                        raise RuntimeError('Server failed during requests')
                    time.sleep(5)
                if client.returncode or load(output/'pipeline/state.json')['phase'] != 'complete':
                    raise RuntimeError(f'{kind} failed: {output}')

            quality_v2 = (root/'stories/admission-hold.json').exists()
            config = load('config/dfm16_expansion.json')['simple_stories']
            for wave in range(0 if quality_v2 else 10):
                counts = accepted_counts(root)
                missing = {f'{lang}/{task}': total*pct//100-counts[lang, task]
                    for lang, total in config['accepted_targets'].items()
                    for task, pct in config['task_percentages'].items()
                    if counts[lang, task] < total*pct//100}
                if not missing:
                    break
                inputs = prepare_wave(root, wave)
                state('stories_generation_review', wave=wave, missing=missing)
                invoke('stories', inputs, inputs/'audit')
            # Materialization enforces every accepted quota, including the final wave.
            if not quality_v2:
                out = materialize_stories(root)
                with (work/'tokenize.log').open('a') as stream:
                    cpus.append(subprocess.Popen([sys.executable, '-u', '-m', __name__.replace('__main__', 'scripts.queue_dfm16_expansion'),
                        '--tokenize', str(out)], stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT))

            # Only ready, pinned conversions enter the audit; prompt-only inputs stay held.
            finalizations = []
            if quality_v2:
                quality_root = root/'stories/quality-v2'
                state('stories_v2_calibration')
                invoke('stories', quality_root/'pilot', quality_root/'pilot/audit')
                from scripts.report_dfm16_stories_v2 import report
                report(quality_root/'pilot')
                state('stories_v1_strict_reaudit', rows=300000)
                invoke('audit', quality_root/'reaudit', quality_root/'reaudit/audit')
                finalizations.append((quality_root/'reaudit', root/'accepted/simplestories-reaudited-v2'))
            deferred_sources = []
            for source in load('config/dfm16_expansion.json')['sources']:
                inputs = root/'converted'/source['repo_id'].replace('/', '__')
                if not (inputs/'readiness.json').exists():
                    if source['repo_id'] == 'openbmb/UltraData-SFT-2605':
                        deferred_sources.append(source)
                    continue
                if not load(inputs/'manifest.json')['chunks']:
                    continue
                state('source_audit', repo_id=source['repo_id'])
                invoke('audit', inputs, inputs/'audit')
                finalizations.append((inputs, root/'accepted'/source['repo_id'].replace('/', '__')))
            inputs = prepare_structured_answers(root)
            if inputs is not None:
                state('structured_answer_generation_review')
                invoke('answers', inputs, inputs/'audit')
                finalizations.append((inputs, root/'accepted'/inputs.name))
            from scripts.prepare_dfm16_verified_answers import SOURCES
            generated_sources = set()
            for repo in SOURCES:
                inputs = root/'generation'/repo.replace('/', '__')
                if not (inputs/'readiness.json').exists():
                    raise RuntimeError('Missing verified-generation preparation: '+repo)
                if load(inputs/'manifest.json')['chunks']:
                    state('verified_answer_generation_review', repo_id=repo)
                    invoke('answers', inputs, inputs/'audit')
                    finalizations.append((inputs, root/'accepted'/(inputs.name+'__generated')))
                generated_sources.add(repo)
            for source in deferred_sources:
                inputs = root/'converted'/source['repo_id'].replace('/', '__')
                while not (inputs/'readiness.json').exists():
                    if server.poll() is not None:
                        raise RuntimeError('Owned server exited while awaiting conversion')
                    state('waiting_for_source_conversion', repo_id=source['repo_id'])
                    time.sleep(30)
                state('source_audit', repo_id=source['repo_id'])
                invoke('audit', inputs, inputs/'audit')
                finalizations.append((inputs, root/'accepted'/inputs.name))
            pending = []
            for source in load('config/dfm16_expansion.json')['sources']:
                path = root/'converted'/source['repo_id'].replace('/', '__')/'conversion.json'
                summary = load(path) if path.exists() else {}
                generated_here = source['repo_id'].endswith('instruction_following-structured_outputs') or source['repo_id'] in generated_sources
                if not summary or (summary.get('counts', {}).get('pending_generation') and not generated_here):
                    pending.append(dict(source=source, preparation=summary,
                        phase='needs_verified_generation_adapter' if summary else 'preparation_pending'))
            write_json(root/'followup-queue.json', dict(after='simplestories-300k', sources=pending,
                note='Not admitted until a source-specific verifier/adapter is ready', sampling=False))
            state('gpu_work_complete', note='Inspect source holds and pending generation; no sampling')
        except BaseException as exc:
            state('failed', error=repr(exc))
            raise
        finally:
            if client is not None and client.poll() is None:
                client.terminate()
                client.wait(timeout=180)
            if server is not None and server.poll() is None:
                (server_root/'stop.request').touch()
                server.wait(timeout=300)
                if server.returncode:
                    raise RuntimeError('Owned server cleanup failed')
                for gpu in range(8):
                    if load(server_root/f'gpu{gpu}/cleanup.json')['survivors']:
                        raise RuntimeError('Owned GPU process survived cleanup')
            for process in cpus:
                if process.wait() != 0:
                    state('cpu_tokenization_failed')
                    raise RuntimeError('Accepted story tokenization failed')
        for inputs, out in finalizations:
            state('finalizing_accepted_source', source=str(inputs))
            tokenize(finalize_audited(inputs, out), 64)
        write_json(root/'prepared-sources.json', dict(sampling=False,
            sources=[dict(path=str(p), receipt=load(p)) for p in sorted((root/'accepted').glob('*/prepared.json'))]))
        state('complete_ready_sources', remaining_queue=str(root/'followup-queue.json'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--work', type=Path, default=WORK)
    parser.add_argument('--tokenize', type=Path)
    args = parser.parse_args()
    if args.tokenize:
        tokenize(args.tokenize, 64)
    else:
        run(args.root, args.work)
