"""Install the matched 3.82M vLLM comparison without interrupting live claims."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

import schedule_hrm_v2_downstream as base
from eval_scheduler.model import Action, Job, JobStatus, plan_database, write_plan
from eval_scheduler.plan import split_euroeval_postprocessing
from eval_scheduler.runtime import vllm_server_key
from eval_scheduler.store import SQLiteJobStore

ROOT = base.ROOT
OUT = ROOT / 'logs/scheduler/mimir2_control_3820000_vllm'
PREFIX = 'mimir2-3820k-'


def build(existing):
    base.CHILD = OUT
    OUT.mkdir(parents=True, exist_ok=True)
    jobs, epochs = base.build(existing)
    successor = next(j for j in existing if j.job_id == 'xl-dfm15-resume-3800000-to-3850000')
    if successor.status != JobStatus.PENDING:
        raise RuntimeError('XL continuation already claimed; choose a new safe boundary')
    mapping = {j.job_id: PREFIX + j.job_id for j in jobs}
    start = Job(PREFIX + 'start', Action.TERMINAL_BARRIER, 'control',
                'Matched 3.82M comparison after existing XXL evaluation boundary',
                deps=successor.deps, deps_mode='terminal')
    rows = [start]
    for j in jobs:
        mode = 'v2' if j.job_id.startswith('v2-') else 'control'
        export = ROOT / f'exports/mimir2_{mode}_step3820000_ema_hf'
        receipt = json.loads((export / 'export_receipt.json').read_text())
        cfg = json.loads((export / 'config.json').read_text())
        assert receipt['ema'] and receipt['tag'] == base.TAG
        assert cfg['architectures'] == ['Mimir2ForCausalLM']
        assert not cfg.get('mos_sparse', False)
        assert bool(cfg.get('gates_enabled')) == (mode == 'v2')
        meta = dict(j.metadata)
        meta.update(
            plan_dir=str(base.PLAN), include_hf_export=True,
            standard_config=str(ROOT / 'evaluation/config/dfm6_vllm_benchmarking.yaml'),
            standard_engine_backend='vllm', hrm_server_backend='vllm',
            standard_hf_export_dir=str(export), hrm_hf_export_dir=str(export),
            vllm_python='/home/ucloud/miniforge3/envs/mimir2/bin/python',
            cuda_home='/home/ucloud/miniforge3/envs/mimir2',
            vllm_attention_backend='FLASH_ATTN',
            vllm_extra_args='--no-enable-prefix-caching --no-enable-chunked-prefill '
                            '--chat-template /work/dfm/HRM-Text/evaluation/chat_templates/gemma4_native_chat.jinja',
            vllm_start_timeout=3600, min_gpu_free_mib=178000,
            model_prefix=f'mimir2-{mode}-3820000-ema',
        )
        # Preserve the proven lower memory budget for same-GPU judge tasks.
        meta['vllm_gpu_memory_utilization'] = 0.65 if meta.get('judge_model') else 0.9
        deps = tuple(mapping[d] for d in j.deps) or (start.job_id,)
        row = j.with_updates(job_id=mapping[j.job_id], deps=deps, metadata=meta)
        if row.action in base.INFERENCE:
            key = vllm_server_key(row, 0)
            assert '--enforce-eager' not in key.extra_args
            assert key.python.endswith('/mimir2/bin/python')
        rows.append(row)
    rows = split_euroeval_postprocessing(rows)
    inference = tuple(j.job_id for j in rows if j.action in base.INFERENCE)
    terminal = Job(PREFIX + 'inference-terminal', Action.TERMINAL_BARRIER, 'control',
                   'Resume XL even if comparison inference fails; publication is independent',
                   deps=inference, deps_mode='terminal')
    rows.append(terminal)
    updated = []
    for j in existing:
        if j.job_id == successor.job_id:
            updated.extend(rows)
            j = j.with_updates(deps=(*j.deps, terminal.job_id))
        updated.append(j)
    return rows, updated, epochs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--install', action='store_true')
    args = p.parse_args()
    store = SQLiteJobStore(plan_database(base.PLAN / 'plan.tsv'))
    if any(j.job_id.startswith(PREFIX) for j in store.load_jobs()):
        raise RuntimeError('Comparison already installed')
    if args.install:
        if store.get_admin_lock():
            raise RuntimeError('Existing administrative lock; do not steal it')
        store.set_admin_lock(True)
    try:
        rows, updated, epochs = build(store.load_jobs())
        write_plan(OUT / 'prepared.tsv', rows)
        receipt = dict(actions=dict(Counter(j.action.value for j in rows)), epochs=epochs,
                       eager=False, ema=True, installed=args.install,
                       scope='8 standard and 13 core DFM tasks per checkpoint; no EuroEval')
        if args.install:
            store.backup(base.PLAN / f'before-mimir2-3820k-{int(time.time())}.sqlite')
            store.import_jobs(updated, require_admin_lock=True)
            store.export_tsv(base.PLAN / 'plan.tsv')
            store.backup(base.PLAN / 'state.backup.sqlite')
        (OUT / 'preparation.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, indent=2))
    finally:
        if args.install:
            store.set_admin_lock(False)


if __name__ == '__main__':
    main()
