"""Expand the three queued 3.82M arms to the full 1.15M task inventory."""
import argparse
from collections import Counter
import json
import time

import schedule_mimir2_3820k as base
from eval_scheduler.model import JobStatus

INFERENCE = {'eval_standard', 'eval_dfm', 'eval_dfm_ifeval', 'eval_euroeval',
             'eval_euroeval_batched_ifeval'}
ACTIONS = INFERENCE | {'export_dfm_results', 'merge_standard', 'merge_dfm',
                       'merge_ifeval', 'merge_euroeval', 'average'}
ARMS = ('mimir2-3820k-v2-3820000-', 'mimir2-3820k-control-3820000-',
        'hrm-3820k-control-3820000-')
IDENTITY = ('ckpt_path', 'ckpt_tag', 'eval_step', 'eval_epoch', 'wandb_project',
            'wandb_run_id', 'wandb_run_name', 'model_prefix', 'plan_dir',
            'standard_hf_export_dir', 'hrm_hf_export_dir', 'vllm_python',
            'cuda_home', 'vllm_extra_args', 'vllm_attention_backend',
            'standard_engine_backend', 'hrm_server_backend', 'include_hf_export',
            'no_ema', 'vllm_start_timeout', 'min_gpu_free_mib')


def key(job):
    return job.action.value, job.name, job.shard, job.shards


def build(jobs):
    template = [j for j in jobs if j.metadata.get('eval_step') == 1150000
                and j.action.value in ACTIONS]
    assert len({key(j) for j in template}) == len(template)
    assert sum(j.action.value in INFERENCE for j in template) == 1047
    by_id = {j.job_id: j for j in jobs}
    terminal_id = 'mimir2-3820k-inference-terminal'
    assert by_id[terminal_id].status == JobStatus.PENDING
    assert by_id['xl-dfm15-resume-3800000-to-3850000'].status == JobStatus.PENDING
    start = 'mimir2-3820k-start'
    added = []
    inference_ids = []
    report = {}
    for prefix in ARMS:
        existing = [j for j in jobs if j.job_id.startswith(prefix)]
        assert existing
        lookup = {key(j): j for j in existing}
        assert len(lookup) == len(existing)
        exemplar = existing[0].metadata
        mapping = {j.job_id: lookup[key(j)].job_id if key(j) in lookup
                   else prefix + 'full-' + str(i) for i, j in enumerate(template)}
        roots = {k: exemplar[k] if k != 'euroeval_log_root'
                 else str(base.OUT / prefix.rstrip('-') / 'euroeval')
                 for k in ('log_root', 'dfm_log_root', 'euroeval_log_root')}
        replacements = {}
        for j in template:
            for k, new in roots.items():
                old = j.metadata.get(k)
                if old:
                    replacements[str(base.ROOT / old)] = new
                    replacements[old] = new

        def rewrite(value):
            if isinstance(value, str):
                if value in mapping:
                    return mapping[value]
                for old in sorted(replacements, key=len, reverse=True):
                    value = value.replace(old, replacements[old])
                return value.replace('step_1150000', 'step_3820000')
            if isinstance(value, dict):
                return {k: rewrite(v) for k, v in value.items()}
            if isinstance(value, list):
                return [rewrite(v) for v in value]
            return value

        arm_added = []
        for j in template:
            if key(j) in lookup:
                continue
            meta = rewrite(j.metadata)
            meta.update({k: exemplar[k] for k in IDENTITY if k in exemplar})
            meta.update(roots)
            meta.pop('dfm14_boundary', None)
            meta.pop('fixed_retry_batch', None)
            meta['vllm_gpu_memory_utilization'] = 0.65 if meta.get('judge_model') else 0.9
            deps = []
            for d in j.deps:
                if d in mapping:
                    deps.append(mapping[d])
                else:
                    assert by_id[d].action.value in ('export_hf', 'terminal_barrier'), d
                    deps.append(start)
            row = j.with_updates(job_id=mapping[j.job_id],
                deps=tuple(dict.fromkeys(deps)) or (start,),
                status=JobStatus.PENDING, attempt=0, max_retries=5,
                log_dir=rewrite(j.log_dir), metadata=meta)
            assert '1150000' not in json.dumps(row.metadata)
            assert '--enforce-eager' not in meta['vllm_extra_args']
            arm_added.append(row)
        all_arm = existing + arm_added
        assert Counter(key(j) for j in all_arm) == Counter(key(j) for j in template)
        inference_ids.extend(j.job_id for j in all_arm if j.action.value in INFERENCE)
        report[prefix] = dict(added=len(arm_added), total=len(all_arm),
                             inference=1047, run=exemplar['wandb_run_id'])
        added.extend(arm_added)
    updated = []
    for j in jobs:
        if j.job_id == terminal_id:
            updated.extend(added)
            j = j.with_updates(deps=tuple(inference_ids), deps_mode='terminal')
        updated.append(j)
    assert len(inference_ids) == 3141
    return updated, report, len(added)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    store = base.SQLiteJobStore(base.plan_database(base.base.PLAN / 'plan.tsv'))
    if args.install:
        if store.get_admin_lock():
            raise RuntimeError('Existing admin lock; refusing to steal it')
        store.set_admin_lock(True)
    try:
        updated, arms, added = build(store.load_jobs())
        if args.install:
            store.backup(base.base.PLAN / f'before-full-3820k-{int(time.time())}.sqlite')
            store.import_jobs(updated, require_admin_lock=True)
            store.export_tsv(base.base.PLAN / 'plan.tsv')
            store.backup(base.base.PLAN / 'state.backup.sqlite')
        report = dict(installed=args.install, added_rows=added, arms=arms)
        (base.OUT / 'full_suite_preparation.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    finally:
        if args.install:
            store.set_admin_lock(False)


if __name__ == '__main__':
    main()
