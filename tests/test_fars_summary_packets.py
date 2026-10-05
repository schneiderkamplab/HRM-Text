import json
import sqlite3

import pytest

from dfm12 import fars_summary_packets as p
from dfm12.io import load, write_json


def record(component=p.COMPONENTS[0]):
    return dict(id='old', component=component, rendered_tokens=10,
        messages=[dict(role='user',content='full article'),dict(role='assistant',content='old summary')],
        provenance=dict(repo='ParsiAI/FarsInstruct',revision='r',file='source.parquet',row=0))


def test_packet_preserves_full_source_and_prompt():
    r = record()
    upstream = dict(inputs='full article',outputs='original target',template='summarize_the_article')
    packet = p.packet(p.COMPONENTS[0], 'old', json.dumps(r), 'accepted', upstream, {})
    assert packet['candidate'] == r
    assert packet['upstream_record'] == upstream
    assert packet['audit_request']['model'] == p.MODEL
    assert not packet['publication_allowed']
    upstream['inputs'] = 'changed'
    with pytest.raises(ValueError, match='drift'):
        p.packet(p.COMPONENTS[0], 'old', json.dumps(r), 'accepted', upstream, {})


def test_repair_and_fresh_review_are_separate():
    packet = dict(candidate=record(), upstream_record={'inputs':'full article'})
    review = dict(reason='wrong number',verdict='repair',prompt_mismatch=False)
    assert p.repair_request(packet,review)['model'] == p.MODEL
    fresh = p.fresh_reaudit_request(packet,'correct summary')
    assert 'wrong number' not in fresh['messages'][1]['content']
    assert packet['candidate']['messages'][-1]['content'] == 'old summary'
    for verdict in ('keep','reject','needs_verification'):
        with pytest.raises(ValueError):
            p.repair_request(packet,dict(review,verdict=verdict))
    with pytest.raises(ValueError):
        p.repair_request(packet,dict(review,prompt_mismatch=True))


def test_completed_generation_is_not_acceptance():
    old = record()
    messages = [old['messages'][0],dict(role='assistant',content='corrected')]
    candidate = p.completed_repair(old,dict(status='corrected',messages=messages))
    assert 'rendered_tokens' not in candidate
    assert candidate['admission_authorized'] is False
    assert candidate['provenance']['repair_parent'] == 'old'
    assert old['messages'][-1]['content'] == 'old summary'
    messages[0] = dict(role='user',content='weakened prompt')
    with pytest.raises(ValueError):
        p.completed_repair(old,dict(status='corrected',messages=messages))


def test_resumable_snapshot_includes_unmaterialized_repairs(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    wave, downloads, root = tmp_path/'wave',tmp_path/'downloads',tmp_path/'packets'
    downloads.mkdir()
    write_json(downloads/'wave4-download.json',dict(repo='ParsiAI/FarsInstruct',revision='r'))
    pq.write_table(pa.Table.from_pylist([dict(inputs='full article',outputs='old summary',
        template='summarize_the_article')]), downloads/'source.parquet')
    for component in p.COMPONENTS:
        folder = wave/'release'/component
        folder.mkdir(parents=True)
        with sqlite3.connect(folder/'ledger.sqlite') as db:
            db.execute('CREATE TABLE rows(id,record,status,repair_job,reaudit_job)')
            if component == p.COMPONENTS[0]:
                db.execute('INSERT INTO rows VALUES(?,?,?,?,?)',('old',json.dumps(record()),'accepted',None,None))
    (wave/'repair').mkdir()
    with sqlite3.connect(wave/'repair/jobs.sqlite') as db:
        db.execute('CREATE TABLE jobs(id,stage,payload,status,attempts,owner,lease,result,error)')
        result = dict(status='corrected',messages=[record()['messages'][0],dict(role='assistant',content='new summary')])
        db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',('job','generate',json.dumps({'record':record()}),'done',1,'old',None,json.dumps(result),None))
    first = p.prepare(root,wave,downloads,limit=1)
    assert first['total'] == 2 and first['accounted'] == 1
    second = p.prepare(root,wave,downloads,limit=2)
    assert second['remaining'] == 0
    assert p.prepare(root,wave,downloads,limit=2)['last_batch'] == 0
    assert any(x['disposition']=='staged_for_31B' for x in second['queue_snapshot'])
    with sqlite3.connect(wave/'repair/jobs.sqlite') as db:
        assert db.execute('SELECT status FROM jobs').fetchone()[0] == 'done'
    with sqlite3.connect(root/'snapshot.sqlite') as db:
        db.execute("UPDATE candidates SET status='tampered'")
    with pytest.raises(ValueError, match='Snapshot drift'):
        p.verify(root)
