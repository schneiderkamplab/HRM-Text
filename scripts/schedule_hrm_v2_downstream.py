"""Prepare matched native 3.82M evaluation; install only into a drained plan."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
from eval_scheduler.model import Action, Job, JobStatus, plan_database, write_plan, read_plan
from eval_scheduler.store import SQLiteJobStore
from stop_training_at_complete_checkpoint import preserve, complete

PLAN = ROOT / 'logs/scheduler/dfm10_XL_epoch9_20260831'
CHILD = ROOT / 'logs/scheduler/hrm_v2_control_3820000_native'
TAG = 'step_3820000'
ID = 'hrm-v2-control-3820000-native-evals'
RUN = 'dfm8-xl-from-dfm6-dfm7-epoch5-clean-full'
DFM_TASKS = frozenset(('dala', 'gec_dala', 'piqa', 'multi_wiki_qa',
    'generative_talemaader', 'wmt24pp_en_da', 'govreport', 'nordjyllandnews',
    'humaneval', 'mbpp', 'danish_citizen_tests', 'andersen_modernization'))
INFERENCE = {Action.EVAL_STANDARD, Action.EVAL_DFM, Action.EVAL_DFM_IFEVAL}
MERGES = {Action.MERGE_STANDARD, Action.MERGE_DFM, Action.MERGE_IFEVAL}


def snapshot(mode):
    source = ROOT / 'checkpoints/hrm_v2' / f'hrm-{mode}-XL-from-3800000'
    target = CHILD / 'checkpoints' / mode
    if not target.exists():
        preserve(source, target, TAG)
    if not complete(target, TAG):
        raise RuntimeError(f'Incomplete snapshot {target}')
    cfg_path = target / 'all_config.yaml'
    cfg = yaml.safe_load(cfg_path.read_text())
    if mode == 'v2':
        # Pilot predates the gates-off default. Explicitly retain its architecture.
        assert cfg['arch']['name'] == 'baselines.hrm_v2@HierarchicalReasoningModel'
        cfg['arch']['gates_enabled'] = True
        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    meta_path = target / 'train_metadata.yaml'
    meta = yaml.safe_load(meta_path.read_text())
    tokenizer = ROOT / 'incoming/mimir-xl-20261015/data/dfm11_tokenizer'
    template = ROOT / 'incoming/mimir-xl-20261015/data/sampled_dfm15/chat_template.jinja'
    assert (tokenizer / 'tokenizer.json').is_file() and template.is_file()
    meta['tokenizer_info'].update(tokenizer_path=str(tokenizer), chat_template_path=str(template))
    meta_path.write_text(yaml.safe_dump(meta, sort_keys=False))
    state = json.loads((target / f'checkpoint_state_{TAG}.json').read_text())
    rows = len(np.load(ROOT / 'incoming/mimir-xl-20261015/data/sampled_dfm15/epoch_0/inst_len.npy', mmap_mode='r'))
    return target, 11.812711203938841 + state['global_row_cursor_in_epoch'] / rows


def standard_config():
    cfg = yaml.safe_load((ROOT / 'evaluation/config/dfm6_vllm_benchmarking.yaml').read_text())
    cfg = {k: cfg[k] for k in ('ckpt_path', 'generation_config', 'benchmarks')}
    cfg['engine'] = 'SimpleEngine'
    cfg['ckpt_tag'] = TAG
    cfg['generation_config'].pop('stop_token_ids', None)
    for b in cfg['benchmarks']:
        # Keep production prompts/scoring/limits, but allow native batch sizing.
        b.get('generation_config', {}).pop('batch_size', None)
    path = CHILD / 'standard.yaml'
    path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    return path


def select(j):
    return (j.action in (Action.EVAL_STANDARD, Action.MERGE_STANDARD,
                         Action.EVAL_DFM_IFEVAL, Action.MERGE_IFEVAL)
            or j.action in (Action.EVAL_DFM, Action.MERGE_DFM) and j.name in DFM_TASKS)


def build(jobs):
    template = [j for j in jobs if j.metadata.get('eval_step') == 1150000 and select(j)]
    assert len({j.name for j in template if j.action == Action.EVAL_STANDARD}) == 8
    assert {j.name for j in template if j.action == Action.EVAL_DFM} == DFM_TASKS
    all_rows = []
    config = standard_config()
    epochs = {}
    for mode in ('v2', 'control'):
        checkpoint, epoch = snapshot(mode)
        epochs[mode] = epoch
        prefix = f'{mode}-3820000-'
        mapping = {j.job_id: prefix + str(i) for i, j in enumerate(template)}
        # SQLite's publication rows have the original IDs. Native jobs publish inline.
        aliases = {j.job_id.removesuffix('-inference'): mapping[j.job_id]
                   for j in template if j.action in INFERENCE}
        mapping.update(aliases)
        roots = {k: str(CHILD / mode / k) for k in ('log_root', 'dfm_log_root')}
        def rewrite(v):
            if isinstance(v, str):
                for key, new in roots.items():
                    old = template[0].metadata[key]
                    v = v.replace(old, new)
                return v.replace('step_1150000', TAG)
            if isinstance(v, dict):
                return {k: rewrite(x) for k, x in v.items()}
            if isinstance(v, list):
                return [rewrite(x) for x in v]
            return v
        for j in template:
            meta = rewrite(j.metadata)
            for key in ('dfm14_boundary', 'defer_dfm_export', 'fixed_retry_batch',
                        'hrm_hf_export_dir', 'standard_hf_export_dir'):
                meta.pop(key, None)
            meta.update(ckpt_path=str(checkpoint), ckpt_tag=TAG, eval_step=3820000,
                        eval_epoch=epoch, standard_engine_backend='simple', hrm_server_backend='simple',
                        standard_config=str(config), include_hf_export=False,
                        no_ema=False, plan_dir=str(CHILD), min_gpu_free_mib=60000,
                        save_native_generations=True,
                        model_prefix=f'hrm-{mode}-XL-native', log_wandb=True,
                        wandb_project='DFM5', wandb_run_id='hrm-v2-XL-from-3800000' if mode=='v2' else RUN,
                        wandb_run_name='hrm-v2-XL-from-3800000' if mode=='v2' else 'DFM8-XL clean full from DFM6-DFM7 epoch5',
                        **roots)
            deps = tuple(mapping[d] for d in j.deps if d in mapping) if j.action in MERGES else ()
            if j.action in MERGES:
                assert len(deps) == len(j.deps), (j.job_id, j.deps)
            batch = 16 if j.action in INFERENCE else None
            if j.action == Action.EVAL_STANDARD and j.name not in ('MATH', 'GSM8k'):
                batch = 64
            all_rows.append(j.with_updates(job_id=mapping[j.job_id], deps=deps,
                status=JobStatus.PENDING, attempt=0, max_retries=5, initial_batch=batch,
                log_dir=rewrite(j.log_dir), metadata=meta))
    assert abs(epochs['v2']-epochs['control']) < 1e-12, epochs
    return all_rows, epochs


def install(store):
    if store.get_admin_lock():
        raise RuntimeError('Plan already locked')
    store.set_admin_lock(True)
    try:
        jobs = store.load_jobs()
        if any(j.status == JobStatus.RUNNING for j in jobs):
            raise RuntimeError('Wait for scheduler drain before installation')
        if any(j.job_id == ID for j in jobs):
            print('Already installed'); return
        assert read_plan(CHILD / 'plan.tsv')
        next_id = 'xl-dfm15-resume-3800000-to-3850000'
        next_job = next(j for j in jobs if j.job_id == next_id)
        assert next_job.status == JobStatus.PENDING
        evals = Job(ID, Action.EVAL_NATIVE_PLAN, 'native', 'XL gated/control 3.82M native comparison',
            deps=next_job.deps, gpu_policy='all', gpu_count=8, max_retries=0,
            log_dir=str(CHILD), metadata={'native_plan_dir': str(CHILD),
                'python_bin': '/home/ucloud/miniforge3/envs/hrm/bin/python', 'min_gpu_free_mib': 178000})
        gate = Job(ID+'-terminal', Action.TERMINAL_BARRIER, 'control',
                   'Native comparison terminal; training continues on eval failures',
                   deps=(ID,), deps_mode='terminal')
        updated = []
        for j in jobs:
            if j.job_id == next_id:
                updated.extend([evals, gate])
                j = j.with_updates(deps=(*j.deps, gate.job_id))
            updated.append(j)
        store.backup(PLAN / f'before-native-3820k-{int(time.time())}.sqlite')
        store.import_jobs(updated, require_admin_lock=True)
        store.export_tsv(PLAN / 'plan.tsv')
        store.backup(PLAN / 'state.backup.sqlite')
        print('Installed native comparison before XL 3.82M -> 3.85M; 1.15M/3.85M unchanged')
    finally:
        store.set_admin_lock(False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--install', action='store_true')
    args = p.parse_args()
    store = SQLiteJobStore(plan_database(PLAN / 'plan.tsv'))
    if args.install:
        install(store)
    else:
        CHILD.mkdir(parents=True, exist_ok=True)
        if (CHILD / 'plan.tsv').exists():
            raise RuntimeError('Refusing to overwrite prepared/results plan')
        jobs, epochs = build(store.load_jobs())
        write_plan(CHILD / 'plan.tsv', jobs)
        receipt = {'jobs': len(jobs), 'actions': dict(Counter(str(j.action) for j in jobs)),
                   'epochs': epochs, 'ema': True, 'dfm_tasks': sorted(DFM_TASKS),
                   'scope': 'Full standard plus core DFM; excludes EuroEval and extended multilingual tasks'}
        (CHILD / 'preparation.json').write_text(json.dumps(receipt, indent=2)+'\n')
        print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
