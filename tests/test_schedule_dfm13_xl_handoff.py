from pathlib import Path
import pytest
from scripts import schedule_dfm13_xl_handoff as h


def job(name, action=h.Action.WAIT_CHECKPOINT, step=h.START, **kw):
    return h.Job(job_id=name, action=action, family='test',name=name,
                 metadata=dict(xl_boundary=step),**kw)


def template():
    return [job('train',h.Action.TRAIN_UNTIL_STEP,status=h.JobStatus.RUNNING),
            job('wait',deps=('train',)),job('export',h.Action.EXPORT_HF,deps=('wait',)),
            job('average',h.Action.AVERAGE,deps=('export',)),
            job('teardown',h.Action.TEARDOWN_EVAL,deps=('export',)),
            job('future',h.Action.TRAIN_UNTIL_STEP,step=h.START+50000,deps=('teardown',))]


def test_retire_preserves_current_and_eval():
    before=template(); kept,removed=h.retire_future(before)
    assert kept==before[:-1] and removed==before[-1:]
    assert kept[0].status==h.JobStatus.RUNNING


def test_no_retiring_attempted_training():
    rows=template();rows[-1]=rows[-1].with_updates(status=h.JobStatus.RUNNING)
    with pytest.raises(ValueError,match='already attempted'):h.retire_future(rows)


def test_real_checkpoint_readiness_gate_keeps_runner_waiting(tmp_path):
    plan=tmp_path/'plan';plan.mkdir();control=tmp_path/'control'
    h.write_plan(plan/'plan.tsv',template())
    h.arm(plan,control);h.readiness_gate(plan,control)
    rows=h.read_plan(plan/'plan.tsv');gate=next(j for j in rows if j.job_id==h.GATE)
    assert gate.action==h.Action.WAIT_CHECKPOINT
    assert gate.metadata['ckpt_path']==str(control/'resume')
    assert 'average' in gate.deps and 'teardown' in gate.deps
    assert gate.metadata['checkpoint_wait_max_seconds']==0
    new=h.build(rows,dict(end_step=h.START+100000))
    assert gate.job_id in new[0].deps
    h.readiness_gate(plan,control)
    assert h.read_plan(plan/'plan.tsv')==rows


def test_arm_backup_idempotent(tmp_path):
    plan=tmp_path/'plan';plan.mkdir();control=tmp_path/'control'
    h.write_plan(plan/'plan.tsv',template())
    receipt=h.arm(plan,control)
    assert receipt['removed_ids']==['future']
    assert h.read_plan(control/'plan-before-handoff.tsv')==template()
    assert h.arm(plan,control)==receipt
    assert h.read_plan(plan/'plan.tsv')==template()[:-1]


def test_successor_waits_all_averages():
    run=dict(end_step=h.START+100001)
    jobs=template()[:-1];new=h.build(jobs,run)
    trains=[j for j in new if j.action==h.Action.TRAIN_UNTIL_STEP]
    assert set(trains[0].deps)=={j.job_id for j in jobs}
    assert all(j.deps_mode=='success' for j in trains)
    assert len(trains)==3
    assert trains[-1].metadata['stop_after_step']==run['end_step']+1
    assert trains[-1].metadata['ckpt_tag']==f"step_{run['end_step']+1}"
    assert trains[-1].metadata['completion_checkpoint_tag']=='epoch_1'


def state():
    return dict(step=h.START,carry_policy='none',world_size=8,gradient_accumulation_steps=2,
                epoch=11,batch_in_epoch=123,global_row_cursor_in_epoch=999,lr_rewarm={'steps':1000})


def test_cursor_reset_not_source_mutation():
    original=state(); result=h.reset_state(original,Path('/sample'))
    assert original==state()
    assert result['epoch']==1 and result['step']==h.START
    assert result['batch_in_epoch']==result['global_row_cursor_in_epoch']==0
    assert result['batch_in_epoch_exact'] is True
    assert 'lr_rewarm' not in result


def test_carry_failclosed():
    original=state();original['carry_policy']='per_rank'
    with pytest.raises(ValueError):h.reset_state(original,Path('/sample'))


def test_training_config_continuity():
    args=h.training_arguments(dict(end_step=4000000),[
        'stop_after_step=3200000',f'resume_checkpoint_path={h.CONTROL}/resume',
        'resume_checkpoint_tag=step_3150000'])
    settings=dict(x.split('=',1) for x in args if '=' in x)
    assert settings['epochs']=='1'
    assert settings['data']=='dfm13'
    assert settings['data.path']==str(h.prep.SAMPLE)
    assert settings['arch.bp_max_steps']=='8' and settings['arch.bp_warmup_ratio']=='0'
    assert settings['lr']=='3e-4' and settings['lr_auto']=='true'
    assert settings['lr_decay_start_step']=='3950000'
    assert settings['lr_rewarm_steps']=='0'
    assert settings['reset_ema_on_resume']=='false'
    assert settings['gradient_accumulation_steps']=='2'
    assert settings['wandb_run_id']==h.old.RUN
    assert settings['checkpoint_step_interval']=='10000'
    assert settings['stop_after_step']=='3200000'
    assert args.count('stop_after_step=3200000')==1


def test_reject_extra_override():
    with pytest.raises(ValueError):h.training_arguments(dict(end_step=4000000),['lr=1'])


def test_display_uses_actual_row_cursors_not_step_estimate():
    assert h.display_epoch({'global_row_cursor_in_epoch':60},100,
                           {'global_row_cursor_in_epoch':25},100)==pytest.approx(10.85)
    assert h.display_epoch({'global_row_cursor_in_epoch':60},100,{},100,True)==pytest.approx(11.6)


def test_hydra_compose_cpu():
    from hydra import compose, initialize_config_dir
    args=h.training_arguments(dict(end_step=4000000),[
        'stop_after_step=3200000',f'resume_checkpoint_path={h.CONTROL}/resume',
        'resume_checkpoint_tag=step_3150000'])
    with initialize_config_dir(version_base=None,config_dir=str(h.ROOT/'config')):
        c=compose(config_name='cfg_pretrain',overrides=args[3:])
        assert c.data.target_only and c.data.path==str(h.prep.SAMPLE)
        assert c.epochs==1 and c.arch.bp_max_steps==8 and c.arch.bp_warmup_ratio==0
        assert c.lr_rewarm_steps==0 and c.lr_decay_start_step==3950000


def test_retirement_refuses_dangling_dependency():
    rows=template()+[job('unrelated',step=0,deps=('future',))]
    with pytest.raises(ValueError,match='dangling'):h.retire_future(rows)


def test_skip_is_preserved_but_not_training_requirement():
    rows=template()[:-1]+[job('intentional',h.Action.EVAL_STANDARD,status=h.JobStatus.SKIPPED)]
    new=h.build(rows,dict(end_step=h.START+100000))
    assert 'intentional' not in new[0].deps
    assert sum(j.status==h.JobStatus.SKIPPED for j in new)==2


def test_existing_resume_must_have_original_binding(tmp_path,monkeypatch):
    source=tmp_path/'source';control=tmp_path/'control';target=control/'resume'
    original=state();tag=f'step_{h.START}'
    h.write_json(source/f'checkpoint_state_{tag}.json',original)
    h.write_json(target/f'checkpoint_state_{tag}.json',h.reset_state(original,h.prep.SAMPLE))
    h.write_json(target/'handoff.json',{'source_sidecar_sha256':'wrong'})
    monkeypatch.setattr(h,'SOURCE',source)
    with pytest.raises(ValueError,match='resume view'):h.fresh_resume(control)
    assert h.load(source/f'checkpoint_state_{tag}.json')==original


def test_actual_loader_resume_epoch_zero_cursor(tmp_path):
    from types import SimpleNamespace
    from pretrain import resolve_resume_state
    tag=f'step_{h.START}'
    original=dict(state(),local_batch_size=16384)
    h.write_json(tmp_path/f'checkpoint_state_{tag}.json',h.reset_state(original,h.prep.SAMPLE))
    config=SimpleNamespace(resume_checkpoint_path=str(tmp_path),resume_checkpoint_tag=tag,
        resume_step=None,resume_epoch=None,resume_batch_in_epoch=None)
    resolved=resolve_resume_state(config,current_local_batch_size=16384)
    assert resolved.step==h.START and resolved.start_epoch==1
    assert resolved.skip_batches==0
    # A CPU world-size1 test selects the row-cursor branch; production world8
    # uses exact batch0. Both select epoch_0 and the first row.
    assert resolved.start_row_cursor in (None,0)


def test_real3150_template_graph():
    path=h.PLAN/'plan.tsv'
    if not path.exists():pytest.skip('Local production template unavailable')
    rows,_=h.retire_future(h.read_plan(path))
    rows=[j for j in rows if not j.job_id.startswith(h.PREFIX)]
    new=h.build(rows,dict(end_step=3300123))
    first=next(j for j in new if j.action==h.Action.TRAIN_UNTIL_STEP)
    averages=[j for j in rows if h.boundary(j)==h.START and j.action==h.Action.AVERAGE and j.status!=h.JobStatus.SKIPPED]
    assert len(averages)==4
    assert all(j.job_id in first.deps for j in averages)
