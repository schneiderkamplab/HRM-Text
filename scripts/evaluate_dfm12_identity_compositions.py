#!/usr/bin/env python3
"""Sealed composition evaluation adapter: EMA only, after corrective training.

Preflight reads CPU assets only. Runtime uses frozen v4 workers; exit zero means
operational completion, never semantic acceptance or permission to train/export.
"""
import argparse
from collections import Counter
from collections.abc import Mapping
import copy
import os
from pathlib import Path
import signal
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import atomic, digest, file_hash, load, lock, write_json
from scripts import evaluate_dfm12_identity_continuation_v4 as evaluation
from scripts import queue_dfm12_identity_ema_samples as memory

HOLDOUT = ROOT/'data/dfm12/identity-composition-holdout-20260927-v1'
HOLDOUT_SHA = 'bd1181b9d37b4da3afc8dfbc7ee20599a1010dd85b60c867d712b712a369787c'
V4_SHA = '96656afd01dd02974e97e55a1c6f535cc0d0842896624a8d18dad261fd54e5ab'
MEMORY_SHA = '6dc88744124275cbdbfbfd994a6271b7f45f4fda111352cb6d5794a7302323e3'
CHECKPOINT = ROOT/'checkpoints/dfm12/XL-identity-corrective10000-from-step2887261'
TRAINING_RECEIPT = ROOT/'logs/training/dfm12_XL_identity_corrective10000steps/complete.json'
TAG = 'step_2897261'
ORIGINAL_WORKER = evaluation.worker


def memory_policy(allocator_gib):
    if not 16 <= allocator_gib <= 80:
        raise ValueError('Allocator budget must be between 16 and 80 GiB')
    return dict(memory.CO_RESIDENT_POLICY,
                allocator_limit_gib_per_worker=allocator_gib,
                required_free_mib=(allocator_gib + 12) * 1024)


def verify_helpers():
    evaluation.verify_helpers()
    for path, expected in ((evaluation.__file__, V4_SHA), (memory.__file__, MEMORY_SHA)):
        if file_hash(path) != expected:
            raise ValueError('Frozen evaluator dependency changed: '+str(path))


def load_holdout(root):
    root = Path(root).resolve()
    if file_hash(root/'manifest.json') != HOLDOUT_SHA:
        raise ValueError('Sealed holdout manifest changed')
    manifest = load(root/'manifest.json')
    if (manifest['schema'] != 'sealed-identity-compositions-v1'
            or any(manifest[k] is not False for k in ('training_allowed','evaluated','model_outputs_used'))
            or manifest['exact_normalized_overlap'] != 0
            or set(manifest['files']) != {'cases.json','rubric.json'}):
        raise ValueError('Invalid sealed holdout policy')
    pins = {str(root/name): sha for name,sha in manifest['files'].items()}
    pins[str(root/'manifest.json')] = HOLDOUT_SHA
    pins[manifest['source']] = manifest['source_sha256']
    pins.update({str(Path(manifest['authority'])/name): sha
                 for name,sha in manifest['authority_pins'].items()})
    pins.update(manifest['exclusions'])
    for path,sha in pins.items():
        if file_hash(path) != sha:
            raise ValueError('Holdout evidence drift: '+path)
    cases, rubric = load(root/'cases.json'), load(root/'rubric.json')
    facts = load(Path(manifest['authority'])/'facts.json')
    allowed = set(facts['facts']) | {'current_runtime','continuation','xl-full-bp'}
    seen, questions = set(), set()
    for case in cases:
        record_sha = digest(case)
        if (case['id'] in seen or case['language'] not in ('da','en')
                or case['suite'] != 'sealed_identity_compositions'
                or case['training_allowed'] is not False
                or case['history_policy'] != 'Generate each followup using this rollout history; never supply gold answers'
                or len(case['users']) != 2 or len(case['criteria']) != 2
                or not case['facts'] or not set(case['facts']) <= allowed):
            raise ValueError('Invalid composition case binding')
        for text in case['users']+case['criteria']:
            if not isinstance(text,str) or not text.strip():
                raise ValueError('Empty composition prompt/criterion')
        for text in case['users']:
            key = evaluation.historical.normalize(text)
            if key in questions:
                raise ValueError('Duplicate composition user turn')
            questions.add(key)
        seen.add(case['id'])
        # V4 stores these for inspection only; run_conversation sends users and
        # actual generated history, never these criteria or the factual registry.
        case['expected_targets'] = copy.deepcopy(case['criteria'])
        case['requests'] = [list(case['facts']) for _ in case['users']]
        case['source_record_sha256'] = record_sha
    if (len(cases) != manifest['conversations'] or len(cases) != 40
            or sum(len(c['users']) for c in cases) != manifest['turns'] or manifest['turns'] != 80
            or Counter(c['language'] for c in cases) != {'da':20,'en':20}
            or not all(isinstance(rubric.get(k),str) and rubric[k].strip()
                       for k in ('scoring','correct','partial','fail','invalid','caveat'))):
        raise ValueError('Incomplete composition coverage/rubric')
    supplement = load(Path(manifest['authority'])/'authority-supplement.json')
    assets = supplement['runtime_asset_binding']['assets']
    for asset in assets.values():
        if file_hash(asset['path']) != asset['sha256']:
            raise ValueError('Runtime asset changed')
        pins[asset['path']] = asset['sha256']
    return cases, rubric, assets, pins


def cpu_prompt_preflight(cases, assets, max_tokens):
    from transformers import PreTrainedTokenizerFast
    tokenizer = PreTrainedTokenizerFast(tokenizer_file=assets['tokenizer']['path'])
    tokenizer.chat_template = Path(assets['template']['path']).read_text()
    tokenizer.pad_token,tokenizer.bos_token,tokenizer.eos_token = '<pad>','<bos>','<turn|>'
    measurements = {}
    for case in cases:
        # Bound both generated assistant turns, keeping the actual history at run
        # time. No reference answers or facts are inserted into a prompt.
        messages = [{'role':'user','content':case['users'][0]},
                    {'role':'assistant','content':''},
                    {'role':'user','content':case['users'][1]}]
        ids = tokenizer.apply_chat_template(messages,tokenize=True,
            add_generation_prompt=True,enable_thinking=False)
        if isinstance(ids,Mapping):
            ids = ids['input_ids']
        if not isinstance(ids,list) or any(type(i) is not int for i in ids):
            raise ValueError('Unexpected prompt tokenization result')
        bound = len(ids)+2*max_tokens+32
        if bound >= 4096:
            raise ValueError('Composition history/output budget exceeds context')
        measurements[case['id']] = {'conservative_total_tokens':bound}
    return measurements


def verify_release(checkpoint, training_receipt, release_path):
    training = load(training_receipt)
    if (training.get('step') != 2897261 or training.get('evaluation_export') != 'EMA_ONLY'
            or Path(training['output']).resolve() != checkpoint.resolve()):
        raise ValueError('Require completed corrective2897261 training receipt')
    release = load(release_path)
    if (release.get('campaign') != 'identity-composition-evaluation'
            or release.get('step') != 2897261 or release.get('all_owned_gpu_work_released') is not True
            or not isinstance(release.get('owned_pids'),list) or not release['owned_pids']
            or any(type(pid) is not int or pid <= 0 for pid in release['owned_pids'])):
        raise ValueError('Explicit post-training owned-GPU release receipt required')
    # PID reuse conservatively blocks; this adapter never signals those PIDs.
    if any(Path(f'/proc/{pid}').exists() for pid in release['owned_pids']):
        raise ValueError('Previously owned GPU work still alive; do not overlap')
    return {str(Path(p).resolve()):file_hash(p) for p in (training_receipt,release_path)}


def save(output, report):
    turns = [t for run in report['runs'] for c in run['conversations'] for t in c['turns']]
    for turn in turns:
        turn.pop('heuristics',None)
        turn['semantic_review'] = 'pending_manual_review'
    report.update(review_required=True,identity_positive=None,full_suite_approved=None,
                  operational_success=report['status'] in evaluation.v3.COMPLETED)
    write_json(output/'responses.json',report)
    write_json(output/'summary.json',dict(status=report['status'],turns=len(turns),
        expected_turns=80,length_stops=sum(t['truncated'] for t in turns),
        semantic_review='pending_manual_review',semantic_pass=None,
        training_allowed=False,export_authorized=False,operational_success=report['operational_success']))
    lines = ['# Sealed Composition Responses','',
             'Manual semantic review required. Criteria are not model inputs. No lexical pass.','']
    for run in report['runs']:
        for case in run['conversations']:
            lines += [f"## {case['id']} / {case['language']}",'']
            for turn in case['turns']:
                lines += [f"### Turn {turn['turn']}",'',turn['user'],'',
                          '**Actual generated answer**','',turn['response'],'',
                          '**Sealed criterion, not supplied**','',turn['expected_target'],'',
                          f"Finish: {turn['finish_reason']}; tokens: {turn['generated_token_count']}",'']
    with atomic(output/'responses.md') as handle:
        handle.write('\n'.join(lines))


def worker(gpu, initial, tasks, cancelled, load_slots, report, run, manifest, phase_dir, deadline):
    verify_helpers()
    if file_hash(__file__) != report['adapter_sha256']:
        raise ValueError('Composition adapter drift')
    for path,sha in report['input_pins'].items():
        if file_hash(path) != sha:
            raise ValueError('Composition input drift: '+path)
    stop = threading.Event()
    def guard():
        peak = 0
        while not stop.is_set():
            try:
                snapshot = memory.real_memory(gpu,os.getpid())
                ceiling = memory.check_co_resident(report,snapshot)
                peak = max(peak,snapshot['own_used_mib'])
                write_json(Path(phase_dir)/f'memory-gpu-{gpu}.json',dict(
                    pid=os.getpid(),peak_own_mib=peak,ceiling_mib=ceiling,**snapshot))
            except BaseException as exc:
                write_json(Path(phase_dir)/f'memory-gpu-{gpu}-failure.json',dict(error=str(exc)))
                cancelled.set()
                os.kill(os.getpid(),signal.SIGTERM)
                return
            stop.wait(1)
    monitor = threading.Thread(target=guard,daemon=True)
    monitor.start()
    try:
        ORIGINAL_WORKER(gpu,initial,tasks,cancelled,load_slots,report,run,manifest,phase_dir,deadline)
    finally:
        stop.set()
        monitor.join(timeout=12)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--heldout-root',type=Path,default=HOLDOUT)
    parser.add_argument('--checkpoint',type=Path,default=CHECKPOINT)
    parser.add_argument('--training-completion',type=Path,default=TRAINING_RECEIPT)
    parser.add_argument('--gpu-release-receipt',type=Path)
    parser.add_argument('--preflight-only',action='store_true')
    parser.add_argument('--max-new-tokens',type=int,default=512)
    parser.add_argument('--max-seconds',type=int,default=3600)
    parser.add_argument('--allocator-limit-gib',type=int,default=80)
    args = parser.parse_args(argv)
    policy = memory_policy(args.allocator_limit_gib)
    if not 1 <= args.max_new_tokens <= 512 or not 1 <= args.max_seconds <= 7200:
        parser.error('Output limit1..512; total runtime1..7200 seconds')
    if not args.preflight_only and args.gpu_release_receipt is None:
        parser.error('Runtime requires --gpu-release-receipt after training has finished')
    verify_helpers()
    cases,rubric,assets,pins = load_holdout(args.heldout_root)
    measurements = cpu_prompt_preflight(cases,assets,args.max_new_tokens)
    run = dict(label='continued',checkpoint=str(args.checkpoint.resolve()),tag=TAG,
               status='planned',conversations=[])
    report = dict(status='preflight',started=time.time(),cases=cases,rubric=rubric,
        ema=True,non_ema=False,latest_only=True,heldout_only=True,wandb=False,
        identity_priming=False,batch_size=1,gpus=list(evaluation.GPUS),
        max_context=4096,max_new_tokens=args.max_new_tokens,max_seconds=args.max_seconds,
        concurrent_checkpoint_loads=2,adapter_sha256=file_hash(__file__),script_sha256=V4_SHA,
        inference_source_sha256=file_hash(ROOT/'simple_inference_engine.py'),
        input_pins=pins,prompt_preflight=measurements,runs=[run],
        history_policy='Actual generated history only; never rubric, facts or gold assistant priming',
        dataset_policy=dict(training_allowed=False,semantic_pass=None,
            evidence_scope='Sealed prompt composition over known facts, not unseen knowledge'),
        **policy)
    # Fresh outputs only, including preflight. Frozen sealed inputs are never edited.
    args.output.mkdir(parents=True,exist_ok=False)
    if args.preflight_only:
        save(args.output,report)
        print('CPU preflight:40 conversations/80 turns; no GPU probe, inference or generated answers')
        return 0
    with lock(args.output/'.evaluation.lock'):
        try:
            report['input_pins'].update(verify_release(args.checkpoint,args.training_completion,args.gpu_release_receipt))
            run['checkpoint_pins'] = evaluation.checkpoint_pins(run)
            evaluation.ema_source(args.checkpoint,TAG)
            report['runtime_asset_binding'] = evaluation.runtime_asset_binding(args.checkpoint,assets)
            for gpu in evaluation.GPUS:
                memory.check_co_resident(report,memory.real_memory(gpu),loading=True)
            report['contract_sha256'] = digest(report)
            report['status'] = 'running'
            old_worker,old_save = evaluation.worker,evaluation.save
            evaluation.worker,evaluation.save = worker,save
            try:
                result = evaluation.run_phase(report,run,assets,args.output,args.max_seconds)
                if result == 0:
                    result = evaluation.finish_report(report)
                return result
            finally:
                evaluation.worker,evaluation.save = old_worker,old_save
        except BaseException as exc:
            report.update(status='failed',error=repr(exc))
            raise
        finally:
            save(args.output,report)
            write_json(args.output/'completion.json',dict(status=report['status'],
                responses_sha256=file_hash(args.output/'responses.json'),review_required=True,
                semantic_pass=None,training_allowed=False,export_authorized=False))


if __name__ == '__main__':
    raise SystemExit(main())
