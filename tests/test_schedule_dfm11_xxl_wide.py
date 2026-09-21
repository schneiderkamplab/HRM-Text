import importlib.util
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location('wide_campaign', Path(__file__).resolve().parents[1] / 'scripts/schedule_dfm11_xxl_wide.py')
campaign = importlib.util.module_from_spec(spec)
spec.loader.exec_module(campaign)
from eval_scheduler.model import Job as SchedulerJob, JobStatus, Action


def Job(**kwargs):
    return SchedulerJob(family='test', name='test', **kwargs)


def test_final_epoch_skips_unreachable_and_releases_final_eval(tmp_path, monkeypatch):
    prefix = campaign.PREFIX
    jobs = [Job(job_id=prefix+'train-750000', action=Action.TRAIN_UNTIL_STEP,
                status=JobStatus.RUNNING, metadata={'ckpt_tag': 'step_750000'}),
            Job(job_id=prefix+'eval-750000', action=Action.WAIT_CHECKPOINT,
                metadata={'dfm11_boundary': 750000}),
            Job(job_id=prefix+'train-800000', action=Action.TRAIN_UNTIL_STEP,
                metadata={'dfm11_boundary': 800000}),
            Job(job_id=prefix+'epoch_2-'+campaign.WAIT, action=Action.WAIT_CHECKPOINT)]
    campaign.write_plan(tmp_path/'plan.tsv', jobs)
    monkeypatch.setattr(campaign, 'checkpoint_ready', lambda j: (j.metadata.get('ckpt_tag') == 'epoch_2', ''))
    campaign.finalize(tmp_path, 750000)
    result = campaign.read_plan(tmp_path/'plan.tsv')
    assert result[1].status == result[2].status == JobStatus.SKIPPED
    assert result[3].deps == (prefix+'train-750000',)


def test_fractional_epoch_before_eval_release(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(campaign, 'ROOT', tmp_path)
    ckpt = tmp_path/campaign.CKPT
    ckpt.mkdir(parents=True)
    (ckpt/'checkpoint_state_step_400000.json').write_text(json.dumps({'global_row_cursor_in_epoch': 25}))
    data = tmp_path/'data/sampled_dfm11/epoch_1'
    data.mkdir(parents=True)
    np.save(data/'inst_start.npy', np.arange(100))
    jobs = [Job(job_id=campaign.PREFIX+'train-400000', action=Action.TRAIN_UNTIL_STEP,
                status=JobStatus.RUNNING, metadata={'ckpt_tag': 'step_400000'}),
            Job(job_id=campaign.PREFIX+'eval-400000', action=Action.WAIT_CHECKPOINT,
                metadata={'dfm11_boundary': 400000})]
    campaign.write_plan(tmp_path/'plan.tsv', jobs)
    monkeypatch.setattr(campaign, 'checkpoint_ready', lambda j: (j.metadata.get('ckpt_tag') == 'step_400000', ''))
    campaign.finalize(tmp_path, 400000)
    assert campaign.read_plan(tmp_path/'plan.tsv')[1].metadata['eval_epoch'] == 1.25
