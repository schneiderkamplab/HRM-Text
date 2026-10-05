import io
import json
from pathlib import Path

import pytest

from dfm12.baltic_sources_cpu import p3_messages, speech_rows
from dfm12.baltic_transforms import transform, input_rows, clean_window
from dfm12.baltic_pivots import texts
from dfm12.baltic_audit import queue, finalize, index_queue
from dfm12.jobs import Queue
from dfm12.io import file_hash, load, write_json
from scripts.prepare_dfm13_baltic import records


def test_p3_incorrect_rank_rejected():
    row=dict(inputs_pretokenized='Question',targets_pretokenized='Answer',is_correct=False)
    with pytest.raises(ValueError,match='incorrect_rank'):
        p3_messages(row)
    row['is_correct']=True
    assert p3_messages(row)[-1]['content']=='Answer'


def test_parlamint_preserves_speech_and_paragraphs():
    xml=b'<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><u xml:id="a" who="#x"><seg>First.</seg><seg>Second <hi>paragraph</hi>.</seg></u><u xml:id="b"><seg>Other speech.</seg></u></text></TEI>'
    result=list(speech_rows(io.BytesIO(xml),'test.xml'))
    assert len(result)==2
    assert result[0]['text']=='First.\n\nSecond paragraph.'
    assert result[0]['speaker']=='#x'


@pytest.mark.parametrize('lang',['lt','lv'])
@pytest.mark.parametrize('task',['denoising','span-filling','prefix-continuation','paragraph-reordering'])
def test_native_transform_contract(lang,task):
    text='\n\n'.join(('A'+str(i)+' sentence with many distinct words. ')*8 for i in range(3))
    row=transform(text,lang,task,{'source':'test'})
    assert row['language']==lang
    assert row['audit_context']['original']==text
    assert row['messages'][1]['content']
    if task in {'denoising','paragraph-reordering'}:
        assert row['messages'][1]['content']==text


def test_csv_embedded_newlines(tmp_path):
    p=tmp_path/'test.csv'
    p.write_text('text,summary_abstract\n"one\ntwo","short, summary"\n')
    assert list(records(p))==[{'text':'one\ntwo','summary_abstract':'short, summary'}]


def test_sitting_sampling_spans_document(tmp_path):
    p=tmp_path/'docs.jsonl'
    p.write_text(json.dumps({'text':'\n'.join(str(i)+' sentence. '*100 for i in range(20))})+'\n')
    out=list(input_rows(p,'Europarl_lt'))
    assert len(out)>1
    assert '19 sentence.' in out[-1]['text']


def test_pivot_reads_actual_text_not_instruction():
    row=dict(language='lt',reverse_language='en',messages=[{'content':'prompt'},{'content':'target'}],
             reverse_messages=[{'content':'prompt'},{'content':'source'}])
    assert texts(row)=={'en':'source','lt':'target'}


def test_queue_is_idempotent_and_deduplicates(tmp_path):
    row=dict(id='one',language='lt',task='instruction',messages=[
        dict(role='user',content='Q'),dict(role='assistant',content='A')])
    p=tmp_path/'rows.jsonl'
    p.write_text(json.dumps(row)+'\n')
    for stage in ['instructions','transforms','translations']:
        write_json(tmp_path/'audit-ready'/f'{stage}-manifest.json',[
            dict(component=stage,path=str(p),sha256=file_hash(p))])
    queue(tmp_path)
    assert load(tmp_path/'audit/manifest.json')['total_unique_jobs']==1
    queue(tmp_path)
    assert load(tmp_path/'audit/manifest.json')['total_unique_jobs']==1
    assert load(tmp_path/'audit/manifest.json')['new_jobs']==0
    report=load(tmp_path/'audit/manifest.json')
    assert len(report['preflight_manifests'])==3


def test_finalize_rejects_changed_preflight(tmp_path):
    manifest=tmp_path/'audit-ready/translations-manifest.json'
    write_json(manifest,[])
    write_json(tmp_path/'audit/manifest.json',dict(preflight_manifests={str(manifest):file_hash(manifest)}))
    write_json(manifest,[{'changed':True}])
    with pytest.raises(ValueError,match='Preflight changed'):
        finalize(tmp_path)


def test_queue_ensures_component_jobs_without_resetting_failed_records(tmp_path):
    entries=[]
    for component in ['first', 'second']:
        row=dict(id='shared',component=component,messages=[
            dict(role='user',content='Q'),dict(role='assistant',content='A')])
        path=tmp_path/f'{component}.jsonl'
        path.write_text(json.dumps(row)+'\n')
        entries.append(dict(component=component,path=str(path),sha256=file_hash(path)))
    for stage in ['instructions','transforms','translations']:
        write_json(tmp_path/'audit-ready'/f'{stage}-manifest.json',
                   entries if stage=='translations' else [])
    queue(tmp_path)
    report=load(tmp_path/'audit/manifest.json')
    assert report['total_unique_jobs']==2
    assert report['total_candidate_ids']==1
    assert report['new_jobs']==2
    q=Queue(tmp_path/'audit/jobs.sqlite')
    try:
        ids=[row[0] for row in q.db.execute('SELECT id FROM jobs ORDER BY id')]
        q.db.execute("UPDATE jobs SET status='failed',attempts=4,error='preserved' WHERE id=?",(ids[0],))
        q.db.execute('DELETE FROM jobs WHERE id=?',(ids[1],))
        before=q.db.execute('SELECT * FROM jobs WHERE id=?',(ids[0],)).fetchone()
    finally:
        q.close()
    queue(tmp_path)
    assert load(tmp_path/'audit/manifest.json')['new_jobs']==1
    queue(tmp_path)
    report=load(tmp_path/'audit/manifest.json')
    assert report['new_jobs']==0
    assert report['total_unique_jobs']==2
    assert all(item['exact_payload_jobs_ensured']==1 for item in report['component_job_coverage'])
    q=Queue(tmp_path/'audit/jobs.sqlite')
    try:
        assert q.db.execute('SELECT * FROM jobs WHERE id=?',(ids[0],)).fetchone()==before
    finally:
        q.close()


def test_queue_rejects_candidate_id_collision(tmp_path):
    paths=[]
    for i in range(2):
        p=tmp_path/f'{i}.jsonl'
        p.write_text(json.dumps(dict(id='same',messages=[
            dict(role='user',content='Q'),dict(role='assistant',content=str(i))]))+'\n')
        paths.append(dict(component=str(i),path=str(p),sha256=file_hash(p)))
    for stage in ['instructions','transforms','translations']:
        write_json(tmp_path/'audit-ready'/f'{stage}-manifest.json',paths if stage=='instructions' else [])
    with pytest.raises(ValueError,match='ID collision'):
        queue(tmp_path)


def test_audit_indexes_preserve_claim_order(tmp_path):
    path=tmp_path/'jobs.sqlite'
    q=Queue(path)
    first=q.add('audit',{'n':1})
    second=q.add('audit',{'n':2})
    index_queue(path)
    q.close()
    q=Queue(path)
    detail=str(q.db.execute("EXPLAIN QUERY PLAN SELECT id FROM jobs WHERE stage='audit' AND status='pending' AND attempts<4 ORDER BY rowid LIMIT 1").fetchall())
    assert 'baltic_job_claim' in detail
    assert q.claim('audit','worker')[0]==first
    assert q.claim('audit','worker')[0]==second
    q.close()
