import pytest
import runpy
from scripts import schedule_dfm13_wave34_baseline as s


def test_sync_bridge_fails_closed():
    validate=runpy.run_path(str(s.SYNC_BRIDGE))['validate']
    jobs,_=fixture()
    args=['scripts/generate_dfm5_l_eval_comparison_report.py']
    with pytest.raises(ValueError,match='not complete'):validate(jobs,args)
    jobs=[j.with_updates(status=s.JobStatus.DONE) if j.action==s.Action.TRAIN_UNTIL_STEP else j for j in jobs]
    validate(jobs,args)
    with pytest.raises(ValueError,match='Unexpected'):validate(jobs,['wrong'])


def test_existing_dispatch_uses_bridge(monkeypatch,tmp_path):
    from eval_scheduler import runtime
    jobs,r=fixture();sync=next(j for j in s.build(jobs,r,tmp_path) if j.job_id==s.SYNC_ID)
    calls=[]
    monkeypatch.setattr(runtime,'run_command',lambda argv,**kwargs:calls.append(argv) or 0)
    assert runtime.run_report(sync)==0
    assert calls==[[str(s.SYNC_BRIDGE),'scripts/generate_dfm5_l_eval_comparison_report.py']]


def test_average_does_not_inherit_export_training_wrapper(monkeypatch,tmp_path):
    from eval_scheduler import runtime
    jobs,registry=fixture()
    jobs=[j.with_updates(metadata={**j.metadata,
        'python_bin':'/scripts/resume_training.sh',
        'vllm_python':'/env/bin/python','wandb_run_name':'test'}) for j in jobs]
    calls=[]
    monkeypatch.setattr(runtime,'run_command',lambda argv,**kwargs:calls.append(argv) or 0)
    averages=[j for j in s.build(jobs,registry,tmp_path)
              if j.metadata.get(s.MARK) and j.action==s.Action.AVERAGE]
    assert len(averages)==3
    for job in averages:
        assert runtime.run_average(job)==0
    assert all(argv[:2]==['/env/bin/python','scripts/log_multilingual_headline_averages.py']
               for argv in calls)


def fixture():
    jobs=[]
    for step in (3150000,3200000,3250000):
        tag=f'step_{step}';prefix=f'old-{step}-'
        meta=dict(eval_step=step,xl_boundary=step,ckpt_tag=tag,checkpoint_tag=tag,
            wandb_run_id=s.RUN,wandb_project='DFM5',fix_mistral_regex=False,eval_epoch=11.1,
            ckpt_path='/checkpoint',dfm_log_root='/dfm/'+tag,euroeval_log_root='/euro/'+tag,log_root='/std/'+tag,
            multilingual_manifest='/legacy',command='DO NOT CHANGE',hf_export_dir='/hf/'+tag)
        status=s.JobStatus.DONE if step==3150000 else s.JobStatus.PENDING
        jobs.append(s.Job(job_id=prefix+'train',action=s.Action.TRAIN_UNTIL_STEP,name=tag,family='training',
            status=s.JobStatus.RUNNING if step==3200000 else status,metadata=meta))
        for suffix,action,deps in [('wait',s.Action.WAIT_CHECKPOINT,['train']),('export',s.Action.EXPORT_HF,['wait']),
            ('dfm',s.Action.EVAL_DFM,['export']),('merge',s.Action.MERGE_DFM,['dfm']),
            ('euro',s.Action.EVAL_EUROEVAL,['export']),('average',s.Action.AVERAGE,['merge','euro']),
            ('barrier',s.Action.TERMINAL_BARRIER,['dfm','euro']),('teardown',s.Action.TEARDOWN_EVAL,['barrier'])]:
            metadata={**meta,'dfm_suite':'dala_nl','euroeval_category':'sentiment-classification'}
            jobs.append(s.Job(job_id=prefix+suffix,action=action,name='dala_nl' if suffix in ('dfm','merge') else suffix,family=suffix,
                deps=tuple(prefix+x for x in deps),deps_mode='terminal' if suffix=='barrier' else 'success',status=status,metadata=metadata))
    registry=dict(headline_manifest='/new-populations',dfm=[dict(name='new_dala_lt',suite='dala',config='/config',language='lt',shards=2)],
        euroeval=[dict(dataset='new-lv-eval',language='lv',category='sentiment-classification')])
    return jobs,registry


def test_ordering_and_training_preservation(tmp_path):
    jobs,r=fixture();out=s.build(jobs,r,tmp_path);by={j.job_id:j for j in out}
    assert by['old-3200000-train']==next(j for j in jobs if j.job_id=='old-3200000-train')
    sync=by[s.SYNC_ID];assert sync.deps==('old-3200000-train',) and not sync.requires_gpu
    assert '--wait' in sync.metadata['command']
    baseline=[j for j in out if j.metadata.get(s.MARK) and s.boundary(j)==3150000]
    for j in baseline:
        if j.action in s.EVALS:assert s.SYNC_ID in j.deps
    average=next(j for j in baseline if j.action==s.Action.AVERAGE)
    assert average.job_id in by['old-3200000-wait'].deps
    assert any('teardown' in d for d in by['old-3200000-wait'].deps)
    assert all(j.metadata['population_require_complete'] for j in out if j.metadata.get(s.MARK) and j.action==s.Action.AVERAGE)


def test_future_coverage_and_teardown_gates(tmp_path):
    jobs,r=fixture();out=s.build(jobs,r,tmp_path);by={j.job_id:j for j in out}
    for step in (3200000,3250000):
        gpu=[j for j in out if j.metadata.get(s.MARK) and s.boundary(j)==step and j.action in s.EVALS]
        assert len(gpu)==3
        assert all(j.job_id.startswith('dfm13-xl-') for j in gpu)
        assert {j.job_id for j in gpu}<=set(by[f'old-{step}-barrier'].deps)
        assert by[f'old-{step}-teardown'].deps==(f'old-{step}-barrier',)
    assert 'dfm13-xl-wave34-step_3200000-average' in by['old-3250000-train'].deps
    for old in jobs:
        assert by[old.job_id].metadata==old.metadata


def test_baseline_paths_do_not_overwrite_old(tmp_path):
    jobs,r=fixture();out=s.build(jobs,r,tmp_path)
    for j in out[len(jobs):]:
        if j.action in s.EVALS:assert '/wave34/' in j.metadata['dfm_log_root']


def test_no_valeu():
    jobs,r=fixture();r['euroeval'][0]['dataset']='valeu-lv'
    with pytest.raises(ValueError,match='VALEU'):s.build(jobs,r)


def test_done_future_lifecycle_preserved_with_fresh_cleanup():
    jobs,r=fixture();jobs=[j.with_updates(status=s.JobStatus.DONE) if j.action in
        (s.Action.TERMINAL_BARRIER,s.Action.TEARDOWN_EVAL) else j for j in jobs]
    out=s.build(jobs,r);by={j.job_id:j for j in out}
    assert by['old-3200000-teardown']==next(j for j in jobs if j.job_id=='old-3200000-teardown')
    assert 'dfm13-xl-wave34-step_3200000-teardown' in by['old-3250000-train'].deps
    assert 'old-3200000-euro' in by['dfm13-xl-wave34-step_3200000-barrier'].deps


@pytest.mark.parametrize('old_cleanup_done',[False,True])
def test_failed_new_gpu_cleans_pool_but_does_not_resume_training(old_cleanup_done):
    from eval_scheduler.runtime import dependencies_satisfied
    jobs,r=fixture()
    if old_cleanup_done:
        jobs=[j.with_updates(status=s.JobStatus.DONE) if j.action in
              (s.Action.TERMINAL_BARRIER,s.Action.TEARDOWN_EVAL) else j for j in jobs]
    out=s.build(jobs,r)
    failed=next(j.job_id for j in out if j.metadata.get(s.MARK) and
                s.boundary(j)==3200000 and j.action==s.Action.EVAL_DFM)
    # All GPU work has terminated; the new average cannot succeed.
    out=[j.with_updates(status=s.JobStatus.FAILED if j.job_id==failed else s.JobStatus.DONE)
         if j.action in s.EVALS else j for j in out]
    by={j.job_id:j for j in out}
    barrier=by['dfm13-xl-wave34-step_3200000-barrier']
    assert dependencies_satisfied(barrier,out)
    out=[j.with_updates(status=s.JobStatus.DONE) if j.job_id==barrier.job_id else j for j in out]
    teardown=by['dfm13-xl-wave34-step_3200000-teardown']
    assert dependencies_satisfied(teardown,out)
    assert not dependencies_satisfied(by['old-3250000-train'],out)
    if not old_cleanup_done:
        oldbarrier=by['old-3200000-barrier']
        assert dependencies_satisfied(oldbarrier,out)
        out=[j.with_updates(status=s.JobStatus.DONE) if j.job_id==oldbarrier.job_id else j for j in out]
        assert dependencies_satisfied(by['old-3200000-teardown'],out)
    # Even successful averaging cannot bypass cleanup.
    out=[j.with_updates(status=s.JobStatus.DONE) if j.job_id in
         by['old-3250000-train'].deps and j.job_id!=teardown.job_id else j for j in out]
    assert not dependencies_satisfied(by['old-3250000-train'],out)
    out=[j.with_updates(status=s.JobStatus.DONE) if j.job_id==teardown.job_id else j for j in out]
    assert dependencies_satisfied(by['old-3250000-train'],out)


def test_matching_templates_preserve_calibrated_settings():
    jobs,r=fixture()
    jobs=[j.with_updates(metadata={**j.metadata,'vllm_extra_args':'--max-num-seqs 123',
          'dfm_task_args':['special=1'],'euroeval_max_concurrent_calls':17},initial_batch=7)
          if j.action in (s.Action.EVAL_DFM,s.Action.EVAL_EUROEVAL) else j for j in jobs]
    wrong=next(j for j in jobs if j.action==s.Action.EVAL_DFM)
    jobs.insert(0,wrong.with_updates(job_id='wrong-wmt',name='wmt',metadata={**wrong.metadata,'dfm_suite':'wmt'}))
    out=s.build(jobs,r)
    for j in out:
        if j.metadata.get(s.MARK) and j.action in s.EVALS:
            assert j.initial_batch==7
            assert j.metadata['vllm_extra_args']=='--max-num-seqs 123'
            assert j.metadata['euroeval_max_concurrent_calls']==17
            assert j.metadata['dfm_task_args']==['special=1']
            assert j.metadata['template_job_id']!='wrong-wmt'


def test_unknown_category_fails_closed():
    jobs,r=fixture();r['euroeval'][0]['category']='unmatched'
    with pytest.raises(ValueError,match='No matching'):s.build(jobs,r)


def test_no_duplicate_coverage():
    jobs,r=fixture();r['dfm'][0]['name']='dala_nl'
    with pytest.raises(ValueError,match='duplicates'):s.build(jobs,r)


def test_refuse_after_training():
    jobs,r=fixture();jobs=[j.with_updates(status=s.JobStatus.DONE) if j.job_id=='old-3200000-train' else j for j in jobs]
    with pytest.raises(ValueError,match='currently running'):s.build(jobs,r)


def test_attempted_future_refused():
    jobs,r=fixture();jobs=[j.with_updates(attempt=1) if j.job_id=='old-3200000-euro' else j for j in jobs]
    with pytest.raises(ValueError,match='attempted'):s.build(jobs,r)


def test_cycle_detection():
    jobs,_=fixture();jobs[0]=jobs[0].with_updates(deps=(jobs[1].job_id,))
    with pytest.raises(ValueError,match='cycle'):s.check_graph(jobs)


def test_missing_receipt_not_ready(tmp_path):
    from dfm12.io import write_json
    r=tmp_path/'registry';receipt=tmp_path/'receipt';write_json(r,{});write_json(receipt,{'status':'pending'})
    with pytest.raises(ValueError,match='not ready'):s.ready(r,receipt)


def test_prepare_does_not_change_live_plan(tmp_path,monkeypatch):
    jobs,r=fixture();plan=tmp_path/'plan';plan.mkdir();control=tmp_path/'control'
    s.write_plan(plan/'plan.tsv',jobs);before=(plan/'plan.tsv').read_bytes()
    registry=tmp_path/'registry';receipt=tmp_path/'receipt';registry.write_text('{}');receipt.write_text('{}')
    monkeypatch.setattr(s,'ready',lambda *args:r)
    result=s.execute(registry,receipt,plan,control)
    assert result['installed'] is False and (plan/'plan.tsv').read_bytes()==before
    assert (control/'preview.json').exists()


def test_install_refuses_missing_sync_without_plan_write(tmp_path,monkeypatch):
    jobs,r=fixture();plan=tmp_path/'plan';plan.mkdir();control=tmp_path/'control'
    s.write_plan(plan/'plan.tsv',jobs);before=(plan/'plan.tsv').read_bytes()
    registry=tmp_path/'registry';receipt=tmp_path/'receipt';registry.write_text('{}');receipt.write_text('{}')
    monkeypatch.setattr(s,'ready',lambda *args:r);monkeypatch.setattr(s,'SYNC_SCRIPT',tmp_path/'missing.py')
    with pytest.raises(ValueError,match='sync script'):
        s.execute(registry,receipt,plan,control,True)
    assert (plan/'plan.tsv').read_bytes()==before
