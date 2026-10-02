"""Prepare the existing scheduler's final identity EMA suite, co-resident."""
import copy
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
sys.path.insert(0, str(ROOT))
from dfm12.io import file_hash, load, write_json
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import Action, JobStatus, read_plan, write_plan
from scripts.stop_training_at_complete_checkpoint import complete

SOURCE = ROOT / 'logs/scheduler/dfm12_XL_identity_step2881261_ema_full_20260926'
PLAN = ROOT / 'logs/scheduler/dfm12_XL_identity_step2897261_ema_full_20260928'
CHECKPOINT = ROOT / 'checkpoints/dfm12/XL-identity-after-gas-probe-from-step2888200'
EXPORT = ROOT / 'exports/dfm12_XL_identity_step2897261_ema_hf_training_tokenizer'
TAG = 'step_2897261'
CPU_ACTIONS = {Action.MERGE_STANDARD, Action.MERGE_DFM, Action.MERGE_IFEVAL, Action.AVERAGE}


def canonical_log_dir(job):
    """Keep evaluation writers and scheduler merge readers on the same layout."""
    meta = job.metadata
    if job.action in {Action.EVAL_STANDARD, Action.MERGE_STANDARD}:
        return Path(meta['log_root']) / 'standard_shards' / job.name
    if job.action == Action.EVAL_DFM:
        return Path(meta['dfm_log_root']) / job.name / f'shard_{job.shard}_of_{job.shards}' / meta['ckpt_tag']
    if job.action == Action.MERGE_DFM:
        return Path(meta['dfm_log_root']) / job.name
    if job.action == Action.EVAL_DFM_IFEVAL:
        return Path(meta['dfm_log_root']) / f'ifeval_shard_{job.shard}' / meta['ckpt_tag']
    if job.action == Action.MERGE_IFEVAL:
        return Path(meta['dfm_log_root'])
    if job.action in {Action.EVAL_EUROEVAL, Action.EVAL_EUROEVAL_BATCHED_IFEVAL}:
        return Path(meta['euroeval_log_root']) / meta['ckpt_tag'] / job.name
    return Path(job.log_dir)


def repair_existing():
    """Restore archive aliases, preserving all raw outputs and successful jobs."""
    with PlanLock(PLAN):
        jobs = read_plan(PLAN / 'plan.tsv')
        if any(j.status == JobStatus.RUNNING for j in jobs):
            raise ValueError('Refuse repair while scheduler jobs are running')
        if any(j.status in {JobStatus.PENDING, JobStatus.FAILED} and j.action not in CPU_ACTIONS for j in jobs):
            raise ValueError('Non-CPU work requires separate authorization')
        links, updates, resets = [], [], []
        for job in jobs:
            if (job.metadata['ckpt_tag'] != TAG or job.metadata['wandb_project'] != 'DFM5'
                    or job.metadata['wandb_run_id'] != 'dfm12-xl-identity-da-en-1000'
                    or job.metadata['eval_epoch'] != 10.050795912217435):
                raise ValueError('Unexpected checkpoint/W&B binding')
            dest, old = canonical_log_dir(job), Path(job.log_dir)
            if job.status == JobStatus.DONE and job.action == Action.EVAL_STANDARD:
                name = f'{job.name}_shard_{job.shard}_of_{job.shards}.log'
                source = old / name
                from scripts.merge_standard_eval_shards import parse_metrics
                parse_metrics(source, job.name)
                links.append((dest / name, source))
            elif job.status == JobStatus.DONE and job.action in {Action.EVAL_DFM, Action.EVAL_DFM_IFEVAL}:
                archives = list((old / 'inspect').glob('*.eval'))
                if len(archives) != 1:
                    raise ValueError(f'Require one archive for {job.job_id}: {archives}')
                links.append((dest, old))
            elif job.status == JobStatus.DONE and job.action in {Action.EVAL_EUROEVAL, Action.EVAL_EUROEVAL_BATCHED_IFEVAL}:
                if not (old / 'merged_metrics.json').is_file():
                    raise ValueError(f'Missing completed EuroEval metrics: {job.job_id}')
                links.append((dest, old))
            meta = dict(job.metadata)
            if dest != old:
                meta.setdefault('original_job_log_dir', str(old))
            if job.action == Action.AVERAGE:
                meta.update(atomic_v3_averages=True, average_prefix='headline_avg_v3')
            if job.status == JobStatus.FAILED:
                resets.append(job.job_id)
                meta['archive_repair_previous_attempt'] = job.attempt
                job = job.with_updates(status=JobStatus.PENDING, attempt=0)
            updates.append(job.with_updates(log_dir=str(dest), metadata=meta))
        for dest, source in links:
            if dest == source:
                continue
            if dest.exists() or dest.is_symlink():
                if dest.resolve() != source.resolve():
                    raise ValueError(f'Conflicting archive path: {dest}')
        backup = PLAN / 'plan.before-archive-repair.tsv'
        if not backup.exists():
            write_plan(backup, jobs)
        for dest, source in links:
            if dest != source and not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.symlink_to(source.resolve(), target_is_directory=source.is_dir())
        write_plan(PLAN / 'plan.tsv', updates)
        write_json(PLAN / 'archive-repair.json', dict(reset_job_ids=resets,
            aliases=[dict(path=str(d), source=str(s)) for d,s in links],
            epoch=10.050795912217435, step=2897261, gpu_reruns=0,
            plan_sha256=file_hash(PLAN / 'plan.tsv'), original_plan_sha256=file_hash(backup)))
    print(json.dumps(dict(reset_merges=len(resets), archive_aliases=len(links))))


def run_cpu_recovery():
    from eval_scheduler.runtime import Runner
    jobs = read_plan(PLAN / 'plan.tsv')
    if any(j.status in {JobStatus.PENDING, JobStatus.RUNNING, JobStatus.FAILED}
           and j.action not in CPU_ACTIONS for j in jobs):
        raise ValueError('Refuse non-CPU recovery')
    # No server pool and no GPU slots: never adopt or shut down existing servers.
    Runner(PLAN, gpus=[], persistent_vllm=False).run()


def prepare_serial_replay():
    """Replay all CPU writers serially and expose EuroEval to recursive globbing."""
    with PlanLock(PLAN):
        jobs = read_plan(PLAN / 'plan.tsv')
        if any(j.status == JobStatus.RUNNING for j in jobs):
            raise ValueError('Refuse replay preparation while jobs are running')
        if any(j.status in {JobStatus.PENDING, JobStatus.FAILED}
               and j.action not in CPU_ACTIONS for j in jobs):
            raise ValueError('Non-CPU work requires separate authorization')
        for job in jobs:
            if job.action not in {Action.EVAL_EUROEVAL, Action.EVAL_EUROEVAL_BATCHED_IFEVAL}:
                continue
            if job.status != JobStatus.DONE:
                continue
            dest = canonical_log_dir(job)
            if dest.is_symlink():
                source = dest.resolve()
                if not (source / 'merged_metrics.json').is_file():
                    raise ValueError(f'Missing EuroEval metrics: {source}')
                # Remove only our alias, never its original archive target.
                dest.unlink()
                dest.mkdir()
                for child in source.iterdir():
                    (dest / child.name).symlink_to(child, target_is_directory=child.is_dir())
        updated = serial_cpu_jobs(jobs)
        write_plan(PLAN / 'plan.before-serial-replay.tsv', jobs)
        write_plan(PLAN / 'plan.tsv', updated)


def serial_cpu_jobs(jobs):
    """Keep original dependencies and add a total order across shared-run writers."""
    writers = [j for j in jobs if j.action in CPU_ACTIONS and j.status != JobStatus.SKIPPED]
    writers.sort(key=lambda j: j.action == Action.AVERAGE)
    replacements = {}
    previous = None
    for job in writers:
        deps = tuple(dict.fromkeys((*job.deps, *((previous,) if previous else ()))))
        replacements[job.job_id] = job.with_updates(deps=deps, status=JobStatus.PENDING, attempt=0)
        previous = job.job_id
    return [replacements.get(j.job_id, j) for j in jobs]


def validate_tokenizer():
    from tokenizers import Tokenizer
    from transformers import AutoTokenizer

    raw_path = ROOT / 'data/dfm11_tokenizer/tokenizer.json'
    assert (EXPORT / 'model.safetensors').is_file()
    assert (EXPORT / 'tokenizer.json').read_bytes() == raw_path.read_bytes()
    config = load(EXPORT / 'tokenizer_config.json')
    config['fix_mistral_regex'] = False
    write_json(EXPORT / 'tokenizer_config.json', config)
    tokenizer = AutoTokenizer.from_pretrained(EXPORT, local_files_only=True)
    raw = Tokenizer.from_file(str(raw_path))
    assert json.loads(tokenizer.backend_tokenizer.to_str())['pre_tokenizer'] == json.loads(raw.to_str())['pre_tokenizer']
    assert tokenizer.chat_template == (ROOT / 'data/dfm11_tokenizer/chat_template.jinja').read_text()
    samples = ['Hello, world!\nNext line.', 'Dansk: et svar, og en forklaring.',
               'def f(x):\n    return x + 1', '\\boxed{42}',
               '{"name":"search","arguments":{"q":"test"}}']
    samples += [tokenizer.apply_chat_template([{'role':'user','content':text}],
        tokenize=False, add_generation_prompt=True, enable_thinking=False) for text in samples.copy()]
    for text in samples:
        assert raw.encode(text, add_special_tokens=False).ids == tokenizer.encode(text, add_special_tokens=False)
    return dict(export=str(EXPORT), raw_tokenizer_sha256=file_hash(raw_path),
                parity_samples=len(samples), fix_mistral_regex=False,
                ema=True, checkpoint=str(CHECKPOINT), tag=TAG)


def main():
    assert complete(CHECKPOINT, TAG), 'Final checkpoint incomplete'
    assert not (PLAN / 'plan.tsv').exists(), 'Refuse to overwrite an existing plan'
    source_hash = file_hash(SOURCE / 'plan.tsv')
    source = read_plan(SOURCE / 'plan.tsv')
    assert len(source) == 290
    assert not any(job.action == Action.TRAIN_UNTIL_STEP for job in source)
    validation = validate_tokenizer()
    mapping = {j.job_id:j.job_id.replace('identity-4000-ema-full-', 'identity-20000-ema-full-') for j in source}
    old_checkpoint = str(ROOT / 'checkpoints/dfm12/XL-identity-expanded-from-step2880261')
    old_export = str(ROOT / 'exports/dfm12_XL_identity_step2881261_ema_hf_training_tokenizer')
    jobs = []
    for original in source:
        job = original.with_updates(
            job_id=mapping[original.job_id], deps=tuple(mapping[d] for d in original.deps),
            name=original.name.replace('step_2881261', TAG),
            log_dir=str(PLAN / 'jobs' / mapping[original.job_id]),
            status=JobStatus.SKIPPED if original.status == JobStatus.SKIPPED else JobStatus.PENDING,
            attempt=0, metadata=copy.deepcopy(original.metadata))
        meta = job.metadata
        for key, value in list(meta.items()):
            if isinstance(value, str):
                meta[key] = (value.replace(str(SOURCE), str(PLAN))
                    .replace(old_checkpoint, str(CHECKPOINT)).replace(old_export, str(EXPORT))
                    .replace('step_2881261', TAG).replace('4000-EMA', '20000-EMA'))
        # Keep the historical identity x-axis: token-equivalent continuation
        # after the completed DFM11 epoch10, not the packed-data internal epoch.
        meta.update(eval_epoch=10 + 20000 * 262144 / 103214604702,
                    vllm_gpu_memory_utilization=0.45, min_gpu_free_mib=90000,
                    port_base=52000, fixed_retry_batch=False, no_ema=False)
        if job.name == 'generative_talemaader' and job.requires_gpu:
            meta.update(vllm_gpu_memory_utilization=0.30, min_gpu_free_mib=93000)
        if job.action == Action.EXPORT_HF:
            meta['min_gpu_free_mib'] = 0
        assert meta['wandb_project'] == 'DFM5'
        assert meta['wandb_run_id'] == 'dfm12-xl-identity-da-en-1000'
        assert meta['fix_mistral_regex'] is False
        assert 0 < meta['vllm_gpu_memory_utilization'] <= .5
        jobs.append(job.with_updates(log_dir=str(canonical_log_dir(job))))
    ids = {job.job_id for job in jobs}
    assert len(ids) == len(jobs) and all(set(j.deps) <= ids for j in jobs)
    assert all('2881261' not in json.dumps(j.metadata) for j in jobs)
    PLAN.mkdir(parents=True, exist_ok=True)
    with PlanLock(PLAN):
        write_plan(PLAN / 'plan.tsv', jobs)
        write_json(PLAN / 'export-validation.json', validation)
        write_json(PLAN / 'preflight.json', dict(source_plan=str(SOURCE),
            source_sha256=source_hash, rows=len(jobs),
            pending=sum(j.status == JobStatus.PENDING for j in jobs),
            skipped=[{'action':j.action.value,'name':j.name} for j in jobs if j.status == JobStatus.SKIPPED],
            eval_epoch=jobs[0].metadata['eval_epoch'], no_training=True,
            shared_server_ports_untouched=list(range(8600,8608)),
            max_vllm_utilization=.45, judged_vllm_utilization=.30))
    assert file_hash(SOURCE / 'plan.tsv') == source_hash
    print(PLAN)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--repair-existing', action='store_true')
    parser.add_argument('--run-cpu-recovery', action='store_true')
    parser.add_argument('--prepare-serial-replay', action='store_true')
    args = parser.parse_args()
    if args.repair_existing:
        repair_existing()
    if args.prepare_serial_replay:
        prepare_serial_replay()
    if args.run_cpu_recovery:
        run_cpu_recovery()
    if not args.repair_existing and not args.run_cpu_recovery and not args.prepare_serial_replay:
        main()
