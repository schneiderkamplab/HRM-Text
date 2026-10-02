import importlib.util
from pathlib import Path
import pytest

P=Path(__file__).resolve().parents[1]/'scripts/dfm13_arena_next_audit.py'
spec=importlib.util.spec_from_file_location('next_audit_test',P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def receipt(name='prism'):
    return dict(name=name,status='ready',license_cleared=True,heldout_overlap_cleared=True,
                input_sha256='abc',evidence=[dict(path='decision.json',sha256='def')])


def test_prism_requires_explicit_clearance():
    entry=receipt()
    entry['license_cleared']=False
    with pytest.raises(ValueError,match='license/overlap'):
        m.eligible(dict(sources=[dict(name='prism',sha256='abc')]),dict(sources=[entry]))


@pytest.mark.parametrize('field',['license_cleared','heldout_overlap_cleared','evidence'])
def test_missing_gate_fails(field):
    entry=receipt()
    del entry[field]
    with pytest.raises(ValueError):
        m.eligible(dict(sources=[dict(name='prism',sha256='abc')]),dict(sources=[entry]))


def test_ready_only():
    inventory=dict(sources=[dict(name='comparia',sha256='abc'),dict(name='prism',sha256='abc')])
    assert m.eligible(inventory,dict(sources=[receipt('comparia'),dict(name='prism',status='held')])) == [receipt('comparia')]


def test_wrong_input_hash():
    with pytest.raises(ValueError,match='hash mismatch'):
        m.eligible(dict(sources=[dict(name='prism',sha256='different')]),dict(sources=[receipt()]))


def test_no_receipt_no_launch(tmp_path):
    assert not m.predecessor_ready(tmp_path)


@pytest.mark.parametrize('running,waiting,kv,active,expected',[
    (25,0,.07,0,128), (154,0,.37,0,102), (256,0,.5,0,0),
    (257,0,.5,0,0), (10,1,.1,0,0), (10,0,.8,0,0),
    (10,0,.9,0,0), (154,0,.37,90,38), (0,0,0,128,0)])
def test_gate_reserves_dispatch(running,waiting,kv,active,expected):
    values={'vllm:num_requests_running':running,'vllm:num_requests_waiting':waiting,'vllm:kv_cache_usage_perc':kv}
    assert m.admission_credits(values,active)==expected


def test_metrics_missing_fail_closed():
    assert m.admission_credits({},0)==0


def test_recent_reserve_not_all_visible_active():
    values={'vllm:num_requests_running':192,'vllm:num_requests_waiting':0,'vllm:kv_cache_usage_perc':.4}
    assert m.admission_credits(values,64,recent=0)==64
    assert m.admission_credits(values,64,recent=20)==44
    assert m.admission_credits(values,64,recent=64)==0


def test_reservation_ages_and_release():
    gate=m.EndpointGate()
    gate.dispatched={1:95,2:99,3:100}
    gate.active=3
    assert gate.recent(100)==2
    assert gate.recent(103)==0
    gate.release(2)
    assert gate.active==2
    assert gate.recent(100)==1


def test_generic_prepare_two_rows(tmp_path):
    row=dict(id='one',target_message_index=1,messages=[dict(role='user',content='hi'),dict(role='assistant',content='hello')])
    import json
    data=tmp_path/'eligible.jsonl'
    data.write_text(json.dumps(row)+'\n'+json.dumps(dict(row,id='two'))+'\n')
    source=dict(name='comparia',sha256=m.base.file_hash(data))
    inventory=tmp_path/'inventory.json'
    m.base.write_json(inventory,dict(sources=[source]))
    evidence=tmp_path/'decision.json'
    m.base.write_json(evidence,dict(status='cleared'))
    entry=receipt('comparia')
    entry.update(input_sha256=source['sha256'],evidence=[dict(path=str(evidence),sha256=m.base.file_hash(evidence))],
                 eligible_source=dict(path=str(data),sha256=source['sha256'],rows=2))
    gate=tmp_path/'gate.json'
    m.base.write_json(gate,dict(inventory_sha256=m.base.file_hash(inventory),sources=[entry]))
    after=tmp_path/'repairs'
    m.base.write_json(after/'plan.json',dict(manifest=dict(pins={},tokenizer_dir='test',context_limit=32768,endpoints=[],model='test')))
    result=m.prepare(tmp_path/'next',inventory,gate,after)
    assert result['total']==2
    assert m.verify(tmp_path/'next')['sources'][0]['rows']==2
