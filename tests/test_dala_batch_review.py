import pytest
from dfm12 import dala_batch_review as b


def pair(text='a'):
    return b.canonical(dict(original=text,corrupted='b'),'Danish')


def result(row,**kw):
    return dict(id=row['id'],**{k:'yes' for k in b.FIELDS},reason='',**kw)


def test_pair_key_ignores_task_and_split_but_retains_content():
    a=dict(original='Good',corrupted='Bad',task='LA',split='train')
    assert b.canonical(a,'en')==b.canonical(dict(a,task='GEC',split='test'),'en')
    assert b.canonical(a,'en')['id']!=b.canonical(a,'da')['id']


def test_missing_and_duplicate_ids_retry_only_affected_rows():
    a,c=pair(),pair('c')
    got,retry=b.decisions(dict(results=[result(a)]),[a,c])
    assert list(got)==[a['id']] and retry==[c['id']]
    got,retry=b.decisions(dict(results=[result(a),result(a),result(c)]),[a,c])
    assert list(got)==[c['id']] and retry==[a['id']]


def test_unexpected_id_rejected_and_wrong_clean_not_passed():
    a=pair(); value=result(a);value['clean_valid']='no'
    assert b.decisions(dict(results=[value]),[a])[0][a['id']]['decision']=='flag'
    got,retry=b.decisions(dict(results=[result(pair('other'))]),[a])
    assert not got and retry==[a['id']]


def test_local_ids_exact_mapping_and_partial_recovery():
    import json
    a,c=pair(),pair('c')
    payload=b.request([a,c])
    assert [r['id'] for r in json.loads(payload['messages'][-1]['content'])]==['0','1']
    x,y=result(a),result(c);x['id']='0';y['id']='01'
    got,retry=b.wire_decisions(dict(results=[x,y]),[a,c])
    assert list(got)==[a['id']] and retry==[c['id']]
    y['id']='1'
    got,retry=b.wire_decisions(dict(results=[x,x,y]),[a,c])
    assert list(got)==[c['id']] and retry==[a['id']]


def test_clean_control_not_scored_as_negative_and_noisy_alt_fails():
    a=b.canonical(dict(original='Fine'),'en','clean_control')
    v=result(a)
    for k in b.FIELDS[1:]:v[k]='not_applicable'
    got,retry=b.decisions(dict(results=[v]),[a])
    assert not retry and got[a['id']]['decision']=='pass'
    a=pair();v=result(a);v['noisy_has_error']='no'
    assert b.decisions(dict(results=[v]),[a])[0][a['id']]['decision']=='flag'


def test_stream_preserves_aliases_and_verifies_hashes(tmp_path):
    import json
    from dfm12.io import file_hash
    from scripts.audit_dala_v2_batches import source_batches
    source=tmp_path/'pairs.jsonl'; receipt=tmp_path/'receipt.json'
    source.write_text(json.dumps(dict(pair_id='original-id',original='Good',corrupted='Bad'))+'\n')
    receipt.write_text('{}')
    spec=dict(component='en:train',language='en',kind='pair',path=str(source),sha256=file_hash(source),
        receipt=str(receipt),receipt_sha256=file_hash(receipt),rows=1,split='train')
    batches=list(source_batches([spec],{'en:train':(-1,False)}))
    _,batch,done=batches[0]
    assert done and batch[0][3]['source_record_id']=='original-id'
    assert batch[0][3]['split']=='train'
    assert not list(source_batches([spec],{'en:train':(0,True)}))
    source.write_text('changed')
    with pytest.raises(ValueError,match='drift'):list(source_batches([spec],{'en:train':(-1,False)}))


def test_larger_source_chunks_resume_without_gaps(tmp_path):
    import json
    from dfm12.io import file_hash
    from scripts.audit_dala_v2_batches import source_batches
    source=tmp_path/'rows.jsonl';receipt=tmp_path/'receipt.json'
    source.write_text(''.join(json.dumps(dict(original=f'Sentence {i}',corrupted='Bad',split='test'))+'\n'
                              for i in range(4100)))
    receipt.write_text('{}')
    spec=dict(component='en:pairs',language='en',kind='pair',path=str(source),sha256=file_hash(source),
              receipt=str(receipt),receipt_sha256=file_hash(receipt),rows=4100,split='from_record')
    batches=list(source_batches([spec],{'en:pairs':(2047,False)}))
    assert [len(b[1]) for b in batches]==[2048,4]
    assert [row[0] for _,batch,_ in batches for row in batch]==list(range(2048,4100))
    assert all(row[3]['split']=='test' for _,batch,_ in batches for row in batch)
    assert batches[-1][2]


def test_bulk_finishes_preserve_owners_and_rollback(tmp_path):
    from dfm12.audit_full import Database
    from scripts.audit_dala_v2_batches import finish_many,read_status
    db=Database(tmp_path/'jobs.sqlite')
    source=dict(component='test',sha256='hash')
    db.register(source)
    db.put(source,[(i,dict(id=str(i)),[]) for i in range(3)])
    jobs=db.claim(3,['endpoint'],0)
    finish_many(db,[(key,owner,attempt,{'decision':'pass'},None) for _,key,_,attempt,owner in jobs[:2]])
    _,key,_,attempt,owner=jobs[2]
    finish_many(db,[(key,'wrong-owner',attempt,{},None)])
    assert dict(read_status(tmp_path/'jobs.sqlite')['jobs'])=={'done':2,'running':1}
    with pytest.raises(TypeError):
        finish_many(db,[(key,owner,attempt,{},None),(key,)])
    assert dict(read_status(tmp_path/'jobs.sqlite')['jobs'])['running']==1
    finish_many(db,[(key,owner,attempt,None,'retry')])
    assert dict(read_status(tmp_path/'jobs.sqlite')['jobs'])=={'done':2,'pending':1}
    db.close()
