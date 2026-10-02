import shlex
from unittest.mock import patch

import pytest

from scripts import resume_xxl_after_dfm12_audit as handoff
from eval_scheduler.model import Action, Job, JobStatus


def job():
    command = shlex.join(['python', 'pretrain.py'] + [f'{k}={v}' for k, v in handoff.REQUIRED.items()]
                        + ['resume_checkpoint_tag=step_650000', 'unrelated=keep'])
    return Job(job_id=handoff.JOB, action=Action.TRAIN_UNTIL_STEP, family='training', name='step_700000',
               status=JobStatus.FAILED, attempt=1, metadata={'command': command, 'stop_after_step': 700000})


def test_repair_only_resume_and_retry_state():
    old = job()
    new = handoff.repaired(old)
    assert new.status == JobStatus.PENDING and new.attempt == 0
    assert new.metadata['resume_from_tag'] == handoff.TAG
    assert 'unrelated=keep' in shlex.split(new.metadata['command'])
    handoff.validate_row(new)
    assert old.status == JobStatus.FAILED


def test_changed_settings_fail_closed():
    old = job()
    with pytest.raises(RuntimeError, match='lr'):
        handoff.repaired(old.with_updates(metadata={**old.metadata,
            'command': old.metadata['command'].replace('lr=3e-4', 'lr=1e-4')}))


def test_gpu_busy_blocks_without_starting():
    with patch.object(handoff.subprocess, 'run') as run, patch.object(handoff.subprocess, 'Popen') as popen:
        run.return_value.stdout = '12345\n'
        with pytest.raises(RuntimeError, match='Compute processes'):
            handoff.gpu_release_check()
        popen.assert_not_called()


def test_pending_row_cannot_be_reprepared():
    with pytest.raises(RuntimeError, match='failed row'):
        handoff.repaired(job().with_updates(status=JobStatus.PENDING))


def test_cpu_watcher_launch_explicitly_restores_all_gpus(tmp_path, monkeypatch):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    monkeypatch.setattr(handoff, 'PLAN', tmp_path)
    monkeypatch.setattr(handoff, 'EVIDENCE', evidence)
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '')
    prepared = handoff.repaired(job())
    stop = tmp_path / 'stop.request'
    stop.write_text('audit pause')
    handoff.write_json(evidence / 'prepared.json', {
        'checkpoint': {}, 'metadata_hash': handoff.digest(prepared.metadata),
        'log_dir': prepared.log_dir, 'stop_sha256': handoff.file_hash(stop)})
    with (
        patch.object(handoff, 'no_active_scheduler_or_training'),
        patch.object(handoff, 'checkpoint_evidence', return_value={}),
        patch.object(handoff, 'gpu_release_check', return_value={i: 180000 for i in range(8)}),
        patch.object(handoff, 'read_plan', return_value=[prepared]),
        patch.object(handoff, 'dependencies'),
        patch.object(handoff.subprocess, 'run') as run,
        patch.object(handoff.subprocess, 'Popen') as popen,
    ):
        popen.return_value.pid = 12345
        handoff.start_after_gpu_release()
        popen.assert_called_once()
        env = popen.call_args.kwargs['env']
        assert env['CUDA_VISIBLE_DEVICES'] == '0,1,2,3,4,5,6,7'
        assert env['PATH'].startswith('/home/ucloud/miniforge3/envs/hrm/bin:')
        assert run.call_args.kwargs['env'] == env
        assert handoff.os.environ['CUDA_VISIBLE_DEVICES'] == ''
