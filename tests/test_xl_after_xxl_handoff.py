import importlib.util
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('xl_handoff', SCRIPTS / 'resume_xl_after_xxl_1150k.py')
handoff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handoff)


def test_resume_preserves_cursor_ema_and_lr(monkeypatch):
    monkeypatch.setattr(handoff, 'resume_source', lambda: (handoff.SOURCE, 'step_3800000'))
    args = dict(arg.split('=', 1) for arg in handoff.command() if '=' in arg)
    assert args['resume_checkpoint_tag'] == 'step_3800000'
    assert args['stop_after_step'] == args['training_total_steps'] == '3850000'
    assert args['lr'] == '1e-5' and args['lr_auto'] == 'true'
    assert args['lr_min_ratio'] == '1' and args['lr_rewarm_steps'] == '0'
    assert args['reset_ema_on_resume'] == 'false'
    assert args['gradient_accumulation_steps'] == '2'
    assert args['arch.bp_max_steps'] == '8'
    assert not {'resume_step', 'resume_epoch', 'resume_batch_in_epoch'} & args.keys()
    assert args['wandb_run_id'] == 'dfm8-xl-from-dfm6-dfm7-epoch5-clean-full'


def test_control_checkpoint_is_preferred_only_when_complete(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(handoff, 'CONTROL_CHECKPOINTS', tmp_path)
    for step in (3810000, 3820000):
        (tmp_path / f'checkpoint_state_step_{step}.json').write_text(json.dumps({'step': step}))
    monkeypatch.setattr(handoff, 'complete', lambda root, tag: tag == 'step_3810000')
    assert handoff.resume_source() == (tmp_path, 'step_3810000')
    monkeypatch.setattr(handoff, 'complete', lambda *args: True)
    args = dict(a.split('=', 1) for a in handoff.command() if '=' in a)
    assert args['resume_checkpoint_tag'] == 'step_3820000'
    assert args['resume_checkpoint_path'] == str(tmp_path)
    monkeypatch.setattr(handoff, 'complete', lambda *args: False)
    assert handoff.resume_source() == (handoff.SOURCE, 'step_3800000')


def test_no_stop_before_complete_checkpoint(monkeypatch):
    monkeypatch.setattr(handoff, 'complete', lambda *args: False)
    import pytest
    with pytest.raises(RuntimeError, match='before its complete'):
        handoff.stop_xxl()


def test_eval_rewrite_preserves_unrelated_values():
    from schedule_xl_3850k_3900k import rewrite
    value = {'log_root': 'logs/dfm_evals/dfm14_XXL_wide/step_1150000',
             'judge_server_model': 'unsloth/gemma-4-E4B-it',
             'vllm_gpu_memory_utilization': 0.65}
    changed = rewrite(value, 3850000)
    assert changed['log_root'] == 'logs/dfm_evals/dfm15_XL_local/step_3850000'
    assert changed['judge_server_model'] == value['judge_server_model']
    assert changed['vllm_gpu_memory_utilization'] == 0.65
