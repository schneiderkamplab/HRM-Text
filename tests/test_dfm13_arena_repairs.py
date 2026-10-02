import copy
import importlib.util
from pathlib import Path
import sqlite3

P = Path(__file__).resolve().parents[1]/'scripts/dfm13_arena_repairs.py'
spec = importlib.util.spec_from_file_location('arena_repairs_test', P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def row():
    return dict(id='x', provenance={'source':'unchanged'}, target_message_index=1,
                messages=[dict(role='user',content='Compute 2+2'),
                          dict(role='assistant',content='5',tool_calls=[],tool_call_id='preserved')])


def test_content_only():
    original = row()
    result = m.corrected(original,'4')
    expected = copy.deepcopy(original)
    expected['messages'][1]['content'] = '4'
    assert result == expected
    assert original['messages'][1]['content'] == '5'


def test_transport_cpu_bounds_preserved():
    payload = m.strong.request(row())
    wire = m.transport(payload)
    assert 'maxLength' not in wire['response_format']['json_schema']['schema']['properties']['reason']
    assert payload['response_format']['json_schema']['schema']['properties']['reason']['maxLength'] == 2400
    assert wire['chat_template_kwargs']['enable_thinking'] is True
    assert wire['max_tokens'] == 8192


def test_fresh_review_no_correction_reason():
    payload = m.correction_request(row(),'SECRET_AUDIT_REASON')
    assert 'SECRET_AUDIT_REASON' in str(payload)
    review = m.strong.request(m.corrected(row(),'4'))
    assert 'SECRET_AUDIT_REASON' not in str(review)


def test_dispositions():
    assert m.destination('keep') == 'accepted'
    assert m.destination('reject') == 'rejected'
    assert m.destination('repair') == 'needs_review'
    assert m.destination('needs_verification') == 'needs_review'


def test_terminal_requires_all_rows_and_no_inflight():
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE jobs(status TEXT)')
    db.execute('INSERT INTO jobs VALUES("complete")')
    assert m.terminal(db,1)
    assert not m.terminal(db,2)
    db.execute('INSERT INTO jobs VALUES("inflight")')
    assert not m.terminal(db,2)
    db.execute('UPDATE jobs SET status="invalid_response" WHERE status="inflight"')
    assert m.terminal(db,2)


def test_locked_source_never_snapshots(tmp_path):
    source = tmp_path/'source'
    root = tmp_path/'followup'
    root.mkdir()
    with m.base.lock(source/'controller.lock'):
        assert not m.snapshot(root,dict(source=str(source),manifest={'total':1}))
    assert not (root/'input.sqlite').exists()


def test_seal_drift(tmp_path):
    import pytest
    m.base.write_json(tmp_path/'plan.json',dict(pins={}))
    m.base.write_json(tmp_path/'seal.json',dict(sha256='wrong'))
    with pytest.raises(ValueError,match='seal drift'):
        m.verify(tmp_path)
