import json
from pathlib import Path

import pytest

from eval_scheduler.database_cli import (
    assert_runner_stopped, read_definition_patch, read_import,
    runner_command_matches, validate_graph,
)
from eval_scheduler.model import Action, Job, write_plan
from eval_scheduler.model import JobStatus
from eval_scheduler.store import SQLiteJobStore
from eval_scheduler.database_cli import database_app
from typer.testing import CliRunner


def job(key, deps=()):
    return Job(key, Action.REPORT, 'test', key, deps=deps)


def test_backup_and_preflight(tmp_path):
    store = SQLiteJobStore(tmp_path/'state.sqlite')
    store.import_jobs([job('a')])
    claim = store.claim_jobs(['a'])['a']
    backup = tmp_path/'backup.sqlite'
    result = CliRunner().invoke(database_app, ['backup', '--database', str(store.path), '--output', str(backup)])
    assert result.exit_code == 0, result.output
    assert SQLiteJobStore(backup).attempt_token('a') == claim.token
    assert CliRunner().invoke(database_app, ['backup', '--database', str(store.path), '--output', str(backup)]).exit_code == 1
    write_plan(tmp_path/'plan.tsv', [job('a')])
    result = CliRunner().invoke(database_app, ['preflight', '--plan-dir', str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)['failures'] == []
    assert not (tmp_path/'database.json').exists()


def test_preflight_requires_single_source(tmp_path):
    store = SQLiteJobStore(tmp_path/'state.sqlite')
    store.import_jobs([job('a')])
    for argv in (['preflight'], ['preflight', '--plan-dir', str(tmp_path), '--database', str(store.path)]):
        result = CliRunner().invoke(database_app, argv)
        assert result.exit_code == 1, result.output
        assert 'exactly one' in result.output


def test_preflight_database_availability(tmp_path):
    store = SQLiteJobStore(tmp_path/'state.sqlite')
    config = tmp_path/'cfg.yaml'
    config.write_text('ok')
    good = Job('good', Action.REPORT, 'test', 'good', metadata={'ckpt_path': str(config)})
    bad = Job('bad', Action.REPORT, 'test', 'bad',
              metadata={'ckpt_path': str(config), 'log_root': '/nonexistent-base-xyz/sub/root'})
    done = Job('done', Action.REPORT, 'test', 'done',
               metadata={'ckpt_path': str(config)}, status=JobStatus.DONE)
    store.import_jobs([good, bad, done])
    result = CliRunner().invoke(database_app, ['preflight', '--database', str(store.path)])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload['pending'] == 2
    assert {f['job_id'] for f in payload['failures']} == {'bad'}
    flat = [issue for f in payload['failures'] for issue in f['issues']]
    assert any('unanchored' in issue for issue in flat)
    result = CliRunner().invoke(database_app, ['preflight', '--database', str(store.path), '--all'])
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)['pending'] == 3


def test_preflight_train_availability(tmp_path):
    store = SQLiteJobStore(tmp_path/'state.sqlite')
    workdir = tmp_path/'repo'
    workdir.mkdir()
    py = tmp_path/'python'
    py.write_text('#!/bin/sh\n')
    py.chmod(0o755)
    ckpt = tmp_path/'ckpt'
    ckpt.mkdir()
    (tmp_path/'settings.json').write_text('{}')
    (tmp_path/'shim.so').write_text('')
    base = {'command': f'{py} pretrain.py cfg=cfg_pretrain stop_after_step=100',
            'workdir': str(workdir), 'ckpt_path': str(ckpt),
            'cooperative_training': {'control_root': str(tmp_path/'control'), 'python': str(py),
                                     'launcher_settings': str(tmp_path/'settings.json'),
                                     'cuda_checkpoint': {'shim_library': str(tmp_path/'shim.so')}}}
    good = Job('tgood', Action.TRAIN_UNTIL_STEP, 'test', 'tgood', metadata=dict(base))
    bad = Job('tbad', Action.TRAIN_UNTIL_STEP, 'test', 'tbad',
              metadata={**base, 'cooperative_training': {**base['cooperative_training'],
                                                         'launcher_settings': str(tmp_path/'absent.json')}})
    store.import_jobs([good, bad])
    result = CliRunner().invoke(database_app, ['preflight', '--database', str(store.path)])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert {f['job_id'] for f in payload['failures']} == {'tbad'}
    assert any('launcher_settings' in issue for issue in payload['failures'][0]['issues'])


def test_tsv_graph_validation(tmp_path):
    path=tmp_path/'input.tsv'
    write_plan(path,[job('a'),job('b',('a',))])
    assert len(read_import(path))==2
    for jobs in ([job('a',('absent',))],[job('a',('b',)),job('b',('a',))],[job('a'),job('a')]):
        write_plan(path,jobs)
        with pytest.raises(ValueError):read_import(path)
    path.write_text('job_id\n')
    with pytest.raises(ValueError):read_import(path)


def test_deep_graph_uses_no_recursive_dfs():
    validate_graph([job(str(i),(str(i-1),) if i else ()) for i in range(3000)])


def test_runner_matching_relative_equal_and_unrelated(tmp_path):
    plan=tmp_path/'plan'
    assert runner_command_matches(['python','-m','eval_scheduler','run','--plan-dir','plan'],tmp_path,plan)
    assert runner_command_matches(['hrm-eval-scheduler','cluster','coordinator','--plan-dir='+str(plan)],tmp_path,plan)
    assert not runner_command_matches(['python','-m','eval_scheduler','status','--plan-dir',str(plan)],tmp_path,plan)
    assert not runner_command_matches(['python','-m','eval_scheduler','run','--plan-dir','other'],tmp_path,plan)


def test_active_runner_blocks_migration(tmp_path):
    proc=tmp_path/'proc';entry=proc/'123456789';entry.mkdir(parents=True)
    (entry/'cmdline').write_bytes(b'python\0-m\0eval_scheduler\0run\0--plan-dir\0plan\0')
    (entry/'cwd').symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(ValueError,match='Active scheduler'):assert_runner_stopped(tmp_path/'plan',proc)
    (entry/'cmdline').write_bytes(b'python\0-m\0eval_scheduler\0status\0--plan-dir\0plan\0')
    assert_runner_stopped(tmp_path/'plan',proc)


def test_patch_rejects_runtime_and_duplicate_keys(tmp_path):
    path=tmp_path/'edit.json'
    for value in ('{"status":"pending"}','{"attempt":0}','{"name":"a","name":"b"}','{}'):
        path.write_text(value)
        with pytest.raises(ValueError):read_definition_patch(path)
    path.write_text(json.dumps({'name':'new','metadata':{'example':True}}))
    assert read_definition_patch(path)['name']=='new'


def test_cli_import_export_edit_reset_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr('eval_scheduler.database_cli.assert_runner_stopped',lambda p:None)
    runner=CliRunner();source=tmp_path/'plan.tsv';db=tmp_path/'jobs.sqlite3'
    write_plan(source,[job('a'),job('b',('a',))])
    args=['import','--source',str(source),'--database',str(db),'--plan-dir',str(tmp_path),'--runners-stopped']
    result=runner.invoke(database_app,args);assert result.exit_code==0,result.output
    assert json.loads((tmp_path/'database.json').read_text())=={'database':str(db.resolve())}
    store=SQLiteJobStore(db)
    claim=store.claim_jobs(['a'])['a']
    assert store.finish('a',claim.token,{'status':JobStatus.DONE,'attempt':3})
    # An old TSV must not revert a completed job to pending or clear its attempts.
    assert runner.invoke(database_app,args).exit_code!=0  # unlocked imports are forbidden
    store.set_admin_lock(True)
    result=runner.invoke(database_app,args)
    assert result.exit_code==0,result.output
    store.set_admin_lock(False)
    assert store.load_jobs()[0].status==JobStatus.DONE
    assert store.load_jobs()[0].attempt==3
    patch=tmp_path/'patch.json';patch.write_text('{"name":"updated"}')
    result=runner.invoke(database_app,['edit','--database',str(db),'--job-id','a','--patch',str(patch)])
    assert result.exit_code==0,result.output
    assert store.load_jobs()[0].status==JobStatus.DONE and store.load_jobs()[0].name=='updated'
    output=tmp_path/'export.tsv'
    assert runner.invoke(database_app,['export','--database',str(db),'--output',str(output)]).exit_code==0
    assert read_import(output)==store.load_jobs()
    status=runner.invoke(database_app,['status','--database',str(db)])
    assert json.loads(status.output)['counts']['done']==1
    assert runner.invoke(database_app,['reset','--database',str(db),'--job-id','a','--yes']).exit_code==0
    assert store.load_jobs()[0].status==JobStatus.PENDING


def test_cli_invalid_import_and_edit_do_not_change_store(tmp_path, monkeypatch):
    monkeypatch.setattr('eval_scheduler.database_cli.assert_runner_stopped',lambda p:None)
    store=SQLiteJobStore(tmp_path/'db');store.import_jobs([job('a'),job('b',('a',))])
    before=store.load_jobs();source=tmp_path/'bad.tsv';write_plan(source,[job('a',('missing',))])
    runner=CliRunner()
    result=runner.invoke(database_app,['import','--source',str(source),'--database',str(store.path),
        '--plan-dir',str(tmp_path),'--runners-stopped'])
    assert result.exit_code!=0 and store.load_jobs()==before
    patch=tmp_path/'patch.json';patch.write_text('{"deps":["b"]}')
    result=runner.invoke(database_app,['edit','--database',str(store.path),'--job-id','a','--patch',str(patch)])
    assert result.exit_code!=0 and store.load_jobs()==before


def test_cli_refuses_implicit_creation_and_running_reset(tmp_path):
    runner=CliRunner();path=tmp_path/'absent'
    assert runner.invoke(database_app,['status','--database',str(path)]).exit_code!=0
    assert not path.exists()
    store=SQLiteJobStore(path);store.import_jobs([job('a')]);claim=store.claim_jobs(['a'])['a']
    result=runner.invoke(database_app,['reset','--database',str(path),'--job-id','a','--yes'])
    assert result.exit_code!=0 and store.attempt_token('a')==claim.token


def test_cli_active_migration_does_not_create_store(tmp_path, monkeypatch):
    def active(_):raise ValueError('Active scheduler PID123')
    monkeypatch.setattr('eval_scheduler.database_cli.assert_runner_stopped',active)
    source=tmp_path/'plan.tsv';write_plan(source,[job('a')]);db=tmp_path/'new.db'
    result=CliRunner().invoke(database_app,['import','--source',str(source),'--database',str(db),
        '--plan-dir',str(tmp_path),'--runners-stopped'])
    assert result.exit_code!=0 and not db.exists()


def test_cli_lock_calls_store_directly(tmp_path,monkeypatch):
    from types import SimpleNamespace
    calls=[]
    monkeypatch.setattr('eval_scheduler.database_cli.open_existing',lambda p:SimpleNamespace(
        set_admin_lock=lambda locked:calls.append(locked)))
    assert CliRunner().invoke(database_app,['lock','--database',str(tmp_path/'db'),'--reason','maintenance']).exit_code==0
    assert CliRunner().invoke(database_app,['unlock','--database',str(tmp_path/'db')]).exit_code==0
    assert calls==[True,False]


def test_recovery_help_is_read_only_and_never_blindly_resets():
    result=CliRunner().invoke(database_app,['recovery-help'])
    assert result.exit_code==0
    for requirement in ('.runner.lock','expected_token','JobStatus.FAILED','remote workers','no automated recover'):
        assert requirement in result.output


def test_locked_import_preserves_running_claim_without_stopping_runner(tmp_path,monkeypatch):
    store=SQLiteJobStore(tmp_path/'db');store.import_jobs([job('a'),job('b')])
    (tmp_path/'database.json').write_text(json.dumps({'database':str(store.path)}))
    claim=store.claim_jobs(['a'])['a'];store.set_admin_lock(True)
    source=tmp_path/'edit.tsv';write_plan(source,[job('a'),job('b').with_updates(name='edited')])
    def forbidden(_):raise AssertionError('Already-migrated locked imports must not require stopped runner')
    monkeypatch.setattr('eval_scheduler.database_cli.assert_runner_stopped',forbidden)
    args=['import','--source',str(source),'--database',str(store.path),'--plan-dir',str(tmp_path)]
    result=CliRunner().invoke(database_app,args)
    assert result.exit_code==0,result.output
    assert store.attempt_token('a')==claim.token and store.load_jobs()[1].name=='edited'
    before=store.load_jobs()
    write_plan(source,[job('a').with_updates(name='unsafe'),job('b')])
    result=CliRunner().invoke(database_app,args)
    assert result.exit_code!=0 and store.load_jobs()==before


def test_real_admin_lock_fences_claims_but_allows_completion(tmp_path):
    store=SQLiteJobStore(tmp_path/'db');store.import_jobs([job('a'),job('b')])
    claim=store.claim_jobs(['a'])['a'];runner=CliRunner()
    result=runner.invoke(database_app,['lock','--database',str(store.path)])
    assert result.exit_code==0,result.output
    assert store.get_admin_lock() and store.claim_jobs(['b'])=={}
    assert store.finish('a',claim.token,{'status':JobStatus.DONE})
    result=runner.invoke(database_app,['unlock','--database',str(store.path)])
    assert result.exit_code==0,result.output
    assert not store.get_admin_lock() and 'b' in store.claim_jobs(['b'])


def test_marker_conflict_and_failed_import_never_publish(tmp_path, monkeypatch):
    monkeypatch.setattr('eval_scheduler.database_cli.assert_runner_stopped',lambda p:None)
    source=tmp_path/'input.tsv';write_plan(source,[job('a')]);db=tmp_path/'new.db'
    marker=tmp_path/'database.json';marker.write_text(json.dumps({'database':str(tmp_path/'other.db')}))
    args=['import','--source',str(source),'--database',str(db),'--plan-dir',str(tmp_path),'--runners-stopped']
    result=CliRunner().invoke(database_app,args)
    assert result.exit_code!=0 and not db.exists()
    marker.unlink()
    def fail(*args,**kwargs):raise ValueError('transaction failed')
    monkeypatch.setattr(SQLiteJobStore,'import_jobs',fail)
    result=CliRunner().invoke(database_app,args)
    assert result.exit_code!=0 and not marker.exists()
