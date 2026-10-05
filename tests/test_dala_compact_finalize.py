import json
import gzip
import sqlite3
from pathlib import Path
import pytest
from dfm12 import dala_compact_finalize as p


def row():
    return dict(language='en', original='This is correct.', corrupted='This are correct.',
                split='train', view='representative', document_id='doc')


def decision(record):
    return dict(id=record['id'], decision='pass', reason='Agreement error.', raw_request_id='raw1',
                producer_v2_audit_equivalent=False,
                **{k:'yes' if i == 0 or record['kind'] == 'pair' else 'not_applicable'
                   for i,k in enumerate(p.FIELDS)})


@pytest.mark.parametrize('kind', ['pair','clean_control'])
def test_compact_pass_and_labels(kind):
    r = row(); c = p.canonical(r,'en',kind); d = decision(c)
    assert p.accepted(c,d,'done')
    for state in ('pending','running','failed'):
        assert not p.accepted(c,d,state)
    for task in ('acceptability','correction'):
        output = p.task_row(r,c,task,{task:'Prompt'}, {'contract':p.CONTRACT})
        expected = r['original'] if task == 'correction' else ('yes' if kind == 'clean_control' else 'no')
        assert output['messages'][-1]['content'] == expected
        assert not output['producer_v2_audit_equivalent']


@pytest.mark.parametrize('change', [dict(decision='review'),dict(clean_valid='uncertain'),
    dict(reason=''),dict(raw_request_id=''),dict(id='wrong'),dict(producer_v2_audit_equivalent=True)])
def test_invalid_pass_excluded(change):
    c=p.canonical(row(),'en','pair')
    assert not p.accepted(c,dict(decision(c),**change),'done')


def test_split_guard():
    for split in ('train','validation','test'):
        assert p.split_name(dict(row(),split=split)) == split+'_representative'
    with pytest.raises(ValueError): p.split_name(dict(row(),split='val'))
    with pytest.raises(ValueError): p.split_name(dict(row(),view='challenge'))


@pytest.mark.parametrize('status,terminal', [('done',True),('failed',True),('running',False),('pending',False)])
def test_snapshot_requires_terminal_and_preserves_source(tmp_path,status,terminal):
    audit=tmp_path/'audit'; audit.mkdir()
    p.write_json(audit/'config.json',{'model':'teacher'})
    r=row(); c=p.canonical(r,'en','pair')
    with sqlite3.connect(audit/'jobs.sqlite') as db:
        db.executescript('CREATE TABLE sources(component,sha256,complete,input_rows,quarantined); CREATE TABLE jobs(id,record,status,result); CREATE TABLE aliases(component,ordinal,id,provenance);')
        db.execute('INSERT INTO sources VALUES(?,?,?,?,?)',('en:pairs','sha',1,1,0))
        db.execute('INSERT INTO jobs VALUES(?,?,?,?)',(c['id'],json.dumps(c),status,json.dumps(decision(c))))
        db.execute('INSERT INTO aliases VALUES(?,?,?,?)',('en:pairs',0,c['id'],json.dumps({'row_sha256':p.digest(r)})))
    old=p.file_hash(audit/'jobs.sqlite')
    result=p.snapshot(audit,[dict(component='en:pairs',sha256='sha',rows=1)],tmp_path/'snapshot')
    assert (result is not None) == terminal
    assert p.file_hash(audit/'jobs.sqlite') == old
    assert (tmp_path/'snapshot/snapshot.json').exists() == terminal


def test_prior_heldout_and_duplicate_control(tmp_path):
    prior=sqlite3.connect(':memory:'); held=sqlite3.connect(':memory:')
    prior.executescript('CREATE TABLE pairs(key);CREATE TABLE clean(key);CREATE TABLE texts(key,split);CREATE TABLE documents(key,split);')
    held.executescript('CREATE TABLE held(kind,key);CREATE TABLE seen(kind,key);')
    r=row()
    held.execute('INSERT INTO held VALUES(?,?)',('document','doc'))
    assert p.exclusion(r,'pair',prior,held) == 'raw_heldout_overlap'
    held.execute('DELETE FROM held')
    assert p.exclusion(r,'clean_control',prior,held) is None
    assert p.exclusion(r,'clean_control',prior,held) == 'duplicate_control_or_noisy_input'
    prior.execute('INSERT INTO pairs VALUES(?)',(p.digest([p.text_key(r['original']),p.text_key(r['corrupted'])]),))
    assert p.exclusion(r,'pair',prior,held) == 'prior_duplicate'


def test_cpu_export_end_to_end_keeps_eval_out_of_train(tmp_path,monkeypatch):
    audit=tmp_path/'audit'; audit.mkdir()
    root=tmp_path/'export'; source=tmp_path/'source'; source.mkdir()
    prior=tmp_path/'prior.sqlite'
    with sqlite3.connect(prior) as db:
        db.executescript('CREATE TABLE pairs(key);CREATE TABLE clean(key);CREATE TABLE texts(key,split);CREATE TABLE documents(key,split);')
    sha=p.file_hash(prior)
    p.write_json(source/'identity.json',{'prior_index_sha256':sha})
    p.write_json(audit/'config.json',{'model':'teacher'})
    rows=[dict(row(),document_id='doc'+str(i),split=split,
               original='Sentence '+str(i)+' is correct.',corrupted='Sentence '+str(i)+' are correct.')
          for i,split in enumerate(('train','validation','test'))]
    path=source/'pairs.jsonl.gz'
    with gzip.open(path,'wt') as f:
        for r in rows:f.write(json.dumps(r)+'\n')
    spec=dict(component='en:pairs',language='en',kind='pair',path=str(path),sha256=p.file_hash(path),rows=3)
    with sqlite3.connect(audit/'jobs.sqlite') as db:
        db.executescript('CREATE TABLE sources(component,sha256,complete,input_rows,quarantined); CREATE TABLE jobs(id,record,status,result); CREATE TABLE aliases(component,ordinal,id,provenance);')
        db.execute('INSERT INTO sources VALUES(?,?,?,?,?)',('en:pairs',spec['sha256'],1,3,0))
        for i,r in enumerate(rows):
            c=p.canonical(r,'en','pair')
            db.execute('INSERT INTO jobs VALUES(?,?,?,?)',(c['id'],json.dumps(c),'done',json.dumps(decision(c))))
            db.execute('INSERT INTO aliases VALUES(?,?,?,?)',('en:pairs',i,c['id'],json.dumps({'row_sha256':p.digest(r)})))
    p.snapshot(audit,[spec],root)
    monkeypatch.setattr(p,'inventory_for',lambda *a: (dict(prior_release=dict(path=str(prior),sha256=sha),
        profile=dict(prompts={'acceptability':'Correct?','correction':'Correct this.'})),{}))
    result=p.finalize((str(root),[spec],False))
    assert result['status']=='exported_not_tokenized' and result['components']==[]
    export=p.load(root/'export.json')
    assert export['counts']['train:acceptability']==1
    for task in ('acceptability','correction'):
        assert len(list((root/'exports'/task).glob('*.gz')))==3
        with gzip.open(root/'train'/task/'part-00000.jsonl.gz','rt') as f:
            training=[json.loads(line) for line in f]
        assert len(training)==1 and training[0]['split']=='train'
