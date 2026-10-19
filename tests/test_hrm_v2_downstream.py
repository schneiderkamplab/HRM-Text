"""Matched native comparisons retain task identity without stale dependencies."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'eval_scheduler'))
from eval_scheduler.model import Action, Job, JobStatus
import schedule_hrm_v2_downstream as schedule


def test_matched_plan_keeps_scoring_and_rebinds_publication_dependencies(tmp_path, monkeypatch):
    monkeypatch.setattr(schedule, 'CHILD', tmp_path)
    monkeypatch.setattr(schedule, 'snapshot', lambda mode: (tmp_path/mode, 11.913))
    monkeypatch.setattr(schedule, 'standard_config', lambda: tmp_path/'standard.yaml')
    base = dict(eval_step=1150000, log_root='logs/eval/old/step_1150000',
                dfm_log_root='logs/dfm_evals/old/step_1150000',
                standard_engine_backend='vllm', hrm_server_backend='vllm',
                defer_dfm_export=True, fixed_retry_batch=True, shards=1,
                judge_model='openai/unchanged', judge_server_model='judge/unchanged')
    rows = []
    for task in ('MATH','GSM8k','DROP','MMLU','ARC','HellaSwag','Winogrande','BoolQ'):
        rows.extend([
            Job(task, Action.EVAL_STANDARD, 'standard', task, deps=('export',),
                metadata=base, log_dir=base['log_root']+'/standard_shards/'+task),
            Job(task+'-merge', Action.MERGE_STANDARD, 'standard', task, deps=(task,), metadata=base)])
    for task in schedule.DFM_TASKS:
        rows.extend([
            Job(task+'-inference', Action.EVAL_DFM, 'dfm', task, deps=('export',), metadata=base,
                log_dir=base['dfm_log_root']+'/'+task+'/shard_0_of_1/step_1150000'),
            Job(task+'-merge', Action.MERGE_DFM, 'dfm', task, deps=(task,), metadata=base)])
    prepared, epochs = schedule.build(rows)
    ids = {j.job_id for j in prepared}
    assert len(ids) == len(prepared) == len(rows)*2
    assert epochs == {'v2':11.913, 'control':11.913}
    for j in prepared:
        assert set(j.deps) <= ids
        assert j.status == JobStatus.PENDING and j.attempt == 0
        assert j.metadata['standard_engine_backend'] == 'simple'
        assert j.metadata['hrm_server_backend'] == 'simple'
        assert j.metadata['eval_step'] == 3820000 and j.metadata['no_ema'] is False
        assert j.metadata['judge_model'] == 'openai/unchanged'
        assert not j.metadata.get('fixed_retry_batch')
        if j.action in schedule.MERGES:
            assert len(j.deps) == 1
        else:
            assert j.deps == ()
            assert 'old/step_1150000' not in j.log_dir
    assert {j.metadata['wandb_run_id'] for j in prepared} == {schedule.RUN,'hrm-v2-XL-from-3800000'}
