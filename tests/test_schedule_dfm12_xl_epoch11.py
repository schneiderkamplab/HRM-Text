from pathlib import Path

import pytest

from scripts import schedule_dfm12_xl_epoch11 as schedule
from dfm12.io import write_json
from eval_scheduler.model import Action, JobStatus, read_plan
from eval_scheduler.runtime import dependencies_satisfied


def test_segment_freezes_policy_before_training(tmp_path, monkeypatch):
    manifest = tmp_path/'run.json'
    write_json(manifest, dict(start_step=2877261,end_step=3325079))
    write_json(tmp_path/'preflight.json', dict(
        run_policy_sha256=schedule.run_policy_hash(manifest), pins={}))
    def train(command, cwd):
        write_json(manifest, dict(start_step=2877261,end_step=3325079,lr_decay_start_step=1))
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(schedule.subprocess,'run',train)
    class ReachedFinalization(Exception):
        pass
    def lock(plan):
        raise ReachedFinalization
    monkeypatch.setattr(schedule,'PlanLock',lock)
    with pytest.raises(ReachedFinalization):
        schedule.segment(tmp_path,manifest,['stop_after_step=2900000'])


@pytest.fixture(scope='module')
def template():
    jobs=read_plan(schedule.SOURCE_PLAN/'plan.tsv')
    return [j for j in jobs if j.job_id.startswith(schedule.TEMPLATE_PREFIX)]


def test_boundaries_and_final_natural_epoch(template,tmp_path):
    run=dict(start_step=2877261,end_step=3078123)
    jobs=schedule.build(template,run,tmp_path,tmp_path/'run.json')
    trains=[j for j in jobs if j.action==Action.TRAIN_UNTIL_STEP]
    assert [j.metadata['stop_after_step'] for j in trains]==[2900000,2950000,3000000,3050000,3078124]
    assert trains[0].metadata['resume_from_tag']=='epoch_10'
    assert trains[0].metadata['resume_ckpt_path']==str(schedule.SOURCE)
    assert trains[-1].metadata['ckpt_tag']=='epoch_11'
    assert trains[-1].metadata['completion_checkpoint_tag']=='epoch_11'
    assert all(j.metadata['min_gpu_free_mib']==178000 and j.gpu_count==8 and j.gpu_policy=='all' for j in trains)
    assert len(jobs)==5*291
    assert all(j.status!=JobStatus.DONE for j in jobs)
    assert sum(j.status==JobStatus.SKIPPED for j in jobs)==5*sum(j.status==JobStatus.SKIPPED for j in template)


def test_exact_boundary_end_gets_one_epoch_evaluation(template):
    jobs=schedule.build(template,dict(start_step=2877261,end_step=3000000))
    trains=[j for j in jobs if j.action==Action.TRAIN_UNTIL_STEP]
    assert [j.metadata['ckpt_tag'] for j in trains]==['step_2900000','step_2950000','epoch_11']


def test_original_run_judges_tokenizer_and_canonical_axes(template):
    jobs=schedule.build(template,dict(start_step=2877261,end_step=3000000))
    for j in jobs:
        if j.action==Action.TRAIN_UNTIL_STEP:
            continue
        assert j.metadata['wandb_run_id']==schedule.RUN
        assert j.metadata['wandb_project']=='DFM5'
        assert j.metadata['fix_mistral_regex'] is False
        assert j.metadata['no_ema'] is False
        assert j.metadata['eval_epoch']>=10
        assert 'dfm11_XL_epoch10' not in str(j.metadata)
        if j.action==Action.EXPORT_HF:
            assert j.metadata['export_tokenizer_path']==str(schedule.ROOT/'data/dfm11_tokenizer')
            assert j.metadata['python_bin']==str(schedule.ROOT/'scripts/resume_xl_dfm12_epoch11.sh')
            assert j.metadata['tokenizer_variant']=='training_no_mistral_regex'
        if j.action==Action.AVERAGE:
            assert j.metadata['atomic_v3_averages'] is True
        if j.action in (Action.EVAL_EUROEVAL,Action.EVAL_EUROEVAL_BATCHED_IFEVAL):
            assert Path(j.log_dir)==Path(j.metadata['euroeval_log_root'])/j.metadata['ckpt_tag']/j.name
        if j.action==Action.EVAL_DFM and j.name=='generative_talemaader':
            assert j.metadata['judge_server_model']=='unsloth/gemma-4-E4B-it'
    assert template[0].metadata['ckpt_tag']=='epoch_10'


def test_release_allows_post_failure_but_waits_for_running_gpu(template):
    jobs=schedule.build(template,dict(start_step=2877261,end_step=3000000))
    first=[j for j in jobs if j.metadata.get('ckpt_tag')=='step_2900000']
    barrier=next(j for j in first if j.action==Action.TERMINAL_BARRIER)
    teardown=next(j for j in first if j.action==Action.TEARDOWN_EVAL)
    settled=[j.with_updates(status=JobStatus.FAILED) if j.action in (Action.AVERAGE,Action.REPORT)
             else j.with_updates(status=JobStatus.DONE) for j in first]
    assert barrier.deps_mode=='terminal'
    assert dependencies_satisfied(barrier,settled)
    assert dependencies_satisfied(teardown,settled)
    active=next(j for j in first if j.job_id in barrier.deps and j.requires_gpu)
    busy=[j.with_updates(status=JobStatus.RUNNING) if j.job_id==active.job_id else j for j in settled]
    assert not dependencies_satisfied(barrier,busy)
    next_train=next(j for j in jobs if j.action==Action.TRAIN_UNTIL_STEP and j.metadata['ckpt_tag']=='step_2950000')
    assert next_train.deps==(teardown.job_id,)


def test_training_options_and_lr_curve():
    from types import SimpleNamespace
    from models.lr_rewarm import rewarm_lr
    run=dict(start_step=2877261,end_step=3325079)
    args=schedule.training_arguments(run,[])
    config=dict(x.split('=',1) for x in args if '=' in x)
    assert config['epochs']=='11' and config['gradient_accumulation_steps']=='2'
    assert config['arch.bp_max_steps']=='8' and config['lr_auto']=='true'
    assert config['fsdp_params_precision']=='fp32' and config['fwd_bwd_dtype']=='bfloat16'
    assert config['wandb_run_id']==schedule.RUN
    assert config['checkpoint_step_interval']=='10000'
    assert config['ephemeral_checkpoint_step_interval']=='500'
    cfg=SimpleNamespace(**{k:float(config[k]) for k in ('lr','lr_min_ratio','lr_rewarm_start_ratio')},
        **{k:int(config[k]) for k in ('lr_rewarm_steps','lr_rewarm_start_step','lr_decay_start_step','lr_decay_end_step')})
    assert config['lr_rewarm_steps']=='22739'
    assert config['lr_decay_start_step']=='3250000'
    for step,expected in [(2877261,1e-5),(2900000,3e-4),(3250000,3e-4),
                          ((3250000+3325079)/2,1.55e-4),(3325079,1e-5)]:
        assert rewarm_lr(cfg,step)==pytest.approx(expected)
    with pytest.raises(ValueError,match='Only scheduler'):
        schedule.training_arguments(run,['lr=1'])


@pytest.mark.parametrize('free',[177999,178000])
def test_gpu_gate(free):
    text='\n'.join(f'{i}, {free}' for i in range(8))
    if free<178000:
        with pytest.raises(RuntimeError):schedule.gpu_gate(text)
    else:
        schedule.gpu_gate(text)


def test_missing_gpu_and_bad_manifest(tmp_path):
    with pytest.raises(RuntimeError):schedule.gpu_gate('0, 180000')
    path=tmp_path/'run.json'
    write_json(path,dict(start_step=2877261,end_step=3200000,identity_repeat=10))
    with pytest.raises(ValueError,match='Identity'):schedule.read_run(path)
    write_json(path,dict(start_step=2877261,end_step=3200000,lr_rewarm_steps=1))
    with pytest.raises(ValueError,match='LR'):schedule.read_run(path)


def test_data_ready_needs_both_publications_and_bound_receipt(tmp_path,monkeypatch):
    from dfm12.io import file_hash
    data=tmp_path/'data'
    monkeypatch.setattr(schedule,'DATA',data)
    manifest=tmp_path/'run.json'
    write_json(manifest,dict(start_step=2877261,end_step=3200000,specification_sha256='spec'))
    assert not schedule.data_ready(manifest)
    write_json(data/'metadata.json',{})
    assert not schedule.data_ready(manifest)
    write_json(tmp_path/'ready.json',dict(specification_sha256='wrong'))
    with pytest.raises(ValueError,match='mismatch'):schedule.data_ready(manifest)
    write_json(tmp_path/'ready.json',dict(specification_sha256='spec',end_step=3200000,
                                        dataset=str(data),metadata_sha256=file_hash(data/'metadata.json')))
    with pytest.raises(ValueError,match='missing'):schedule.data_ready(manifest)
    write_json(data/'epoch-mapping.json',dict(identity_repeat=0))
    for path in [data/'tokens.npy',*(data/'epoch_10'/f'{name}.npy' for name in ('inst_start','inst_len','resp_start','resp_len'))]:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.touch()
    assert schedule.data_ready(manifest)


def test_scheduler_uses_all_gpus_and_persistent_servers():
    command=schedule.scheduler_command(Path('/plan'))
    assert command[-1]=='--persistent-vllm'
    assert command[command.index('--gpus')+1]=='0,1,2,3,4,5,6,7'


def test_export_converter_must_finish_then_tokenizer_validation(monkeypatch,tmp_path):
    calls=[]
    monkeypatch.setattr(schedule.subprocess,'run',lambda command,**kw:calls.append(('convert',command,kw)))
    monkeypatch.setattr(schedule,'validate_export_tokenizer',lambda directory:calls.append(('validate',directory)))
    command=['conversion/convert_to_hf.py','--out_dir',str(tmp_path)]
    schedule.export_checkpoint(command)
    assert calls[0]==('convert',[schedule.PYTHON,*command],dict(cwd=schedule.ROOT,check=True))
    assert calls[1]==('validate',tmp_path)
    with pytest.raises(ValueError):schedule.export_checkpoint(['not-the-converter'])


def test_run_policy_hash_ignores_only_completion_time(tmp_path):
    path=tmp_path/'run.json'
    record=dict(start_step=2877261,end_step=3200000,completed=1)
    write_json(path,record)
    expected=schedule.run_policy_hash(path)
    write_json(path,dict(record,completed=2))
    assert schedule.run_policy_hash(path)==expected
    write_json(path,dict(record,end_step=3200001))
    assert schedule.run_policy_hash(path)!=expected


def test_shell_export_dispatch_and_command_construction(template):
    import shlex
    from eval_scheduler.runtime import python_bin
    jobs=schedule.build(template,dict(start_step=2877261,end_step=3200000))
    job=next(j for j in jobs if j.action==Action.EXPORT_HF)
    command=[python_bin(job),'conversion/convert_to_hf.py','--out_dir','/tmp/export']
    assert command[0]==str(schedule.ROOT/'scripts/resume_xl_dfm12_epoch11.sh')
    script=Path(command[0]).read_text()
    assert '"${1:-}" == "conversion/convert_to_hf.py"' in script
    assert 'schedule_dfm12_xl_epoch11.py export -- "$@"' in script
    train=next(j for j in jobs if j.action==Action.TRAIN_UNTIL_STEP)
    words=shlex.split(train.metadata['command'])
    assert words[words.index('--')+1]=='bash'
