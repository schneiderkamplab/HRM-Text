import importlib.util
from pathlib import Path
import json
import sqlite3
import copy
import pytest

P=Path(__file__).resolve().parents[1]/'scripts/dfm13_arena_export_readiness.py'
spec=importlib.util.spec_from_file_location('export_guard_test',P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture(tmp_path, kind='repaired', terminal=True):
    ledger=tmp_path/'ledger.sqlite'
    source_root=tmp_path/'source';source_root.mkdir()
    data=tmp_path/'original.jsonl'
    original=dict(id='source-id',target_message_index=1,tools=[{'name':'preserve'}],
                  messages=[{'role':'user','content':'question'},{'role':'assistant','content':'original'}])
    data.write_text(json.dumps(original)+'\n')
    source=dict(path=str(data),sha256=m.file_hash(data))
    source_status='invalid_response' if kind=='recovered' else 'complete'
    audit=dict(seq=9,source_line=1,source_id=original['id'],source_sha256=source['sha256'],row_sha256=m.digest(original),
               result=dict(reason='original reason',verdict='keep' if kind=='original' else 'repair'))
    if kind=='recovered':audit.pop('result')
    manifest=dict(total=1,sources=[source])
    m.write_json(source_root/'manifest.json',manifest)
    m.write_json(source_root/'seal.json',dict(manifest_sha256=m.file_hash(source_root/'manifest.json')))
    (source_root/'controller.lock').touch()
    with sqlite3.connect(source_root/'ledger.sqlite') as db:
        db.execute('CREATE TABLE jobs(seq INTEGER,source INTEGER,source_id TEXT,offset INTEGER,length INTEGER,status TEXT,result TEXT,line INTEGER)')
        db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)',(9,0,original['id'],0,data.stat().st_size,source_status,json.dumps(audit),1))
        db.commit()
        with sqlite3.connect(tmp_path/'input.sqlite') as target:db.backup(target)
    m.write_json(tmp_path/'snapshot.json',dict(sha256=m.file_hash(tmp_path/'input.sqlite')))
    m.write_json(tmp_path/'plan.json',dict(source=str(source_root),manifest=manifest,
        pins={str(source_root/n):m.file_hash(source_root/n) for n in ('manifest.json','seal.json')}))
    m.write_json(tmp_path/'seal.json',dict(sha256=m.file_hash(tmp_path/'plan.json')))
    (tmp_path/'controller.lock').touch()
    decision=dict(reason='recovered reason',verdict='keep') if kind=='recovered' else audit['result']
    record=dict(seq=9,source_line=1,source=source,source_id=original['id'],original_audit=audit,
                original_row_sha256=m.digest(original),decision=decision)
    stages=[]
    if kind=='recovered':stages=[('retry_audit',decision)]
    if kind=='repaired':
        candidate=copy.deepcopy(original);candidate['messages'][1]['content']='corrected'
        record.update(candidate=candidate,candidate_sha256=m.digest(candidate),
            correction=dict(reason='correct',status='corrected',content='corrected'),
            fresh_reaudit=dict(reason='checked',verdict='keep'))
        stages=[('correction',record['correction']),('fresh_reaudit',record['fresh_reaudit'])]
    h=record.get('candidate_sha256',m.digest(original))
    with sqlite3.connect(ledger) as db:
        for table in ('accepted','rejected','needs_review'):
            db.execute(f'CREATE TABLE {table}(seq INTEGER PRIMARY KEY,record TEXT)')
        db.execute('CREATE TABLE attempts(seq INTEGER,stage TEXT,n INTEGER,status TEXT,hash TEXT,record TEXT)')
        for stage,result in stages:
            request_hash=m.digest([9,stage])
            attempt=dict(seq=9,stage=stage,attempt=1,status='complete',finish_reason='stop',
                         request_sha256=request_hash,raw_request_id='saved-raw-id',result=result)
            db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?)',(9,stage,1,'complete',request_hash,json.dumps(attempt)))
        db.execute('INSERT INTO accepted VALUES(?,?)',(9,json.dumps(record)))
    if terminal:m.write_json(tmp_path/'complete.json',dict(counts=dict(accepted=1,rejected=0,needs_review=0)))
    if kind=='original':ledger=source_root/'ledger.sqlite'
    holds=dict(schema='dfm13-independent-quality-holds-v1',holds=[dict(disposition='hard_hold',
        ledger=str(ledger),seq=9,source_id=original['id'],candidate_sha256=h,reason='Known factual defect',release_authorized=False)])
    # The caller's selection digest is not necessarily a field in unchanged accepted records.
    record=copy.deepcopy(record);record['candidate_sha256']=h
    return ledger,record,holds


def test_hard_hold_overrides_fresh_keep(tmp_path):
    ledger,record,holds=fixture(tmp_path)
    selection={'candidates':[dict(seq=9,candidate_sha256=record['candidate_sha256'])]}
    assert m.check_selection(ledger,selection,holds)


def test_verification_hold_also_blocks(tmp_path):
    ledger,record,holds=fixture(tmp_path)
    holds['holds'][0]['disposition']='verification_hold'
    assert m.blocked(record,ledger,holds)


def test_all_six_confirmed_candidates_are_held():
    holds=m.load(m.HOLDS)
    assert {h['seq'] for h in holds['holds']} >= {9,2606,2609,2613,2616,2632}
    numerical=next(h for h in holds['holds'] if h['seq']==2616)
    assert numerical['disposition']=='hard_hold'
    assert numerical['candidate_sha256']=='985077936c169d07de8c68e22ed0d375736c88ece28aa9941921cd324b1f572a'
    for h in holds['holds']:
        assert m.blocked(dict(seq=h['seq'],candidate_sha256=h['candidate_sha256']),h['ledger'],holds)


def test_original_keep_three_hash_holds():
    holds=m.load(m.HOLDS)
    originals=[h for h in holds['holds'] if h.get('candidate_kind')=='original']
    assert {h['seq'] for h in originals}=={945,60542,141981}
    for hold in originals:
        assert m.blocked(dict(seq=hold['seq'],candidate_sha256=hold['candidate_sha256']),hold['ledger'],holds)


def test_original_source_bytes_checked_and_held(tmp_path):
    ledger,record,holds=fixture(tmp_path,'original')
    data=tmp_path/'original.jsonl'
    selection=dict(candidates=[dict(seq=9,kind='original',candidate_sha256=record['candidate_sha256'])])
    assert m.check_selection(ledger,selection,holds)
    data.write_text('{}\n')
    with pytest.raises(ValueError):
        m.check_selection(ledger,selection,holds)


def test_changed_hash_does_not_release_same_source(tmp_path):
    ledger,record,holds=fixture(tmp_path)
    record['candidate_sha256']='new hash'
    assert m.blocked(record,ledger,holds)


def test_held_bytes_block_cross_ledger_copy(tmp_path):
    ledger,record,holds=fixture(tmp_path)
    record['seq']=100
    assert m.blocked(record,tmp_path/'other.sqlite',holds)


def test_candidate_hash_drift_rejected(tmp_path):
    ledger,record,holds=fixture(tmp_path)
    with pytest.raises(ValueError,match='hash drift'):
        m.check_selection(ledger,dict(candidates=[dict(seq=9,candidate_sha256='wrong')]),holds)


def test_readiness_blocks_and_detects_hold_file_drift(tmp_path):
    ledger,record,holds=fixture(tmp_path)
    hp=tmp_path/'holds.json'; selection=tmp_path/'selection.json'; assessment=tmp_path/'assessment.md'
    m.write_json(hp,holds)
    m.write_json(selection,dict(candidates=[dict(seq=9,candidate_sha256=record['candidate_sha256'])]))
    assessment.write_text('Independent sample, not whole-corpus certification.')
    receipt=tmp_path/'readiness.json'
    value=m.prepare(ledger,selection,receipt,holds_path=hp,assessment_path=assessment)
    assert value['status']=='blocked_independent_hold'
    with pytest.raises(ValueError,match='Export blocked'):
        m.enforce(receipt)
    hp.write_text('{}')
    with pytest.raises(ValueError,match='pin drift'):
        m.enforce(receipt)


def test_unheld_still_requires_manual_review(tmp_path):
    ledger,record,holds=fixture(tmp_path)
    hp=tmp_path/'holds.json'; selection=tmp_path/'selection.json'; assessment=tmp_path/'assessment.md'
    m.write_json(hp,dict(holds,holds=[]))
    m.write_json(selection,dict(candidates=[dict(seq=9,candidate_sha256=record['candidate_sha256'])]))
    assessment.write_text('Manual assessment pending.')
    receipt=tmp_path/'readiness.json'
    value=m.prepare(ledger,selection,receipt,holds_path=hp,assessment_path=assessment)
    assert value['status']=='manual_quality_review_required'
    with pytest.raises(ValueError,match='Export blocked'):
        m.enforce(receipt)


@pytest.mark.parametrize('kind',['original','recovered','repaired'])
def test_explicit_classification_and_holds_all_paths(tmp_path,kind):
    ledger,record,holds=fixture(tmp_path,kind)
    evidence={}
    selection=dict(candidates=[dict(seq=9,kind=kind,candidate_sha256=record['candidate_sha256'])])
    assert m.check_selection(ledger,selection,holds,evidence)
    assert evidence['classifications'][kind]==1
    assert sum(evidence['classifications'].values())==1
    assert len(evidence['selection_evidence_sha256'])==64
    assert not m.check_selection(ledger,selection,dict(holds,holds=[]))


@pytest.mark.parametrize('change', ['missing','invalid','result','request_hash'])
def test_recovered_requires_completed_matching_attempt(tmp_path,change):
    ledger,record,holds=fixture(tmp_path,'recovered')
    with sqlite3.connect(ledger) as db:
        if change=='missing':db.execute('DELETE FROM attempts')
        elif change=='invalid':db.execute("UPDATE attempts SET status='invalid_response'")
        elif change=='request_hash':db.execute("UPDATE attempts SET hash='wrong'")
        else:
            attempt=json.loads(db.execute('SELECT record FROM attempts').fetchone()[0])
            attempt['result']['verdict']='reject'
            db.execute('UPDATE attempts SET record=?',(json.dumps(attempt),))
    with pytest.raises(ValueError,match='retry_audit'):
        m.check_selection(ledger,dict(candidates=[dict(seq=9,kind='recovered',candidate_sha256=record['candidate_sha256'])]),holds)


@pytest.mark.parametrize('change',['history','tools','target'])
def test_repaired_content_only_not_rehashed_context_changes(tmp_path,change):
    ledger,record,holds=fixture(tmp_path)
    if change=='history':record['candidate']['messages'][0]['content']='changed'
    elif change=='tools':record['candidate']['tools']=[]
    else:record['candidate']['target_message_index']=0
    record['candidate_sha256']=m.digest(record['candidate'])
    with sqlite3.connect(ledger) as db:db.execute('UPDATE accepted SET record=?',(json.dumps(record),))
    with pytest.raises(ValueError,match='history/tools'):
        m.check_selection(ledger,dict(candidates=[dict(seq=9,kind='repaired',candidate_sha256=record['candidate_sha256'])]),holds)


def test_original_keep_cannot_be_mislabeled_recovered(tmp_path):
    ledger,record,holds=fixture(tmp_path,'original')
    repair_ledger=tmp_path/'ledger.sqlite'
    with pytest.raises(ValueError,match='recovered unchanged'):
        m.check_selection(repair_ledger,dict(candidates=[dict(seq=9,kind='recovered',candidate_sha256=record['candidate_sha256'])]),holds)


def test_conflicting_terminal_disposition_fails_closed(tmp_path):
    ledger,record,holds=fixture(tmp_path,'recovered')
    with sqlite3.connect(ledger) as db:db.execute('INSERT INTO rejected VALUES(?,?)',(9,'{}'))
    with pytest.raises(ValueError,match='Conflicting'):
        m.check_selection(ledger,dict(candidates=[dict(seq=9,kind='recovered',candidate_sha256=record['candidate_sha256'])]),holds)


def test_sample_review_not_per_row_gold_but_terminal_and_hash_bound(tmp_path):
    ledger,record,holds=fixture(tmp_path,'recovered')
    hp=tmp_path/'holds.json';selection=tmp_path/'selection.json';assessment=tmp_path/'assessment.md'
    manual=tmp_path/'review.json';output=tmp_path/'readiness.json'
    m.write_json(hp,dict(holds,holds=[]))
    m.write_json(selection,dict(candidates=[dict(seq=9,kind='recovered',candidate_sha256=record['candidate_sha256'])]))
    assessment.write_text('Assistant sample spot-check; not certified accuracy.')
    review=dict(approved=True,whole_target_reviewed=True,terminal_review=True,reviewer='test reviewer',
        review_scope='sample',sample_basis=dict(method='source-stratified',reviewed_count=1,population_count=1,
        limitations='Small sample; no population accuracy estimate or certification.'),
        selection_sha256=m.file_hash(selection),holds_sha256=m.file_hash(hp),assessment_sha256=m.file_hash(assessment))
    m.write_json(manual,review)
    result=m.prepare(ledger,selection,output,manual,holds_path=hp,assessment_path=assessment)
    assert result['status']=='ready_for_separate_export_authorization'
    assert result['quality_certified'] is False
    assert result['export_authorized'] is False
    assert m.enforce(output)['classifications']['recovered']==1
    (tmp_path/'complete.json').unlink()
    with pytest.raises(ValueError,match='not terminal'):
        m.enforce(output)


def test_sample_without_basis_not_approved(tmp_path):
    assert not m.review_matches(dict(approved=True,review_scope='sample'),tmp_path/'missing',tmp_path/'missing',tmp_path/'missing',20)


def test_live_root_not_ready_even_for_valid_candidate(tmp_path):
    ledger,record,holds=fixture(tmp_path,'recovered',terminal=False)
    hp=tmp_path/'holds.json';selection=tmp_path/'selection.json';assessment=tmp_path/'assessment.md'
    m.write_json(hp,dict(holds,holds=[]))
    m.write_json(selection,dict(candidates=[dict(seq=9,kind='recovered',candidate_sha256=record['candidate_sha256'])]))
    assessment.write_text('Sample only.')
    result=m.prepare(ledger,selection,tmp_path/'readiness.json',holds_path=hp,assessment_path=assessment)
    assert result['status']=='terminal_review_required'


def test_terminal_lock_held_is_not_ready(tmp_path):
    ledger,_,_=fixture(tmp_path,'recovered')
    with (tmp_path/'controller.lock').open('rb') as handle:
        m.fcntl.flock(handle,m.fcntl.LOCK_EX|m.fcntl.LOCK_NB)
        assert not m.terminal_ready(ledger)


def test_next_repair_holds_are_explicit():
    holds=m.load(m.HOLDS)
    next_holds=[h for h in holds['holds'] if 'pending-next-repairs' in h['ledger']]
    assert {h['seq']:h['disposition'] for h in next_holds}=={49:'verification_hold',89:'hard_hold'}


@pytest.mark.parametrize('field',['source_id','source_line','original_row_sha256'])
def test_recovered_provenance_mismatch(tmp_path,field):
    ledger,record,holds=fixture(tmp_path,'recovered')
    with sqlite3.connect(ledger) as db:
        actual=json.loads(db.execute('SELECT record FROM accepted').fetchone()[0])
        actual[field]='wrong'
        db.execute('UPDATE accepted SET record=?',(json.dumps(actual),))
    with pytest.raises(ValueError,match='provenance drift'):
        m.check_selection(ledger,dict(candidates=[dict(seq=9,kind='recovered',candidate_sha256=record['candidate_sha256'])]),holds)


def test_snapshot_drift_rejected(tmp_path):
    ledger,record,holds=fixture(tmp_path,'recovered')
    with sqlite3.connect(tmp_path/'input.sqlite') as db:db.execute("UPDATE jobs SET source_id='changed'")
    with pytest.raises(ValueError,match='snapshot drift'):
        m.check_selection(ledger,dict(candidates=[dict(seq=9,kind='recovered',candidate_sha256=record['candidate_sha256'])]),holds)
