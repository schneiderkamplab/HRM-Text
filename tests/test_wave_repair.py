import pytest
from dfm12 import wave_repair as repair


def original():
    return dict(id='a',language='hr',task='instruction',messages=[
        dict(role='user',content='Question'),dict(role='assistant',content='Wrong answer')])


def test_repair_preserves_user(monkeypatch):
    monkeypatch.setattr(repair,'native_renderer',lambda:type('Renderer',(),{'count':lambda self,m:12})())
    row=original()
    result=dict(status='corrected',messages=[row['messages'][0],dict(role='assistant',content='Correct answer')])
    new=repair.validate_repair(row,result)
    assert new['id']!=row['id']
    assert row['messages'][-1]['content']=='Wrong answer'
    assert new['provenance']['repair_parent']=='a'


def test_repair_cannot_change_task():
    row=original()
    result=dict(status='corrected',messages=[dict(role='user',content='Different question'),row['messages'][1]])
    with pytest.raises(ValueError,match='nonassistant_changed'):
        repair.validate_repair(row,result)


def test_reject_and_unchanged_cannot_pass():
    row=original()
    with pytest.raises(ValueError,match='not_corrected'):
        repair.validate_repair(row,dict(status='reject',messages=row['messages']))
    with pytest.raises(ValueError,match='unchanged_repair'):
        repair.validate_repair(row,dict(status='corrected',messages=row['messages']))


def test_failed_audit_recovery_is_independently_reviewed(tmp_path):
    import json
    from dfm12.io import file_hash, write_json, digest
    from dfm12.jobs import Queue, audit_payload
    root=tmp_path
    component='test'
    path=root/'audit-ready'/component/'candidates.jsonl'
    path.parent.mkdir(parents=True)
    row=original()
    path.write_text(json.dumps(row)+'\n')
    write_json(path.parent/'receipt.json',dict(path=str(path),sha256=file_hash(path),counts={'ready':1}))
    source=Queue(root/'audit/jobs.sqlite')
    key=source.add('audit',audit_payload(row,repair.MODEL))
    source.db.execute("UPDATE jobs SET status='failed',attempts=4,error='truncated' WHERE id=?",(key,))
    repair.process(root,component)
    status=json.loads((root/'release'/component/'status.json').read_text())
    assert status['counts']=={'audit_retry_pending':1}
    assert not status['export_ready']
    work=Queue(root/'repair/jobs.sqlite')
    retry=digest(['audit',repair.recovery_audit(row)])
    review=dict(keep=True,language_quality=5,coherence=5,usefulness=5,reason='Verified')
    work.db.execute("UPDATE jobs SET status='done',result=? WHERE id=?",(json.dumps(review),retry))
    repair.process(root,component)
    status=json.loads((root/'release'/component/'status.json').read_text())
    assert status['counts']=={'accepted':1}
    assert status['export_ready']
    assert source.db.execute('SELECT status,attempts,error FROM jobs WHERE id=?',(key,)).fetchone()==('failed',4,'truncated')
    work.close();source.close()


def test_quarantine_distinguishes_model_output_from_transport(tmp_path):
    import sqlite3
    from dfm12.jobs import Queue
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE rows(id TEXT,status TEXT,repair_job TEXT,reaudit_job TEXT)')
    work = Queue(tmp_path / 'jobs.sqlite')
    for key, error in [('format', 'ValueError: invalid_role_order'), ('network', 'TimeoutError: disconnected')]:
        job = work.add('generate', {'case': key})
        work.db.execute("UPDATE jobs SET status='failed',attempts=4,error=? WHERE id=?", (error, job))
        db.execute('INSERT INTO rows VALUES(?,?,?,NULL)', (key, 'repair_infrastructure_failed', job))
    repair.quarantine_invalid_outputs(db, work)
    assert dict(db.execute('SELECT id,status FROM rows')) == {
        'format': 'excluded_invalid_repair', 'network': 'repair_infrastructure_failed'}
    assert db.execute('SELECT attempts,error FROM exclusions').fetchone() == (4, 'ValueError: invalid_role_order')
    assert work.db.execute("SELECT count(*) FROM jobs WHERE status='failed'").fetchone()[0] == 2
    work.close();db.close()


def test_missing_target_with_stale_review_is_quarantined(tmp_path):
    import sqlite3
    from dfm12.jobs import Queue
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE rows(id TEXT,status TEXT,repair_job TEXT,reaudit_job TEXT)')
    work = Queue(tmp_path / 'jobs.sqlite')
    review = work.add('audit', {'old': True})
    work.db.execute("UPDATE jobs SET status='done' WHERE id=?", (review,))
    job = work.add('generate', {'repair': True})
    work.db.execute("UPDATE jobs SET status='failed',attempts=4,error=? WHERE id=?",
                    ('ValueError: missing_assistant_target', job))
    db.execute('INSERT INTO rows VALUES(?,?,?,?)', ('row', 'repair_infrastructure_failed', job, review))
    repair.quarantine_invalid_outputs(db, work)
    assert db.execute('SELECT status FROM rows').fetchone()[0] == 'excluded_invalid_repair'
    assert db.execute('SELECT job_id FROM exclusions').fetchone()[0] == job
    assert work.db.execute('SELECT status FROM jobs WHERE id=?', (review,)).fetchone()[0] == 'done'
    work.close();db.close()
