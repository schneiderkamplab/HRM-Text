from pathlib import Path
import subprocess
import sys

import pytest
from scripts import prepare_dfm14_xl_handoff as p
from scripts import schedule_dfm14_xl_handoff as h


def job(name, action, step=h.START, **kwargs):
    return h.Job(job_id=name, action=action, family='test', name=name,
                 metadata={'xl_boundary': step}, **kwargs)


def fixture():
    return [job('train3250', h.Action.TRAIN_UNTIL_STEP, status=h.JobStatus.RUNNING),
            job('wait', h.Action.WAIT_CHECKPOINT, deps=('train3250',)),
            job('export', h.Action.EXPORT_HF, deps=('wait',)),
            job('eval', h.Action.EVAL_DFM, deps=('export',)),
            job('new16-eval', h.Action.EVAL_DFM, deps=('export',)),
            job('average50', h.Action.AVERAGE, deps=('eval', 'new16-eval')),
            job('barrier', h.Action.TERMINAL_BARRIER, deps=('eval', 'new16-eval'), deps_mode='terminal'),
            job('teardown', h.Action.TEARDOWN_EVAL, deps=('barrier',)),
            job('old3300', h.Action.TRAIN_UNTIL_STEP, step=3300000, deps=('average50', 'teardown'))]


def run():
    return {'end_step': 3350001, 'eval_steps': [3300000, 3350000, 3350001]}


def test_gate_preserves_current_and_requires_every_current_eval():
    jobs = fixture(); armed = h.arm_rows(jobs)
    assert armed[:8] == jobs[:8]
    assert h.GATE in armed[8].deps
    assert set(armed[-1].deps) == {j.job_id for j in jobs[:8]}


def test_clone_new_language_coverage_and_final_boundary():
    jobs = h.arm_rows(fixture()); out, retired, generated = h.build(jobs, run())
    assert next(j for j in out if j.job_id == 'train3250') == jobs[0]
    assert next(j for j in out if j.job_id == 'old3300').status == h.JobStatus.SKIPPED
    trains = [j for j in generated if j.action == h.Action.TRAIN_UNTIL_STEP]
    assert len(trains) == 3
    assert trains[-1].metadata['stop_after_step'] == 3350002
    assert trains[-1].metadata['completion_checkpoint_tag'] == 'epoch_1'
    assert sum('average50' in j.job_id for j in generated) == 3
    assert sum('new16-eval' in j.job_id for j in generated) == 3
    for t in trains[1:]:
        assert any('average50' in d for d in t.deps)
    for j in generated:
        if j.action == h.Action.TERMINAL_BARRIER:
            assert j.deps_mode == 'terminal'
    h.check_graph(out)


def test_preserve_done_cleanup_but_fresh_successor_cleanup():
    jobs = fixture() + [job('old-done-cleanup', h.Action.TEARDOWN_EVAL, step=3300000,
                           deps=('old3300',), status=h.JobStatus.DONE)]
    armed = h.arm_rows(jobs); out, _, _ = h.build(armed, run())
    assert next(j for j in out if j.job_id == 'old-done-cleanup') == jobs[-1]


@pytest.mark.parametrize('status,attempt', [(h.JobStatus.RUNNING, 0), (h.JobStatus.DONE, 1),
                                         (h.JobStatus.PENDING, 1), (h.JobStatus.FAILED, 1)])
def test_no_raced_future(status, attempt):
    jobs = fixture(); jobs[-1] = jobs[-1].with_updates(status=status, attempt=attempt)
    with pytest.raises(ValueError, match='already attempted'):
        h.arm_rows(jobs)


def test_no_live_plan_writes_preview_build(tmp_path):
    plan = tmp_path / 'plan'; plan.mkdir()
    jobs = fixture(); h.write_plan(plan / 'plan.tsv', jobs)
    h.build(h.arm_rows(jobs), run(), plan=plan, control=tmp_path / 'control')
    assert h.read_plan(plan / 'plan.tsv') == jobs


def test_lr_and_hydra_actual_arguments():
    from hydra import compose, initialize_config_dir
    args = h.training_arguments(run(), ['stop_after_step=3300000',
                  'resume_checkpoint_tag=step_3250000', f'resume_checkpoint_path={h.SOURCE}'])
    assert 'data=dfm14' in args and 'data=dfm13' not in args
    with initialize_config_dir(version_base=None, config_dir=str(h.ROOT / 'config')):
        c = compose(config_name='cfg_pretrain', overrides=args[3:])
    assert c.lr == 3e-4 and c.lr_auto and c.lr_min_ratio == 1
    assert c.lr_warmup_steps == c.lr_rewarm_steps == 0
    assert c.lr_decay_start_step is c.lr_decay_end_step is c.lr_cooldown_checkpoint is None
    assert c.epochs == 1 and c.data.path == str(p.SAMPLE) and c.data.target_only
    assert c.gradient_accumulation_steps == 2 and c.global_batch_size == 262144
    assert not c.reset_ema_on_resume
    assert c.wandb_run_id == p.RUN and c.checkpoint_path == str(p.OUTPUT)
    assert c.arch.bp_warmup_ratio == 0


def test_exact_reset_preserves_optimizer_step_and_original():
    original = dict(step=h.START, epoch=1, batch_in_epoch=456, carry_policy='none',
                    world_size=8, gradient_accumulation_steps=2, lr_rewarm={'steps': 123},
                    global_row_cursor_in_epoch=123, optimizer_marker='unchanged')
    new = h.reset_state(original)
    assert new['step'] == original['step'] and new['epoch'] == 1
    assert new['batch_in_epoch'] == new['global_row_cursor_in_epoch'] == 0
    assert new['optimizer_marker'] == 'unchanged' and 'lr_rewarm' not in new
    assert original['global_row_cursor_in_epoch'] == 123
    with pytest.raises(ValueError):
        h.reset_state({**original, 'step': h.START - 1})


def test_actual_parent_fraction_and_final():
    assert h.display_epoch(10.8123, {'global_row_cursor_in_epoch': 25}, 100) == pytest.approx(11.0623)
    assert h.display_epoch(10.8123, {'global_row_cursor_in_epoch': 99}, 100, True) == pytest.approx(11.8123)
    with pytest.raises(ValueError):
        h.display_epoch(10.8, {'global_row_cursor_in_epoch': 101}, 100)


def test_no_receipt_no_readiness(tmp_path):
    assert p.sample_contract(tmp_path) is None


def test_budget_not_token_estimate():
    budget = {'optimizer_steps': 60001, 'packed_rows': p.ROWS}
    r = p.proposal({'epoch_tokens': p.EXPECTED[0]}, budget)
    assert r['end_step'] == 3310001 and r['eval_steps'] == [3300000, 3310001]
    assert r['dataset_epoch_index'] == 0 and r['dataset_passes'] == 1
    assert r['lr']['decay_end_step'] is None


def test_inherited_stale_pin_blocks_install(tmp_path):
    path = tmp_path / 'module'; path.write_text('current')
    j = fixture()[3].with_updates(metadata={'source_pins': {str(path): 'old'}})
    with pytest.raises(ValueError, match='Inherited evaluation pin drift'):
        h.validate_eval_pins([j])
    h.validate_eval_pins([j.with_updates(metadata={'source_pins': {str(path): h.file_hash(path)}})])


def test_parent_extension_is_required_before_live_changes():
    with pytest.raises(ValueError, match='not fully installed'):
        h.validate_extension(fixture())
    meta = {'xl_boundary': h.START, 'dfm14_eval_50_languages': True}
    rows = [job(f'task-{n}-{shard}', h.Action.EVAL_DFM).with_updates(
            name=f'task-{n}', shard=shard, shards=4, metadata=meta)
            for n in range(32) for shard in range(4)]
    rows.append(job('average50', h.Action.AVERAGE).with_updates(metadata=meta))
    h.validate_extension(rows)
    with pytest.raises(ValueError):
        h.validate_extension(rows[1:])


def test_full_extension_survives_every_boundary_including_final():
    jobs = fixture()
    meta = {'xl_boundary': h.START, 'dfm14_eval_50_languages': True,
            'dfm_log_root': f'logs/dfm_evals/dfm14_extension/step_{h.START}'}
    tasks = [job(f'new-{n}-{shard}', h.Action.EVAL_DFM, deps=('export',)).with_updates(
             name=f'new-{n}', shard=shard, shards=4, metadata=meta)
             for n in range(32) for shard in range(4)]
    avg = job('new-average50', h.Action.AVERAGE,
              deps=tuple(j.job_id for j in tasks) + ('average50',)).with_updates(metadata=meta)
    jobs += [*tasks, avg]
    h.validate_extension(jobs)
    out, _, generated = h.build(h.arm_rows(jobs), run())
    for step in run()['eval_steps']:
        block = [j for j in generated if h.boundary(j) == step and j.metadata.get('dfm14_eval_50_languages')]
        assert len([j for j in block if j.action == h.Action.EVAL_DFM]) == 128
        assert len([j for j in block if j.action == h.Action.AVERAGE]) == 1
        tag = 'epoch_1' if step == run()['end_step'] else f'step_{step}'
        assert all(j.metadata['dfm_log_root'].endswith('/' + tag) for j in block)
    h.check_graph(out)


def test_scheduler_watcher_waits_existing_cpu_owner(tmp_path, monkeypatch):
    import os
    command = Path(f'/proc/{os.getpid()}/cmdline').read_bytes().split(b'\0')[:-1]
    h.write_json(tmp_path / 'prepare-launch.json', {'pid': os.getpid(),
                 'command': [x.decode() for x in command]})
    def publish(_seconds):
        h.write_json(tmp_path / 'prepared.json', {'ready': True})
    monkeypatch.setattr(h.time, 'sleep', publish)
    monkeypatch.setattr(h.prep, 'prepare', lambda *a, **kw: pytest.fail('Must not compete for prepare lock'))
    h.wait_prepared(tmp_path)
    assert h.load(tmp_path / 'scheduler-progress.json')['pid'] == os.getpid()


def test_scheduler_watcher_detects_dead_owner(tmp_path):
    h.write_json(tmp_path / 'prepare-launch.json', {'pid': 999999999, 'command': ['missing']})
    with pytest.raises(ValueError, match='owner exited'):
        h.wait_prepared(tmp_path)


def test_final_cleanup_is_fresh_and_failure_safe():
    from eval_scheduler.runtime import dependencies_satisfied
    jobs = fixture()
    jobs = [j.with_updates(status=h.JobStatus.DONE)
            if j.action in (h.Action.TERMINAL_BARRIER, h.Action.TEARDOWN_EVAL) else j for j in jobs]
    out, _, generated = h.build(h.arm_rows(jobs), run())
    final = [j for j in generated if h.boundary(j) == run()['end_step']]
    barrier = next(j for j in final if j.action == h.Action.TERMINAL_BARRIER)
    teardown = next(j for j in final if j.action == h.Action.TEARDOWN_EVAL)
    assert barrier.status == teardown.status == h.JobStatus.PENDING
    assert all(d.startswith('dfm14-xl-epoch_1-') for d in barrier.deps)
    assert not dependencies_satisfied(barrier, out)
    failed = barrier.deps[0]
    terminal = [j.with_updates(status=h.JobStatus.FAILED if j.job_id == failed else h.JobStatus.DONE)
                if j.job_id in barrier.deps else j for j in out]
    assert dependencies_satisfied(barrier, terminal)
    terminal = [j.with_updates(status=h.JobStatus.DONE) if j.job_id == barrier.job_id else j for j in terminal]
    assert dependencies_satisfied(teardown, terminal)
    average = next(j for j in final if j.action == h.Action.AVERAGE)
    assert not dependencies_satisfied(average, terminal)


@pytest.mark.parametrize('script', [h.__file__, p.__file__])
def test_actual_cli_imports(script):
    result = subprocess.run([sys.executable, script, '--help'], cwd=h.ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
