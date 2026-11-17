import io
import json
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'eval_scheduler'))
from eval_scheduler.model import Action,Job,JobStatus
from eval_scheduler.store import SQLiteJobStore
from eval_scheduler import database_monitor as monitor


def fixture(tmp_path,training=False):
    store=SQLiteJobStore(tmp_path/'jobs.sqlite')
    jobs=[Job(j,Action.EVAL_DFM,'dfm',j) for j in ('a','b')]
    jobs += [Job('cpu',Action.MERGE_DFM,'dfm','merge'),
             Job('ready',Action.EVAL_DFM,'dfm','ready'),
             Job('blocked',Action.EVAL_DFM,'dfm','blocked',deps=('a',))]
    if training:jobs.append(Job('train',Action.TRAIN_UNTIL_STEP,'training','train'))
    store.import_jobs(jobs)
    store.claim_jobs(['a','b','cpu']+(['train'] if training else []))
    (tmp_path/'database.json').write_text(json.dumps(dict(database='jobs.sqlite',snapshot_path='runtime.json')))
    snapshot=dict(schema_version=1,updated_at=100,database=str(store.path),
        shared=dict(capacity_per_gpu=32,queued=7,accepting=True,slots={
            '0':dict(active=4,queued=2,job_ids=['a','b']),
            '1':dict(active=3,queued=5,job_ids=['a'])}),
        active_jobs={'a':dict(gpus=[0,1],phase='client'),'b':dict(gpus=[0],phase='client'),
                     'cpu':dict(gpus=[],phase='cpu')},
        cpu=dict(total_cores=256,reserve_cores=8,capacity=248,available_cores=242))
    if training:snapshot['training']=dict(job_id='train',gpus=list(range(8)))
    (tmp_path/'runtime.json').write_text(json.dumps(snapshot))
    return store,snapshot


def test_many_clients_per_gpu_requests_not_jobs(tmp_path):
    store,_=fixture(tmp_path)
    before=[j.to_row() for j in store.load_jobs()]
    status=monitor.read_status(tmp_path,now=105)
    assert status['gpus']['0']['client_jobs']==['a','b']
    assert status['gpus']['1']['client_jobs']==['a']
    assert status['gpus']['0']['active']==4
    assert status['ready']==['ready'] and status['blocked_pending']==1
    assert status['cpu_jobs']==['cpu'] and status['cpu']['reserve_cores']==8
    text=monitor.render_text(status)
    assert 'client_jobs=2 a, b' in text and 'active=4 queued=2 capacity=32' in text
    assert 'reserve_cores=8' in text
    assert before==[j.to_row() for j in store.load_jobs()]


def test_training_all_gpus(tmp_path):
    fixture(tmp_path,training=True)
    status=monitor.read_status(tmp_path,now=105)
    assert set(status['gpus'])==set(map(str,range(8)))
    assert all(g['training']==['train'] for g in status['gpus'].values())
    assert 'TRAINING ALL GPUs: train' in monitor.render_text(status)


def test_stale_and_unknown_are_not_idle(tmp_path):
    fixture(tmp_path)
    status=monitor.read_status(tmp_path,now=200)
    assert status['snapshot_stale'] and 'last reported' in ' '.join(status['warnings'])
    (tmp_path/'runtime.json').unlink()
    status=monitor.read_status(tmp_path,now=200,gpus=[0])
    assert status['gpus']['0']['active'] is None
    assert 'active=?' in monitor.render_text(status)
    assert status['counts']['running']==3


@pytest.mark.parametrize('content',['{','[]','{"updated_at":NaN}',
    '{"updated_at":100,"updated_at":100}',
    '{"updated_at":100,"database":"foreign.sqlite"}'])
def test_bad_snapshot_never_hides_database(tmp_path,content):
    fixture(tmp_path);(tmp_path/'runtime.json').write_text(content)
    status=monitor.read_status(tmp_path,now=105)
    assert status['counts']['running']==3 and status['warnings']
    assert status['snapshot_stale']


def test_snapshot_finished_jobs_do_not_remain_active(tmp_path):
    store,_=fixture(tmp_path)
    # A real fenced completion makes the asynchronous snapshot stale at job level.
    with sqlite3.connect(store.path) as db:token=db.execute("SELECT token FROM jobs WHERE job_id='a'").fetchone()[0]
    store.finish('a',token,{'status':JobStatus.DONE})
    status=monitor.read_status(tmp_path,now=105)
    assert status['gpus']['0']['client_jobs']==['b']
    assert status['gpus']['1']['client_jobs']==[]
    assert status['ready_count']==2


def test_no_database_creation_and_bounded_details(tmp_path):
    with pytest.raises(sqlite3.OperationalError):
        monitor.read_status(tmp_path,database=tmp_path/'missing.sqlite')
    assert not (tmp_path/'missing.sqlite').exists()
    fixture(tmp_path)
    status=monitor.read_status(tmp_path,now=105,max_jobs=1)
    assert status['counts']['running']==3 and len(status['active_jobs'])==1
    assert status['active_details_truncated']==2 and status['warnings']


def test_wal_uncommitted_writer_and_monitor_read_only(tmp_path):
    store,_=fixture(tmp_path)
    with sqlite3.connect(store.path) as writer:
        writer.execute('BEGIN IMMEDIATE')
        writer.execute("UPDATE jobs SET attempt=9 WHERE job_id='a'")
        status=monitor.read_status(tmp_path,now=105)
        assert status['active_jobs']['a']['attempt']==0
        writer.rollback()


def test_administrative_lock_not_dependency_failure(tmp_path):
    store,_=fixture(tmp_path)
    store.set_admin_lock(True)
    status=monitor.read_status(tmp_path,now=105)
    assert status['dispatch_locked'] and status['ready_count']==0
    assert status['dependency_ready']==1 and status['blocked_pending']==1
    assert not status['ready']


def test_minimal_pool_snapshot_does_not_invent_client_mapping(tmp_path):
    _,snapshot=fixture(tmp_path)
    snapshot['active_jobs']={}
    snapshot['shared']['slots']={'0':{'active':7,'provisioning':False}}
    (tmp_path/'runtime.json').write_text(json.dumps(snapshot))
    status=monitor.read_status(tmp_path,now=105)
    text=monitor.render_text(status)
    assert 'active=7 queued=? capacity=32; client_jobs=?' in text
    assert set(status['unassigned_clients'])=={'a','b','cpu'}


def test_relative_marker_resolves_independently_of_cwd(tmp_path,monkeypatch):
    fixture(tmp_path)
    other=tmp_path/'elsewhere';other.mkdir();monkeypatch.chdir(other)
    assert monitor.read_status(tmp_path,now=105)['total']==5


def test_training_log_progress_and_eta(tmp_path):
    store,snapshot=fixture(tmp_path,training=True)
    logs=tmp_path/'training';logs.mkdir()
    (logs/'train_until_step_100.log').write_text('20/100 [00:10<00:40, 2.00it/s]\n')
    with sqlite3.connect(store.path) as db:
        definition=json.loads(db.execute("SELECT definition FROM jobs WHERE job_id='train'").fetchone()[0])
        definition['metadata_json']=json.dumps(dict(stop_after_step=100,resume_from_tag='step_0'))
        db.execute("UPDATE jobs SET definition=?,log_dir=? WHERE job_id='train'",(json.dumps(definition),str(logs)))
    snapshot['active_jobs']['train']=dict(started_at=90,phase='exclusive',gpus=list(range(8)))
    (tmp_path/'runtime.json').write_text(json.dumps(snapshot))
    status=monitor.read_status(tmp_path,now=105,progress_limit=1)
    assert status['progress_jobs']==['train']
    info=status['active_jobs']['train']
    assert info['progress']=='step 20/100' and info['eta']=='40s' and info['elapsed']=='15s'
    assert 'ETA 40s' in monitor.render_text(status)


def test_client_lines_bounded_and_capacity_never_assumed(tmp_path):
    fixture(tmp_path)
    status=monitor.read_status(tmp_path,now=105,progress_limit=0)
    status['gpus']['0']['client_jobs']=['x'*1000]*1000
    status['gpus']['0']['capacity']=1024
    text=monitor.render_text(status)
    line=next(line for line in text.splitlines() if line.startswith('GPU0'))
    assert len(line)<300 and '(+997 more)' in line and 'capacity=1024' in line


@pytest.mark.parametrize('rich',[False,True])
def test_parent_cli_database_monitor_once(tmp_path,rich):
    from typer.testing import CliRunner
    from eval_scheduler.cli import app
    store,_=fixture(tmp_path)
    (tmp_path/'database.json').write_text(json.dumps({'database':str(store.path)}))
    (tmp_path/'runtime.json').rename(tmp_path/'database_snapshot.json')
    args=['monitor','--plan-dir',str(tmp_path),'--once']+(['--rich'] if rich else [])
    result=CliRunner().invoke(app,args)
    assert result.exit_code==0,result.output
    assert 'capacity' in result.output.lower()


def test_rich_literal_markup_and_control_characters(tmp_path):
    pytest.importorskip('rich')
    from rich.console import Console
    _,snapshot=fixture(tmp_path)
    snapshot['shared']['slots']['0']['job_ids']=['[red]missing']
    (tmp_path/'runtime.json').write_text(json.dumps(snapshot))
    output=io.StringIO()
    Console(file=output,width=160).print(monitor.rich_status_renderable(tmp_path,now=105))
    assert 'Database eval scheduler' in output.getvalue()
    assert monitor._safe('\x1b[31mhello\nworld')==' [31mhello world'


@pytest.mark.parametrize('width,height', [(100,32), (156,40), (220,70)])
def test_legacy_layout_fills_terminal_without_clipping(tmp_path,monkeypatch,width,height):
    import os
    from rich.console import Console
    from eval_scheduler.monitor import GpuInfo
    store,_ = fixture(tmp_path,training=True)
    jobs=store.load_jobs()
    jobs.extend(Job(f'blocked-{n}',Action.EVAL_DFM,'dfm',f'correction-{n}',deps=('a',))
                for n in range(100))
    # Add definitions without altering the active claims in the fixture.
    store.import_jobs(jobs)
    monkeypatch.setattr(monitor.shutil,'get_terminal_size',lambda **kw:os.terminal_size((width,height)))
    monkeypatch.setattr('eval_scheduler.monitor.gpu_infos',
        lambda ids:{g:GpuInfo(g,10000,170000,180000,97) for g in ids})
    output=io.StringIO()
    Console(file=output,width=width,height=height).print(monitor.rich_status_renderable(tmp_path,now=105))
    lines=output.getvalue().splitlines()
    assert len(lines)<=height
    assert len(lines)>=height-3
    for text in ('Running jobs','Next ready','Blocked pending','97%','GiB','more','training:train'):
        assert text in output.getvalue()
    assert max(map(len,lines))<=width


@pytest.mark.parametrize('interval',[0,-1,float('nan'),float('inf')])
def test_watch_rejects_busy_spin(tmp_path,interval):
    with pytest.raises(ValueError):monitor.watch(tmp_path,interval=interval)


def test_adopted_cooperative_training_uses_explicit_control_log(tmp_path):
    store,snapshot=fixture(tmp_path,training=True)
    control=tmp_path/'control';control.mkdir()
    (control/'training.log').write_text('20/100 [00:10<00:40, 2.00it/s]\n')
    with sqlite3.connect(store.path) as db:
        definition=json.loads(db.execute("SELECT definition FROM jobs WHERE job_id='train'").fetchone()[0])
        definition['metadata_json']=json.dumps(dict(stop_after_step=100,cooperative_training={'control_root':str(control)}))
        db.execute("UPDATE jobs SET definition=? WHERE job_id='train'",(json.dumps(definition),))
    status=monitor.read_status(tmp_path,now=105,progress_limit=1)
    info=status['active_jobs']['train']
    assert info['progress']=='step 20/100'
    assert info['eta']=='40s'
    assert info['fraction']==.2
