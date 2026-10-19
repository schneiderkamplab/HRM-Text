import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from schedule_hrm_v2_pilot import experiment


def test_control_runs_after_terminal_pilot_and_is_isolated():
    pilot = experiment('v2')
    control = experiment('control', (pilot.job_id,))
    assert control.deps_mode == 'terminal'
    assert control.deps == (pilot.job_id,)
    assert pilot.metadata['ckpt_path'] != control.metadata['ckpt_path']
    for job in (pilot, control):
        assert job.gpu_policy == 'all' and job.gpu_count == 8
        assert job.metadata['resume_from_tag'] == 'step_3800000'
        assert job.metadata['stop_after_step'] == 3820000
    assert 'wandb_resume=never' in pilot.metadata['command']
    assert 'wandb_resume=must' in control.metadata['command']
    assert 'wandb_run_id=dfm8-xl-from-dfm6-dfm7-epoch5-clean-full' in control.metadata['command']
    assert 'arch/net@arch=hrm_v2' in pilot.metadata['command']
    assert 'arch/net@arch=hrm' in control.metadata['command']
