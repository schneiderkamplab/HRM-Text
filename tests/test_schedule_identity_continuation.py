import json
from pathlib import Path
import pytest
from scripts import schedule_identity_continuation as s
from eval_scheduler.runtime import dependencies_satisfied


def test_constant_lr_and_fresh_epoch():
    args=dict(a.lstrip('+').split('=',1) for a in s.overrides({'data_config':'dfm11_identity_da_en','data_path':'fresh'}))
    assert args['epochs']=='12'
    assert args['data.path']=='fresh'
    assert args['lr']=='1e-5' and args['lr_auto']=='true'
    assert args['lr_min_ratio']=='1' and args['lr_warmup_steps']=='0'
    assert args['lr_piecewise_points']=='null'
    assert args['wandb_run_id']==s.old.RUN_ID
    assert int(args['stop_after_step'])-s.START==1000


def test_parent_gate_binds_report(tmp_path):
    report=tmp_path/'report';report.write_text('report')
    approval={'decision':'approve_full_suite','assessor':'parent','rationale':'reviewed all cases',
              'checkpoint_step':s.END,'report_sha256':s.file_hash(report)}
    assert s.approval_valid(approval,report)
    assert not s.approval_valid(dict(approval,assessor='heuristic'),report)
    report.write_text('changed')
    assert not s.approval_valid(approval,report)


def test_fresh_resume_preserves_original(tmp_path,monkeypatch):
    source=tmp_path/'source';source.mkdir();target=tmp_path/'resume'
    original={'step':s.START,'epoch':11,'batch_in_epoch':2000,
              'global_row_cursor_in_epoch':629152,'carry_policy':'none','data_path':'old'}
    name=f'checkpoint_state_{s.TAG}.json'
    (source/name).write_text(json.dumps(original))
    before=(source/name).read_bytes()
    monkeypatch.setattr(s,'complete',lambda *_:True)
    def preserve(src,dst,tag):
        dst.mkdir();s.shutil.copy2(src/name,dst/name)
    monkeypatch.setattr(s,'preserve',preserve)
    s.fresh_resume(source,target,'new')
    assert (source/name).read_bytes()==before
    copied=s.load(target/name)
    assert (copied['step'],copied['epoch'],copied['batch_in_epoch'],copied['global_row_cursor_in_epoch'])==(s.START,12,0,0)
    s.fresh_resume(source,target,'new')
    with pytest.raises(ValueError):s.fresh_resume(source,target,'different')
    (source/name).write_text(json.dumps(dict(original, data_path='changed')))
    with pytest.raises(ValueError, match='provenance'):
        s.fresh_resume(source,target,'new')


def test_insertion_failure_releases_xxl(tmp_path):
    spec=tmp_path/'spec.json';spec.write_text(json.dumps({'data_config':'dfm11_identity_da_en','data_path':'fresh'}))
    original=s.Job(s.old.XXL_JOB,s.Action.TRAIN_UNTIL_STEP,'training','XXL',
        status=s.JobStatus.RUNNING,metadata={'command':'torchrun pretrain.py resume_checkpoint_tag=old lr=3e-4',
        'wandb_run_id':'original','resume_ckpt_path':'untouched','stop_after_step':700000})
    jobs=s.insert([original],spec,'ephemeral_step_661500'); by={j.job_id:j for j in jobs}
    assert by[s.old.XXL_JOB].metadata['wandb_run_id']=='original'
    assert 'lr=3e-4' in by[s.old.XXL_JOB].metadata['command']
    failed=[j.with_updates(status=s.JobStatus.FAILED) if j.job_id==s.JOB else j for j in jobs]
    assert dependencies_satisfied(by[s.BARRIER],failed)
    released=[j.with_updates(status=s.JobStatus.DONE) if j.job_id==s.BARRIER else j for j in failed]
    assert dependencies_satisfied(by[s.old.XXL_JOB],released)


def test_actual_full_template_remapped():
    jobs=[j for j in s.read_plan(s.old.PLAN/'plan.tsv') if j.job_id != s.BARRIER]
    jobs.append(s.Job(s.BARRIER,s.Action.TERMINAL_BARRIER,'control','test',deps=(s.JOB,),deps_mode='terminal'))
    result=s.full_suite(jobs,10.005)
    additions=[j for j in result if j.job_id.startswith(s.PREFIX)]
    assert len(additions)==290
    assert {s.Action.EVAL_STANDARD,s.Action.EVAL_DFM,s.Action.EVAL_EUROEVAL} <= {j.action for j in additions}
    known={j.job_id for j in additions}|{s.JOB}
    for job in additions:
        assert set(job.deps)<=known
        assert job.metadata['no_ema'] is True
        assert job.metadata['wandb_run_id']==s.old.RUN_ID
        assert job.metadata['eval_epoch']==10.005
        assert 'XXL' not in json.dumps({k:v for k,v in job.metadata.items() if k!='plan_dir'})
        assert 'fix_mistral_regex' not in json.dumps(job.metadata)
    barrier=next(j for j in additions if j.action==s.Action.TERMINAL_BARRIER)
    assert barrier.deps_mode=='terminal'
    terminal=[j.with_updates(status=s.JobStatus.FAILED) if j.job_id in barrier.deps else j for j in additions]
    assert dependencies_satisfied(barrier,terminal)
    assert next(j for j in result if j.job_id==s.BARRIER).deps_mode=='terminal'


def test_evaluation_inventory():
    from scripts.evaluate_dfm12_identity_continuation import load_cases
    from collections import Counter
    rows,_=load_cases(s.ROOT/'data/dfm12/identity-expansion-da-en-20260926-v2-r2')
    assert Counter(row['suite'] for row in rows)=={'regression':16,'heldout':100}
    assert sum(len(row['users']) for row in rows)==206


@pytest.mark.parametrize('start,epoch,cumulative', [(2879261, 13, 3000), (2880261, 14, 4000)])
def test_campaign_preserves_optimizer_step_and_uses_fresh_epoch(monkeypatch, start, epoch, cumulative):
    for name in ('START', 'END', 'TAG', 'JOB', 'BARRIER', 'PREFIX', 'STATE',
                 'OUTPUT', 'SOURCE', 'TRAINER_EPOCH', 'IDENTITY_STEPS', 'EVAL_ROOT'):
        monkeypatch.setattr(s, name, getattr(s, name))
    spec = {'start_step': start, 'end_step': start + 1000,
            'data_config': 'dfm11_identity_da_en', 'data_path': 'new-mixture',
            'campaign': {'trainer_epoch': epoch, 'job_id': f'xl-identity-expanded-{cumulative}steps',
                         'source': str(s.ROOT / 'checkpoints/identity-previous'),
                         'output': str(s.ROOT / 'checkpoints/dfm12/identity-next'),
                         'state': str(s.ROOT / 'logs/training/identity-next')}}
    s.configure(spec)
    args = dict(a.lstrip('+').split('=', 1) for a in s.overrides(spec))
    assert s.START == start and s.END == start + 1000
    assert s.IDENTITY_STEPS == cumulative
    assert args['resume_checkpoint_tag'] == f'step_{start}'
    assert args['epochs'] == str(epoch)
    assert args['stop_after_step'] == str(start + 1000)
    assert args['lr'] == '1e-5' and args['lr_auto'] == 'true'
    assert args['reset_ema_on_resume'] == 'false'
    assert s.SOURCE != s.OUTPUT
    assert args['wandb_run_id'] == s.old.RUN_ID


@pytest.mark.parametrize('field,value', [('output', '/tmp/not-our-checkpoints'),
                                      ('state', '/tmp/not-our-logs'),
                                      ('output', str(s.old.XXL))])
def test_campaign_rejects_unowned_paths(field, value):
    campaign = {'trainer_epoch': 13, 'job_id': 'xl-identity-third',
                'source': str(s.ROOT / 'checkpoints/previous'),
                'output': str(s.ROOT / 'checkpoints/dfm12/next'),
                'state': str(s.ROOT / 'logs/training/next')}
    campaign[field] = value
    with pytest.raises(ValueError, match='ownership'):
        s.configure({'start_step': 2879261, 'end_step': 2880261, 'campaign': campaign})


def test_preflight_rejects_existing_output(tmp_path, monkeypatch):
    output = tmp_path / 'existing'
    output.mkdir()
    monkeypatch.setattr(s, 'OUTPUT', output)
    spec = tmp_path / 'spec.json'
    spec.write_text('{}')
    with pytest.raises(ValueError, match='must be fresh'):
        s.preflight(spec)


def test_evaluation_gpu_allocation_is_explicit_and_backwards_compatible():
    assert s.evaluation_environment({})['CUDA_VISIBLE_DEVICES'] == '7'
    env = s.evaluation_environment({'evaluation_gpus': '0,1,2,3,4,5,6,7'})
    assert env['CUDA_VISIBLE_DEVICES'] == '0,1,2,3,4,5,6,7'
    assert env['WANDB_DISABLED'] == 'true'


@pytest.mark.parametrize('devices', ['', '8', '7,7', 'all', [0, 1], '0, 1'])
def test_invalid_evaluation_allocation(devices):
    with pytest.raises(ValueError, match='Evaluation GPUs'):
        s.evaluation_environment({'evaluation_gpus': devices})


@pytest.mark.parametrize('evaluation_code', [0, 4, 3])
def test_deferred_review_releases_without_approval_or_sleep(tmp_path, monkeypatch, evaluation_code):
    from types import SimpleNamespace
    monkeypatch.setattr(s, 'STATE', tmp_path)
    monkeypatch.setattr(s, 'complete', lambda *_: True)
    monkeypatch.setattr(s.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0))
    seen = {}
    def popen(*args, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(pid=123, wait=lambda **kw: evaluation_code)
    monkeypatch.setattr(s.subprocess, 'Popen', popen)
    monkeypatch.setattr(s, 'identity', lambda pid: {'pid': pid})
    monkeypatch.setattr(s.time, 'sleep', lambda *_: pytest.fail('Deferred review must not wait'))
    monkeypatch.setattr(s, 'apply_full_suite', lambda *_: pytest.fail('No automatic approval'))
    report = tmp_path / 'responses.json'
    report.write_text(json.dumps({'status': 'complete_with_length_stops'}))
    spec = tmp_path / 'spec.json'
    spec.write_text(json.dumps({'evaluation_command': ['evaluate'],
        'evaluation_report': str(report), 'review_mode': 'deferred',
        'evaluation_gpus': '0,1,2,3,4,5,6,7'}))
    assert s.segment(spec, ['train']) == 0
    assert seen['env']['CUDA_VISIBLE_DEVICES'] == '0,1,2,3,4,5,6,7'
    if evaluation_code == 3:
        assert 'exited 3' in s.load(tmp_path / 'evaluation-error.json')['error']
        assert not (tmp_path / 'review-deferred.json').exists()
    else:
        assert s.load(tmp_path / 'review-deferred.json')['report_sha256'] == s.file_hash(report)
    assert s.load(tmp_path / 'phase.json')['phase'] == 'scheduler_barrier_released'
