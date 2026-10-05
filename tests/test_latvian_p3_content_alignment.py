import json
import numpy as np
from dfm12 import latvian_p3_content_alignment as m
from dfm12.jobs import Queue


def test_ranking_independent_of_source_ordinals():
    vectors=np.array([[1.,0.],[0.,1.],[.5,.5]])
    indices,_=m.rank(vectors,np.array([0.,1.]),['a','b','c'])
    perm=[2,0,1];other,_=m.rank(vectors[perm],np.array([0.,1.]),['c','a','b'])
    assert [['a','b','c'][i] for i in indices]==[['c','a','b'][i] for i in other]


def test_chunks_never_truncate():
    ids=list(range(2049))
    assert sum(m.chunks(ids),[])==ids
    assert max(map(len,m.chunks(ids)))<=480


def test_explicit_verified_xlmr_frame_without_legacy_api():
    from types import SimpleNamespace
    tokenizer=SimpleNamespace(bos_token_id=0,eos_token_id=2,
        encode=lambda text,add_special_tokens: [0,4,2] if add_special_tokens else [4])
    assert m.wrap_xlmr(tokenizer,[5,6])==[0,5,6,2]


def test_uncertainty_is_not_probability_from_similarity():
    result=m.uncertainty('2010?', [dict(question='2011?'),dict(question='2010?')], [.99,.985])
    assert result['near_tie'] and result['numeric_anchor_mismatch']
    assert result['probability_interval']==[0.,1.] and not result['verified']


def test_durable_idempotent_queue_lease_retry(tmp_path):
    path=tmp_path/'queue.sqlite'; q=Queue(path)
    packet=dict(id='row',messages=[dict(role='assistant',content='complete '*1000)],
        source_alignment_status='content_ranked_proposals_unverified',admission_authorized=False)
    key,payload=m.queue_record(q,packet);assert m.queue_record(q,packet)[0]==key
    assert json.loads(payload['request']['messages'][1]['content'])==packet
    assert payload['request']['model']=='google/gemma-4-31B-it'
    claimed=q.claim(m.STAGE,'test-owner');assert claimed[0]==key
    q.finish(key,'test-owner',claimed[2]+1,error='retry fixture');q.close()
    q=Queue(path)
    again=q.claim(m.STAGE,'second-owner');assert again[0]==key and again[2]==1
    q.finish(key,'second-owner',again[2]+1,result=dict(alignment='uncertain',keep=False));q.close()


def test_wilson_bounds_finite_at_extremes():
    assert m.wilson(0,0)==[0.,1.]
    assert 0<m.wilson(20,20)[0]<1
    assert 0<m.wilson(0,20)[1]<1
