#!/usr/bin/env python3
"""Fail-closed CPU queue and bounded EMA stochastic conversation generation."""
import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import signal
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import atomic, digest, file_hash, load, write_json
from scripts import evaluate_dfm12_identity_continuation_v4 as evaluation

ORIGINAL_WORKER = evaluation.worker
ORIGINAL_SAVE = evaluation.save

CO_RESIDENT_POLICY = dict(resource_mode='manual_co_resident',
                         allocator_limit_gib_per_worker=80, non_torch_reserve_mib=4096,
                         required_free_mib=92*1024)


def real_memory(gpu, pid=None):
    def query(fields):
        return subprocess.check_output(['nvidia-smi', '-i', str(gpu), *fields,
                                        '--format=csv,noheader,nounits'], text=True, timeout=10)
    total, free = map(int, query(['--query-gpu=memory.total,memory.free']).strip().split(','))
    rows = query(['--query-compute-apps=pid,used_gpu_memory']).strip().splitlines()
    usage = {int(row.split(',')[0]): int(row.split(',')[1]) for row in rows if row.strip()}
    return dict(gpu=gpu, total_mib=total, free_mib=free, compute_memory_mib=usage,
                own_used_mib=usage.get(pid, 0))


def check_co_resident(report, snapshot, loading=False):
    required = evaluation.required_free_mib(report, snapshot['total_mib'])
    ceiling = (report['allocator_limit_gib_per_worker'] * 1024 + report['non_torch_reserve_mib'])
    if snapshot['own_used_mib'] > ceiling:
        raise RuntimeError('Owned GPU footprint exceeded Torch plus non-Torch budget')
    if snapshot['free_mib'] < (required if loading else 8192):
        raise RuntimeError('Insufficient real co-resident GPU headroom')
    return ceiling


def read_pool(corpus):
    return [json.loads(line) for line in (Path(corpus) / 'prompt-pool.jsonl').read_text().splitlines()]


def expand_cases(cases, samples=4):
    result = []
    for case in cases:
        for sample in range(samples):
            row = copy.deepcopy(case)
            row.update(source_case_id=case['id'], sampling_index=sample,
                       sampling_seed=int(digest([case['id'], sample, 'ema-2887261-v1'])[:8], 16))
            row['id'] = digest([case['id'], row['sampling_seed']])
            if row['suite'] != 'development_identity_preferences' or row['split'] not in ('train','validation'):
                raise ValueError('Sampling must preserve development family split')
            result.append(row)
    return result


def nucleus_sample(logits, temperature, top_p):
    import torch
    if temperature == 0:
        return logits.argmax(-1)
    if not temperature > 0 or not 0 < top_p <= 1:
        raise ValueError('Invalid sampling settings')
    scores, indices = torch.sort(logits.float() / temperature, descending=True, dim=-1)
    probabilities = torch.softmax(scores, dim=-1)
    exclude = probabilities.cumsum(-1) - probabilities >= top_p
    probabilities = probabilities.masked_fill(exclude, 0)
    if not torch.isfinite(probabilities).all() or (probabilities.sum(-1) <= 0).any():
        raise ValueError('Invalid sampling probabilities')
    draw = torch.multinomial(probabilities, 1)
    return indices.gather(-1, draw).squeeze(-1)


def worker(gpu, initial, tasks, cancelled, load_slots, report, run, manifest, phase_dir, deadline):
    # Hooks are process-local and restored; no frozen source file is modified.
    if file_hash(__file__) != report['sampling_script_sha256']:
        raise ValueError('Sampling wrapper changed')
    evaluation.worker_environment(gpu)
    import torch
    import simple_inference_engine as engine
    old_sample = engine._sample
    old_generate = evaluation.historical.generate_turn
    old_conversation = evaluation.historical.run_conversation
    def sample(logits, temp):
        return nucleus_sample(logits, temp, report['sampling']['top_p'])
    def generate(checkpoint, messages, context, limit):
        rendered, ids = evaluation.historical.render_prompt(checkpoint.tokenizer, messages, context, limit)
        adapter = evaluation.historical.TokenizedCheckpoint(checkpoint, ids)
        start = time.monotonic()
        outputs = list(engine.inference_generate(adapter, iter([(0, ('raw',''))]), context, limit, 1,
                                                 report['sampling']['temperature']))
        if len(outputs) != 1 or outputs[0][0] != 0 or adapter.generated_ids is None:
            raise ValueError('Incomplete sampled output')
        tokens = adapter.generated_ids
        eos = bool(tokens and tokens[-1] == adapter.eos_id)
        if not eos and len(tokens) != limit:
            raise ValueError('Unexpected sampling termination')
        return dict(response=outputs[0][1], rendered_prompt=rendered, prompt_token_ids=ids,
                    generated_token_ids=tokens, generated_token_count=len(tokens),
                    finish_reason='eos' if eos else 'length', truncated=not eos,
                    seconds=time.monotonic()-start)
    def conversation(case, *args, **kwargs):
        torch.manual_seed(case['sampling_seed'])
        torch.cuda.manual_seed_all(case['sampling_seed'])
        return old_conversation(case, *args, **kwargs)
    engine._sample = sample
    evaluation.historical.generate_turn = generate
    evaluation.historical.run_conversation = conversation
    monitor_stop = threading.Event()
    monitor = None
    if report.get('resource_mode') == 'manual_co_resident':
        def monitor_memory():
            peak = 0
            while not monitor_stop.is_set():
                try:
                    snapshot = real_memory(gpu, os.getpid())
                    peak = max(peak, snapshot['own_used_mib'])
                    check_co_resident(report, snapshot)
                    write_json(Path(phase_dir)/f'memory-gpu-{gpu}.json',
                               dict(pid=os.getpid(), time=time.time(), peak_own_mib=peak, **snapshot))
                except BaseException as exc:
                    write_json(Path(phase_dir)/f'memory-gpu-{gpu}-failure.json',
                               dict(pid=os.getpid(), time=time.time(), error=str(exc)))
                    cancelled.set()
                    os.kill(os.getpid(), signal.SIGTERM)
                    return
                monitor_stop.wait(2)
        monitor = threading.Thread(target=monitor_memory, daemon=True)
        monitor.start()
    try:
        ORIGINAL_WORKER(gpu, initial, tasks, cancelled, load_slots, report, run, manifest, phase_dir, deadline)
    finally:
        monitor_stop.set()
        if monitor is not None:
            monitor.join(timeout=12)
        engine._sample = old_sample
        evaluation.historical.generate_turn = old_generate
        evaluation.historical.run_conversation = old_conversation


def save(output, report):
    ORIGINAL_SAVE(output, report)
    path = output / 'responses.md'
    text = path.read_text().replace('EMA, greedy, batch one per GPU.',
          'EMA, temperature 0.7, top_p 0.9, batch one per GPU. All candidates UNREVIEWED.')
    with atomic(path) as handle:
        handle.write(text)


def verify_spec(spec):
    if spec.get('resource_mode', 'exclusive_after_pilot') != 'exclusive_after_pilot':
        if (any(spec.get(k) != v for k, v in CO_RESIDENT_POLICY.items())
                or spec.get('user_override') != 'run_now_ema_2887261_all8_max_half_memory'):
            raise ValueError('Unrecognized manual resource authorization')
    if (spec['sampling'] != dict(temperature=0.7, top_p=0.9, samples_per_conversation=4)
            or spec['max_new_tokens'] != 512 or spec['max_context'] != 4096
            or not 0 < spec['max_seconds'] <= 3600):
        raise ValueError('Sampling contract changed')
    for path, sha in spec['code_pins'].items():
        if file_hash(path) != sha:
            raise ValueError('Queue code pin changed: ' + path)
    corpus = Path(spec['corpus'])
    if file_hash(corpus / 'manifest.json') != spec['corpus_manifest_sha256']:
        raise ValueError('Corpus manifest changed')
    manifest = load(corpus / 'manifest.json')
    for relative, sha in manifest['files'].items():
        if file_hash(corpus / relative) != sha:
            raise ValueError('Corpus file changed: ' + relative)
    if manifest['source_mode'] != 'EMA_ONLY' or manifest['tag'] != 'step_2887261':
        raise ValueError('Only latest EMA permitted')
    if file_hash(manifest['source']) != manifest['source_sha256']:
        raise ValueError('Greedy baseline source changed')
    if evaluation.checkpoint_pins(dict(checkpoint=manifest['checkpoint'], tag=manifest['tag'])) != manifest['checkpoint_pins']:
        raise ValueError('Checkpoint changed')
    evaluation.verify_helpers()
    return manifest


def released(spec, spec_sha):
    completion_path = Path(spec['pilot_root']) / 'completion.json'
    if completion_path.exists():
        current = load(completion_path)
        if current.get('status') not in ('complete','completed','complete_with_length_stops'):
            return False, 'Second pilot status=' + str(current.get('status')) + '; not completed'
        if current.get('gpu_released') is not True:
            return False, 'Second pilot has not confirmed GPU release'
    path = Path(spec['dependency_receipt'])
    if not path.exists():
        return False, 'Waiting for Poincare second-pilot completion AND GPU-release handoff'
    receipt = load(path)
    if (receipt.get('schema') != 'identity-ema-after-pilot-release-v1'
            or receipt.get('queue_spec_sha256') != spec_sha
            or receipt.get('producer') not in ('poincare', 'parent')
            or receipt.get('purpose') != 'second_pilot_completed_and_gpu_released'
            or receipt.get('authorized') is not True
            or receipt.get('time', 0) < spec['created']):
        raise ValueError('Invalid/stale/unbound pilot handoff')
    pilot = Path(receipt['pilot_root']).resolve()
    if pilot != Path(spec['pilot_root']).resolve():
        raise ValueError('Wrong pilot dependency')
    times = []
    for kind in ('completion','release'):
        pin = receipt[kind]
        target = Path(pin['path']).resolve()
        if not target.is_relative_to(pilot) or file_hash(target) != pin['sha256']:
            raise ValueError('Pilot receipt path/hash mismatch')
        if kind == 'completion' and target != completion_path.resolve():
            raise ValueError('Wrong pilot completion receipt')
        doc = load(target)
        if kind == 'completion' and doc.get('status') not in ('complete','completed','complete_with_length_stops'):
            raise ValueError('Pilot not operationally completed')
        if kind == 'release' and doc.get('only_owned_servers') is not True:
            raise ValueError('Missing owned-server release evidence')
        timestamp = doc.get('time', doc.get('completed', 0))
        if not isinstance(timestamp, (int,float)) or timestamp < spec['created']:
            raise ValueError('Old pilot evidence cannot release this queue')
        times.append(timestamp)
    if times[1] < times[0] or receipt['time'] < times[1]:
        raise ValueError('GPU release precedes completion')
    return True, 'Verified fresh pilot completion and release; GPU availability still required'


def prepare(corpus, root, pilot_root=None, manual_co_resident=False):
    if not manual_co_resident and pilot_root is None:
        raise ValueError('Exclusive queue requires explicit pilot root')
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    corpus = Path(corpus).resolve()
    paths = [Path(__file__).resolve(), Path(evaluation.__file__), Path(evaluation.v3.__file__),
             Path(evaluation.historical.__file__), ROOT/'simple_inference_engine.py',
             ROOT/'scripts/smoke_dfm12_identity.py']
    spec = dict(schema='identity-ema-stochastic-queue-v1', created=time.time(), corpus=str(corpus),
                corpus_manifest_sha256=file_hash(corpus/'manifest.json'),
                code_pins={str(p):file_hash(p) for p in paths},
                dependency_receipt=str(root/'poincare-second-pilot-release.json'),
                pilot_root=str(Path(pilot_root).resolve()) if pilot_root else None,
                output=str(root/'samples'), sampling=dict(temperature=0.7, top_p=0.9, samples_per_conversation=4),
                max_seconds=3600, max_wait_seconds=86400, max_new_tokens=512, max_context=4096,
                training_resume=False, full_evaluation=False,
                greedy_baseline='Reuse pinned latest EMA greedy source, no cross-history pairing',
                dependencies='Both second pilot completion and its GPU release; unrelated audit release alone is insufficient')
    if manual_co_resident:
        spec.update(CO_RESIDENT_POLICY,
                    user_override='run_now_ema_2887261_all8_max_half_memory',
                    dependencies='Explicit user supersedes pilot gate; real co-resident memory checks required',
                    superseded_queue=str(ROOT/'data/dfm12/identity-ema-stochastic-20260927-queue-v1'))
        snapshots = [real_memory(g) for g in range(8)]
        for snapshot in snapshots:
            check_co_resident(dict(spec, ema=True), snapshot, loading=True)
        spec['gpu_preflight'] = snapshots
    verify_spec(spec)
    cases = expand_cases(read_pool(corpus))
    write_json(root/'spec.json', spec)
    write_json(root/'preflight.json', dict(status='cpu_ready_waiting_for_dependency',
               spec_sha256=file_hash(root/'spec.json'), sampled_conversations=len(cases),
               maximum_turns=sum(len(c['users']) for c in cases), gpu_actions=False))
    print(root/'spec.json', file_hash(root/'spec.json'))


def run(spec_path, expected_sha):
    if file_hash(spec_path) != expected_sha:
        raise ValueError('Queue spec hash changed')
    spec = load(spec_path)
    manifest = verify_spec(spec)
    manual = spec.get('resource_mode') == 'manual_co_resident'
    if manual:
        for gpu in range(8):
            check_co_resident(dict(spec, ema=True), real_memory(gpu), loading=True)
    else:
        ready, reason = released(spec, expected_sha)
        if not ready:
            raise ValueError(reason)
        for gpu in range(8):
            snapshot = evaluation.gpu_status(gpu)
            if snapshot['compute_pids'] or snapshot['free_mib'] < 104*1024:
                raise ValueError('Insufficient exclusive EMA GPU memory')
    baseline = load(manifest['source'])
    report = copy.deepcopy(baseline)
    report.update(started=time.time(), status='running', cases=expand_cases(read_pool(spec['corpus'])),
                  sampling=spec['sampling'], sampling_script_sha256=file_hash(__file__),
                  script_sha256=file_hash(evaluation.__file__), max_seconds=spec['max_seconds'],
                  per_checkpoint_seconds=spec['max_seconds'], max_context=spec['max_context'],
                  max_new_tokens=spec['max_new_tokens'], quality_status='unreviewed_candidates_only',
                  heldout_only=False,
                  source_greedy_sha256=manifest['source_sha256'], queue_spec_sha256=expected_sha,
                  dataset_policy={'all_cases':'development_identity_preferences',
                                  'family_split':'Inherited before stochastic expansion',
                                  'preference_pair_rule':'Identical exact prompt/history only; never pair separate rollouts'},
                  runs=[dict(label='continued', checkpoint=manifest['checkpoint'], tag=manifest['tag'],
                             checkpoint_pins=manifest['checkpoint_pins'], status='planned', conversations=[])])
    report.pop('completed', None)
    if manual:
        report.update(CO_RESIDENT_POLICY, user_override=spec['user_override'])
    report['contract_sha256'] = digest(report)
    output = Path(spec['output'])
    output.mkdir(parents=True, exist_ok=False)
    evaluation.worker = worker
    evaluation.save = save
    try:
        save(output, report)
        result = evaluation.run_phase(report, report['runs'][0],
                 dict(tokenizer=manifest['runtime_asset_binding']['assets']['tokenizer'],
                      template=manifest['runtime_asset_binding']['assets']['template']), output, spec['max_seconds'])
        if not result:
            result = evaluation.finish_report(report)
        return result
    except BaseException as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        report['completed'] = time.time()
        save(output, report)
        write_json(output/'completion.json', dict(status=report['status'], responses_sha256=file_hash(output/'responses.json'),
                   quality_status='unreviewed', training_launched=False, full_evaluation=False))


def watch(spec_path, expected_sha):
    root = Path(spec_path).parent
    with (root/'watch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (root/'launch.json').exists():
            raise ValueError('Already launched; refusing duplicate')
        deadline = time.monotonic() + load(spec_path)['max_wait_seconds']
        while time.monotonic() < deadline:
            if file_hash(spec_path) != expected_sha:
                raise ValueError('Spec changed while queued')
            spec = load(spec_path)
            ready = False
            try:
                ready, reason = released(spec, expected_sha)
                if ready:
                    verify_spec(spec)
                    snapshots = [evaluation.gpu_status(g) for g in range(8)]
                    ready = all(not s['compute_pids'] and s['free_mib'] >= 104*1024 for s in snapshots)
                    reason = 'Waiting for all eight GPUs free' if not ready else 'ready'
            except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
                reason = f'Fail-closed dependency/resource check: {exc}'
            write_json(root/'watch-status.json', dict(pid=os.getpid(), time=time.time(), ready=ready, reason=reason))
            if ready:
                command = [sys.executable, '-u', str(Path(__file__).resolve()), 'run', '--spec', str(spec_path), '--sha256', expected_sha]
                env = dict(os.environ, CUDA_VISIBLE_DEVICES='0,1,2,3,4,5,6,7', WANDB_MODE='disabled',
                           WANDB_DISABLED='true', PATH='/home/ucloud/miniforge3/envs/hrm/bin:'+os.environ.get('PATH',''))
                with (root/'generation.log').open('x') as log:
                    child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                             start_new_session=True)
                write_json(root/'launch.json', dict(pid=child.pid, pgid=os.getpgid(child.pid), time=time.time(),
                           command=command, spec_sha256=expected_sha, gpu_before=snapshots,
                           dependency_sha256=file_hash(spec['dependency_receipt'])))
                code = child.wait()
                write_json(root/'watch-completion.json', dict(time=time.time(), exit_code=code,
                           no_training_resume=True, no_full_evaluation=True))
                return code
            time.sleep(15)
        write_json(root/'watch-completion.json', dict(time=time.time(), status='dependency_wait_expired', gpu_launched=False))
        return 3


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--corpus', type=Path, required=True); p.add_argument('--queue-root', type=Path, required=True)
    p.add_argument('--pilot-root', type=Path, help='Explicit parent/Poincare-confirmed pilot dependency; never infer latest root')
    p.add_argument('--manual-co-resident', action='store_true', help='Explicit user override: all8 EMA, bounded half-memory co-residency, no pilot dependency')
    for name in ('watch','run'):
        p = sub.add_parser(name); p.add_argument('--spec', type=Path, required=True); p.add_argument('--sha256', required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.corpus, args.queue_root, args.pilot_root, args.manual_co_resident)
    else:
        raise SystemExit((watch if args.command == 'watch' else run)(args.spec.resolve(), args.sha256))
