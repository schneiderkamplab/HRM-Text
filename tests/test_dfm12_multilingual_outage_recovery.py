import asyncio
import json
from pathlib import Path

import pytest

from dfm12 import multilingual_outage_recovery as r
from dfm12.io import digest, write_json


@pytest.mark.parametrize('error', [
    "ServerDisconnectedError('Server disconnected')",
    "ClientPayloadError('incomplete response')", "TimeoutError()",
    "ClientConnectorError('connection refused')",
    repr(ValueError("Stream server error: {'message': 'EngineCore encountered an issue. See server log.', 'type': 'InternalServerError', 'code': 500}")),
])
def test_infrastructure_allowlist(error):
    assert r.infrastructure(error)


@pytest.mark.parametrize('error', [None, '', 'Interrupted slot; no automatic replay',
    "ValidationError('ServerDisconnectedError')", "ValueError('Incomplete output: length')",
    "GenerationFailure('structural_whitespace_loop')", "ContractError('bad quote')",
    "ValueError('Stream server error: {}')", "ValueError('Stream server error: []')",
    repr(ValueError("Stream server error: {'message': 'bad input', 'type': 'InternalServerError', 'code': 500}")),
])
def test_not_infrastructure(error):
    assert not r.infrastructure(error)


def fixture(tmp_path, stage='generate'):
    spec = dict(language_code='nl', family='math-code', slot=100000,
                contract_version=4, cohort='test', subtype='math')
    key = r.q.pilot.slot_key(spec)
    error = "ServerDisconnectedError('Server disconnected')"
    status = 'review_abort_status_unknown' if stage == 'review' else 'abort_status_unknown'
    outcome = dict(r.q.pilot.base_outcome(spec), status=status, terminal=True,
                   completed=120, error=error, generation_status='complete' if stage=='review' else 'abort_status_unknown')
    write_json(tmp_path/'stages'/f'{key}-{stage}.json', dict(status='abort_status_unknown',
        error=error, endpoint=r.q.pilot.ENDPOINTS[0], started=90))
    return dict(id=key, origin='production', status=status, outcome_json=json.dumps(outcome),
                spec_json=json.dumps(spec), workdir=str(tmp_path))


@pytest.mark.parametrize('stage',['generate','review'])
def test_select_only_outage_and_matching_stage(tmp_path,stage):
    job=fixture(tmp_path,stage)
    assert r.selected(job,100,130)==stage
    assert r.selected(job,121,130) is None
    assert r.selected(job,100,119) is None
    for status in ('accepted','valid','duplicate','running'):
        assert r.selected(dict(job,status=status),100,130) is None
    assert r.selected(dict(job,origin='first-pilot-reaudit'),100,130) is None


def test_no_discard_complete_response(tmp_path):
    job=fixture(tmp_path)
    path=tmp_path/'stages'/f"{job['id']}-generate.json"
    state=r.load(path)
    write_json(path,dict(state,raw={'finish_reason':'stop'}))
    assert r.selected(job,100,130) is None
    write_json(path,dict(state,endpoint='http://unrelated/v1'))
    assert r.selected(job,100,130) is None
    write_json(path,dict(state,error='TimeoutError()'))
    assert r.selected(job,100,130) is None


def test_original_spec_tampering_fails(tmp_path):
    job=fixture(tmp_path)
    job['spec_json']='{}'
    with pytest.raises(ValueError,match='spec drift'):r.selected(job,100,130)


def ledger_plan(tmp_path):
    db=r.q.Ledger(tmp_path/'jobs.sqlite')
    db.initialize([dict(language='nl',family='math-code',accepted_target=2)])
    job=fixture(tmp_path/'old','review')
    job.update(language='nl',family='math-code',slot=100000,fingerprint='abc')
    keys=list(job)
    db.db.execute('INSERT INTO jobs('+','.join(keys)+') VALUES('+','.join('?' for _ in keys)+')',list(job.values()))
    db.db.execute('UPDATE groups SET attempts=1,next_slot=100001')
    db.db.execute('INSERT INTO fingerprints VALUES (?,?)',('abc',job['id']))
    old=dict(db.db.execute('SELECT * FROM jobs').fetchone())
    return db,dict(id=job['id'],old_job=old,workdir=str(tmp_path/'retry'),stage='review')


def test_activation_exact_once_no_cursors_or_attempts_reset(tmp_path):
    db,plan=ledger_plan(tmp_path)
    assert r.activate(db,plan,tmp_path)
    assert not r.activate(db,plan,tmp_path)
    group=db.db.execute('SELECT * FROM groups').fetchone()
    assert (group['active'],group['accepted'],group['attempts'],group['next_slot'])==(1,0,1,100001)
    with pytest.raises(ValueError,match='Another recovery'):r.activate(db,plan,tmp_path/'other')
    with pytest.raises(ValueError,match='drained'):r.idle(db)
    db.close()


def test_quota_and_original_drift_rollback(tmp_path):
    db,plan=ledger_plan(tmp_path)
    db.db.execute('UPDATE groups SET accepted=target')
    with pytest.raises(ValueError,match='quota'):r.activate(db,plan,tmp_path)
    assert db.db.execute('SELECT count(*) FROM metadata').fetchone()[0]==0
    assert db.db.execute('SELECT status FROM jobs').fetchone()[0]==plan['old_job']['status']
    db.db.execute('UPDATE groups SET accepted=0')
    db.db.execute("UPDATE jobs SET status='invalid_output'")
    with pytest.raises(ValueError,match='changed'):r.activate(db,plan,tmp_path)
    assert db.db.execute('SELECT active FROM groups').fetchone()[0]==0
    db.close()


def test_preserved_owner_only_and_no_delete(tmp_path):
    db,plan=ledger_plan(tmp_path)
    seen=r.OwnedSeen(db,plan['id'],'abc')
    assert 'abc' not in seen
    seen.add('abc')
    assert 'abc' in r.OwnedSeen(db,'foreign','abc')
    with pytest.raises(ValueError,match='ownership'):r.OwnedSeen(db,'foreign','abc').add('abc')
    seen.add('new')
    assert 'new' in seen
    assert db.db.execute('SELECT count(*) FROM fingerprints').fetchone()[0]==2
    db.close()


def test_no_duplicate_production_launch(tmp_path,monkeypatch):
    write_json(tmp_path/'production-resume.json',{'pid':123})
    monkeypatch.setattr(r,'_run_and_resume',lambda *a:pytest.fail('must not relaunch'))
    with pytest.raises(ValueError,match='already issued'):r.run_and_resume(tmp_path,1)


def test_preserved_generation_assembly_and_raw(tmp_path,monkeypatch):
    job=fixture(tmp_path,'review')
    candidate=dict(messages=[{'role':'assistant','content':'retained'}],tools=[])
    job['fingerprint']=digest(candidate)
    path=tmp_path/'stages'/f"{job['id']}-generate.json"
    state=dict(status='complete',raw=dict(finish_reason='stop',content='{"answer": "retained"}'),output={'answer':'retained'})
    write_json(path,state)
    write_json(tmp_path/'candidates'/f"{job['id']}.json",candidate)
    monkeypatch.setattr(r.q.v6,'generation_assemble',lambda *args:candidate)
    assert r.preserved_generation(job,None,None)==job['fingerprint']
    write_json(path,dict(state,output={'answer':'modified'}))
    with pytest.raises(ValueError,match='raw/output'):r.preserved_generation(job,None,None)


def test_frozen_stage_reuses_generation_without_network_or_rewrite(tmp_path):
    payload={'messages':[{'role':'user','content':'retained prompt'}]}
    path=tmp_path/'stages'/'saved-generate.json'
    state=dict(status='complete',request_sha256=digest(payload),attempts=1,
               output={'answer':'retained'},raw={'finish_reason':'stop','content':'{"answer":"retained"}'})
    write_json(path,state)
    before=path.read_bytes()
    async def forbidden(*args,**kwargs):
        pytest.fail('completed generation must not be regenerated')
    stages=r.q.v6.Stages(tmp_path,None,None,None,query=forbidden)
    assert asyncio.run(stages.call('saved','generate',payload,{},r.q.pilot.ENDPOINTS[0],16384))==state
    assert path.read_bytes()==before
    with pytest.raises(ValueError,match='request drift'):
        asyncio.run(stages.call('saved','generate',{}, {},r.q.pilot.ENDPOINTS[0],16384))
