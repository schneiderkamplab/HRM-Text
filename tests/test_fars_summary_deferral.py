import json
import sqlite3

import pytest

from dfm12 import fars_summary_deferral as d
from dfm12.io import digest,load


def setup_queue(tmp_path):
    path=tmp_path/'jobs.sqlite'
    db=sqlite3.connect(path)
    db.execute('CREATE TABLE jobs(id PRIMARY KEY,stage,payload,status,attempts,owner,lease,result,error)')
    db.execute('CREATE TABLE events(timestamp,job_id,attempt,status,detail)')
    ids=[]
    for index,(status,attempts,owner,lease,component) in enumerate([
        ('pending',0,None,None,d.COMPONENTS[0]),
        ('running',1,'worker',99999999999,d.COMPONENTS[0]),
        ('pending',0,None,None,'other'),
        ('pending',1,None,None,d.COMPONENTS[0]),
        ('pending',0,None,99999999999,d.COMPONENTS[0]),
        ('pending',0,None,None,d.COMPONENTS[1])]):
        payload=dict(record=dict(component=component,id=index))
        key=digest(['generate',payload]);ids.append(key)
        db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',
            (key,'generate',json.dumps(payload),status,attempts,owner,lease,None,None))
    db.commit();db.close()
    return path,ids


def test_conditional_preservation_resume_and_readiness(tmp_path):
    queue,ids=setup_queue(tmp_path);root=tmp_path/'deferral'
    assert d.propose(queue,root)==2
    with sqlite3.connect(queue) as db:
        before=db.execute('SELECT * FROM jobs ORDER BY id').fetchall()
        db.execute("UPDATE jobs SET status='running',attempts=1,owner='raced' WHERE id=?",(ids[5],))
    receipt=d.apply(root)
    assert receipt['unfinished31B']==1 and receipt['reviewed']==0
    d.apply(root)
    with sqlite3.connect(queue) as db:
        assert db.execute('SELECT count(*) FROM events').fetchone()[0]==1
        authorized=d.authorized_jobs(root,db)
        row=db.execute('SELECT * FROM jobs WHERE id=?',(ids[0],)).fetchone()
        original=next(r for r in before if r[0]==ids[0])
        assert row[:3]==original[:3] and row[4:]==original[4:]
        assert d.handoff_state(ids[0],row[3],row[2],authorized)=='unfinished31B_authorized'
        assert d.handoff_state(ids[1],'running','x',authorized).startswith('blocked')
        assert d.handoff_state('fake',d.STATUS,'x',authorized).startswith('blocked')
        db.execute("UPDATE jobs SET payload='changed' WHERE id=?",(ids[0],))
        with pytest.raises(ValueError): d.authorized_jobs(root,db)


def test_proposal_hash_drift_fails_closed(tmp_path):
    queue,_=setup_queue(tmp_path);root=tmp_path/'deferral';d.propose(queue,root)
    (root/'proposal.json').write_text('{}')
    with pytest.raises(ValueError): d.apply(root)


def test_payload_race_is_not_deferred(tmp_path):
    queue,ids=setup_queue(tmp_path);root=tmp_path/'deferral';d.propose(queue,root)
    with sqlite3.connect(queue) as db:
        db.execute("UPDATE jobs SET payload='{}' WHERE id=?",(ids[0],))
    assert d.apply(root)['unfinished31B']==1


def test_transition_requires_exact_receipt_and_blocks_arbitrary_deferred(tmp_path):
    from dfm12.wave4_gemma31_transition import terminal_database
    queue,ids=setup_queue(tmp_path);root=tmp_path/'deferral';d.propose(queue,root);d.apply(root)
    with sqlite3.connect(queue) as db:
        db.execute("UPDATE jobs SET status='done' WHERE status!='deferred31B'")
    with pytest.raises(ValueError,match='Nonterminal'):
        terminal_database(queue)
    assert terminal_database(queue,root)=={'deferred31B':2,'done':4}
    with sqlite3.connect(queue) as db:
        db.execute("UPDATE jobs SET status='deferred31B' WHERE id=?",(ids[2],))
    with pytest.raises(ValueError,match='Unrecognized'):
        terminal_database(queue,root)


def test_readiness_requires_all_deferral_evidence_pinned(tmp_path,monkeypatch):
    from dfm12 import wave4_gemma31_transition as transition
    from dfm12.io import file_hash
    queue,ids=setup_queue(tmp_path);root=tmp_path/'deferral';d.propose(queue,root);d.apply(root)
    with sqlite3.connect(queue) as db:
        db.execute("UPDATE jobs SET status='done' WHERE status!='deferred31B'")
    monkeypatch.setattr(transition,'alive',lambda _:False)
    contract=dict(cpu_preparation_complete=True,producers_frozen=True,
        databases=[str(queue)],clients_and_producers=[{'pid':123}],
        deferred31B_authorizations={str(queue):str(root)},
        completion_receipts={str(root/'receipt.json'):file_hash(root/'receipt.json')})
    with pytest.raises(ValueError,match='not pinned'):
        transition.readiness(contract)
    for name in ('proposal.json','proposal-seal.json','receipt-seal.json'):
        contract['completion_receipts'][str(root/name)]=file_hash(root/name)
    result=transition.readiness(contract)
    assert result[str(queue)]['deferred31B']==2 and result[str(queue)]['done']==4
