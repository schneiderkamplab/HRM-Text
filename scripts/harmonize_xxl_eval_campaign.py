"""Reconcile pending XXL campaigns with a snapshotted XL task/average contract.

Keep local model, capacity, runtime state and training commands. Copy benchmark
protocols, not remote launch environments. SQLite is the only live authority.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
sys.path.insert(0, str(ROOT))
from eval_scheduler.database_cli import validate_graph
from eval_scheduler.model import Action, Job, JobStatus, plan_database
from eval_scheduler.store import SQLiteJobStore
from scripts.schedule_identity_final_ema_full import canonical_log_dir

INFERENCE = {Action.EVAL_STANDARD, Action.EVAL_DFM, Action.EVAL_DFM_IFEVAL,
             Action.EVAL_EUROEVAL, Action.EVAL_EUROEVAL_BATCHED_IFEVAL}
COPY_ACTIONS = INFERENCE | {Action.EXPORT_DFM_RESULTS, Action.MERGE_DFM,
                           Action.MERGE_STANDARD, Action.MERGE_IFEVAL,
                           Action.MERGE_EUROEVAL, Action.AVERAGE}
PROTOCOL = {'dfm_suite', 'dfm_max_gen_toks', 'dfm_single_tasks_config', 'language',
            'euroeval_languages', 'euroeval_context_policy', 'euroeval_category',
            'euroeval_inference_action', 'defer_dfm_export', 'defer_euroeval_merge',
            'semantic_acceptability_version', 'shards'}
AVERAGES = {'average_prefix', 'average_scope', 'atomic_v3_averages',
            'extra_average_prefixes', 'multilingual_manifest',
            'population_require_complete', 'population_manifest_sha256',
            'semantic_acceptability_version'}


def identity(job):
    if job.action == Action.AVERAGE:
        # Expanded DaLA dispatch takes precedence over its provenance manifest.
        prefix = job.metadata.get('average_prefix', 'headline_avg_v2')
        manifest = job.metadata.get('multilingual_manifest')
        if manifest and prefix not in ('headline_avg_dala_v2', 'suite_avg_dala_v2'):
            return ('average', 'population', Path(manifest).name)
        return ('average', prefix)
    return (job.action.value, job.name, job.shard)


def load_reference(path, prefix):
    return [Job.from_row({**json.loads(r['definition']), 'status': r['status'],
                         'attempt': r['attempt'], 'log_dir': r['log_dir']})
            for r in json.loads(path.read_text())
            if r['job_id'].startswith(prefix) and r['status'] != 'skipped']


def build(jobs, reference, assets, plan, minimum_step=1000000, defer_first_to=None):
    reference = [j for j in reference if j.action in COPY_ACTIONS]
    if len({identity(j) for j in reference}) != len(reference):
        raise ValueError('Ambiguous reference task identities')
    steps = sorted({int(j.metadata['dfm14_boundary']) for j in jobs
                    if j.action == Action.EXPORT_HF and j.job_id.startswith('xxlw-dfm14-')
                    and int(j.metadata.get('dfm14_boundary', 0)) >= minimum_step})
    updates, additions, receipt = {}, [], {}
    deferred_inference = []
    deferred_boundary = None
    if defer_first_to:
        resume = next(j for j in jobs if j.job_id == defer_first_to)
        if resume.action != Action.TRAIN_UNTIL_STEP:
            raise ValueError('Deferred prerequisite must be a training boundary')
        deferred_boundary = int(resume.metadata['eval_step'])
        if deferred_boundary <= minimum_step:
            raise ValueError('Defer to a later boundary')
    mapping_paths = assets['mappings']
    for step in steps:
        prefix = f'xxlw-dfm14-{step}-'
        block = [j for j in jobs if j.job_id.startswith(prefix) and j.status != JobStatus.SKIPPED]
        export = next(j for j in block if j.action == Action.EXPORT_HF)
        known = {identity(j): j for j in block if j.action in COPY_ACTIONS}
        for job in block:
            if (job.status == JobStatus.PENDING and job.action in
                    (Action.EVAL_EUROEVAL, Action.EVAL_EUROEVAL_BATCHED_IFEVAL, Action.MERGE_EUROEVAL)):
                updates[job.job_id] = job.with_updates(metadata={**job.metadata,
                    'euroeval_bin': assets['euroeval_bin']})
        mapping = {}
        created = []
        for source in reference:
            key = identity(source)
            if key in known:
                mapping[source.job_id] = known[key].job_id
                continue
            suffix = hashlib.sha256(repr(key).encode()).hexdigest()[:10]
            job_id = prefix + f'parity-{source.name}-{suffix}'
            mapping[source.job_id] = job_id
            seed = next(j for j in block if j.action == source.action)
            if source.action == Action.EVAL_DFM:
                seed = next(j for j in block if j.action == source.action and j.name == 'dala_ga')
            elif source.action in (Action.EVAL_EUROEVAL, Action.MERGE_EUROEVAL):
                seed = next(j for j in block if j.action == source.action and j.name == 'scala-en')
            meta = dict(seed.metadata)
            for k in list(meta):
                if (k.startswith(('judge_', 'managed_judge', 'additional_'))
                        or k in AVERAGES or k in PROTOCOL):
                    meta.pop(k)
            allowed = AVERAGES if source.action == Action.AVERAGE else PROTOCOL
            for k in allowed:
                if k in source.metadata:
                    value = source.metadata[k]
                    if k in ('multilingual_manifest', 'dfm_single_tasks_config'):
                        value = mapping_paths.get(value, value)
                        if str(value).startswith('/work/dfm/'):
                            raise ValueError('Unprepared reference input: ' + value)
                    meta[k] = value
            meta.update(campaign_parity_reference=source.job_id, fix_mistral_regex=False)
            if source.action in (Action.EVAL_EUROEVAL, Action.MERGE_EUROEVAL):
                meta['euroeval_bin'] = assets['euroeval_bin']
                meta['hf_export_dir'] = meta.get('hf_export_dir') or meta.get('hrm_hf_export_dir') or meta.get('standard_hf_export_dir')
            if source.action == Action.AVERAGE:
                # All local outputs are under one root per suite, unlike remote history.
                for key in ('log_root', 'dfm_log_root', 'euroeval_log_root'):
                    meta[key] = export.metadata[key]
                if source.metadata.get('average_prefix') == 'headline_avg_talemaader_v2':
                    meta['python_bin'] = str(ROOT / 'scripts/todo5_future_average')
            job = source.with_updates(job_id=job_id, status=JobStatus.PENDING, attempt=0,
                metadata=meta, deps=(), max_retries=max(3, seed.max_retries),
                initial_batch=seed.initial_batch, gpu_policy=seed.gpu_policy,
                log_dir=str(plan / 'parity' / f'step_{step}' / source.name))
            job = job.with_updates(log_dir=str(canonical_log_dir(job)))
            if job.action == Action.EXPORT_DFM_RESULTS:
                job = job.with_updates(log_dir=str(Path(meta['dfm_log_root']) / job.name /
                    f'shard_{job.shard}_of_{job.shards}' / meta['ckpt_tag']))
            if job.action == Action.MERGE_EUROEVAL:
                job = job.with_updates(log_dir=str(Path(meta['euroeval_log_root']) /
                    meta['ckpt_tag'] / job.name))
            created.append((source, job))
        new_ids = {j.job_id for _, j in created}
        for source, job in created:
            if job.action in INFERENCE:
                deps = (export.job_id, defer_first_to) if defer_first_to and step == minimum_step else (export.job_id,)
            else:
                deps = tuple(mapping[d] for d in source.deps)
            job = job.with_updates(deps=deps)
            additions.append(job)
        # Existing population jobs must wait for the same contributors as the XL job.
        for source in reference:
            if source.action != Action.AVERAGE or mapping[source.job_id] in new_ids:
                continue
            old = known[identity(source)]
            deps = tuple(mapping[d] for d in source.deps)
            if set(deps) == set(old.deps):
                continue
            if old.status != JobStatus.PENDING:
                raise ValueError('Average already started; explicit replay required: ' + old.job_id)
            meta = dict(old.metadata)
            for key in AVERAGES:
                meta.pop(key, None)
                if key in source.metadata:
                    meta[key] = mapping_paths.get(source.metadata[key], source.metadata[key]) \
                        if isinstance(source.metadata[key], str) else source.metadata[key]
            for key in list(meta):
                if key.startswith('additional_'):
                    meta.pop(key)
            updates[old.job_id] = old.with_updates(deps=deps, metadata=meta)
        averages = tuple(mapping[j.job_id] for j in reference if j.action == Action.AVERAGE)
        for job in block:
            if job.action == Action.REPORT and job.status == JobStatus.PENDING:
                updates[job.job_id] = job.with_updates(deps=tuple(dict.fromkeys((*job.deps, *averages))))
        inference = [j.job_id for j in block if j.action in INFERENCE]
        inference += [j.job_id for j in additions if j.job_id.startswith(prefix) and j.action in INFERENCE]
        if defer_first_to and step == minimum_step:
            deferred_inference = [j.job_id for j in [*block, *additions]
                                  if j.job_id.startswith(prefix) and j.action in INFERENCE
                                  and j.metadata.get('campaign_parity_reference')]
        if step == deferred_boundary:
            inference += deferred_inference
        # Gate both teardown and the next training lease on inference only. CPU
        # publication failures are never prerequisites for resuming training.
        for job in jobs:
            if job.action != Action.TERMINAL_BARRIER:
                continue
            relevant = job.job_id.startswith(prefix) or (
                job.job_id.endswith('-evals-terminal') and any(d.startswith(prefix) for d in job.deps))
            if relevant:
                if defer_first_to and step == minimum_step:
                    continue
                if job.status != JobStatus.PENDING:
                    raise ValueError('Training boundary already released: ' + job.job_id)
                updates[job.job_id] = job.with_updates(deps=tuple(inference), deps_mode='terminal')
        own_inference = sum(j.startswith(prefix) for j in inference)
        receipt[step] = {'added': len(created), 'inference': own_inference,
                         'gate_inference': len(inference),
                         'parity_rows': sum(bool(j.metadata.get('campaign_parity_reference'))
                             for j in [*block, *additions] if j.job_id.startswith(prefix)),
                         'actions_added': dict(Counter(j.action.value for _, j in created))}
        if defer_first_to and step == minimum_step:
            receipt[step]['deferred_until'] = defer_first_to
    result = [updates.get(j.job_id, j) for j in jobs] + additions
    validate_graph(result)
    for old, new in zip(jobs, result):
        if old.action == Action.TRAIN_UNTIL_STEP or old.status == JobStatus.RUNNING:
            if old != new:
                raise ValueError('Changed active job or training command: ' + old.job_id)
    return result, receipt


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--plan-dir', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--reference-prefix', default='dfm14-xl-step_3450000-')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--defer-first-to', help='Supplement the finished first checkpoint at this later training boundary')
    args = parser.parse_args()
    plan = args.plan_dir.resolve()
    assets = json.loads(args.assets.read_text())
    if hashlib.sha256(args.snapshot.read_bytes()).hexdigest() != assets['snapshot_sha256']:
        raise ValueError('Reference snapshot differs from verified assets')
    for path in assets['mappings'].values():
        if not Path(path).is_file():
            raise FileNotFoundError(path)
    reference = load_reference(args.snapshot, args.reference_prefix)
    store = SQLiteJobStore(plan_database(plan / 'plan.tsv'))
    if args.apply:
        if store.get_admin_lock():
            raise RuntimeError('Administration already locked by another operator')
        store.set_admin_lock(True)
    try:
        before = store.load_jobs()
        after, receipt = build(before, reference, assets, plan, defer_first_to=args.defer_first_to)
        from eval_scheduler.database_runner import DatabaseRunner
        from eval_scheduler.shared_pool import SharedServerPool
        runner = DatabaseRunner(plan, store, list(range(8)), SharedServerPool(plan, list(range(8))))
        previous = {j.job_id: j for j in before}
        for job in after:
            if job != previous.get(job.job_id):
                runner._validate(job)
        if args.apply:
            backup = plan / 'state.before-full-parity.sqlite'
            if not backup.exists():
                store.backup(backup)
            store.import_jobs(after, preserve_runtime=True, require_admin_lock=True)
            store.export_tsv(plan / 'plan.tsv')
            store.backup(plan / 'state.backup.sqlite')
            (plan / 'full-parity-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, indent=2))
    finally:
        if args.apply:
            store.set_admin_lock(False)


if __name__ == '__main__':
    main()
