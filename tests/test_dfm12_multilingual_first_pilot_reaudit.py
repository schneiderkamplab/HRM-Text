import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from dfm12 import multilingual_first_pilot_reaudit as reaudit
from dfm12.io import digest, file_hash, load, lock, write_json


def original():
    return dict(id='old-id', language='nl', family='grounded-instruct',
        messages=[{'role': 'user', 'content': 'Say hello.'}, {'role': 'assistant', 'content': 'Hallo.'}], tools=[],
        provenance=dict(language_code='nl', family='grounded-instruct', subtype='factual QA',
                        source={'text': 'Hello is a greeting.', 'id': 'source-id'}), audit={'keep': True})


def student(renderer, candidate):
    candidate['rendered_training_tokens'] = 24
    return candidate


def reviewer():
    return SimpleNamespace(deterministic_checks=lambda record: [], schema=lambda record: {'type': 'object'})


def test_canonical_preserves_full_messages_and_provenance(monkeypatch):
    monkeypatch.setattr(reaudit, 'student_validate', student)
    row = original()
    row['messages'] += [{'role': 'user', 'content': 'Again? '}, {'role': 'assistant', 'content': 'Hallo!'}]
    before = copy.deepcopy(row)
    candidate, checks = reaudit.canonicalize(row, None, reviewer())
    assert row == before
    for key in ('id', 'messages', 'tools', 'provenance'):
        assert candidate[key] == row[key]
    assert 'audit' not in candidate and not candidate['admission_authorized']
    record = reaudit.review_record(candidate)
    assert record['historical_generator_metadata_not_user_input'] == row['provenance']
    assert 'not user-provided' in record['provenance_warning']
    assert 'audit' not in record


def tool_row(user='Reserve item-1.'):
    row = original()
    row.update(family='tool-dialogue', tools=[{'type': 'function', 'function': {'name': 'lookup_stock',
        'parameters': {'type': 'object', 'properties': {'item': {'type': 'string'}, 'warehouse': {'type': 'string'}},
                       'required': ['item', 'warehouse'], 'additionalProperties': False}}}])
    row['provenance'].update(family='tool-dialogue', subtype='single', item='item-1', warehouse='warehouse-2')
    row['messages'] = [dict(role='user', content=user), dict(role='assistant', content='', tool_calls=[
        dict(id='call-1', type='function', function=dict(name='lookup_stock', arguments={'item': 'item-1', 'warehouse': 'warehouse-2'}))]),
        dict(role='tool', content='{"stock":4}', name='lookup_stock', tool_call_id='call-1'),
        dict(role='assistant', content='There are four available.')]
    return row


def test_provenance_only_warehouse_fails_without_changing_text(monkeypatch):
    monkeypatch.setattr(reaudit, 'student_validate', student)
    row = tool_row()
    candidate, checks = reaudit.canonicalize(row, None, reviewer())
    assert any(c['field'] == 'warehouse' and not c['passed'] for c in checks)
    assert candidate['messages'] == row['messages']


def test_tool_grounding_accepts_preceding_user_not_assistant_claim():
    assert all(c['passed'] for c in reaudit.identifier_grounding(tool_row('Reserve item-1 at warehouse-2.')))
    row = tool_row()
    row['messages'][1]['content'] = 'User supplied warehouse-2.'
    assert not all(c['passed'] for c in reaudit.identifier_grounding(row))


def test_string_tool_arguments_validation_copy_only(monkeypatch):
    monkeypatch.setattr(reaudit, 'student_validate', student)
    row = tool_row('Reserve item-1 at warehouse-2.')
    call = row['messages'][1]['tool_calls'][0]['function']
    call['arguments'] = json.dumps(call['arguments'])
    candidate, checks = reaudit.canonicalize(row, None, reviewer())
    assert isinstance(candidate['messages'][1]['tool_calls'][0]['function']['arguments'], str)
    assert all(c['passed'] for c in checks)
    call['arguments'] = '{"item":"item-1","item":"item-2"}'
    with pytest.raises(ValueError, match='Duplicate'):
        reaudit.canonicalize(row, None, reviewer())


def test_bad_roles_and_student_failure_not_repaired(monkeypatch):
    monkeypatch.setattr(reaudit, 'student_validate', student)
    row = original()
    row['messages'][1]['role'] = 'user'
    with pytest.raises(ValueError, match='role_order'):
        reaudit.canonicalize(row, None, reviewer())
    def fail(*a):
        raise ValueError('student context exceeds 4096')
    monkeypatch.setattr(reaudit, 'student_validate', fail)
    with pytest.raises(ValueError, match='4096'):
        reaudit.canonicalize(original(), None, reviewer())


def make_job(root, monkeypatch):
    monkeypatch.setattr(reaudit, 'student_validate', student)
    row = original()
    candidate, _ = reaudit.canonicalize(row, None, reviewer())
    key = digest('old-id')
    folder = reaudit.directory(root, key)
    original_path = folder / 'original' / f'{key}.json'
    write_json(original_path, row)
    path = folder / 'candidates' / f'{key}.json'
    write_json(path, candidate)
    source = dict(record_sha256=digest(row), original_snapshot_sha256=file_hash(original_path))
    store = reaudit.Store(root)
    with store.db:
        store.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',
            (key, row['id'], row['language'], row['family'], 'pending', file_hash(path),
             reaudit.fingerprint(candidate), json.dumps(source), None))
    return store, key, folder, candidate


def test_claim_exclusive_terminal_never_replayed(tmp_path, monkeypatch):
    store, key, folder, _ = make_job(tmp_path, monkeypatch)
    assert store.claim()['id'] == key
    assert store.claim() is None
    store.recover()
    assert store.db.execute('SELECT status FROM jobs').fetchone()[0] == 'abort_status_unknown'
    assert store.claim() is None
    assert not load(folder / 'outcomes' / f'{key}.json')['eligible_for_quarter_import']
    store.close()


def test_lock_excludes_second_owner(tmp_path):
    with lock(tmp_path / 'reaudit.lock'):
        with pytest.raises(BlockingIOError):
            with lock(tmp_path / 'reaudit.lock'):
                pytest.fail('second writer')


def client(monkeypatch, folder, keep=True, status='complete'):
    calls = []
    monkeypatch.setattr(reaudit.v6, 'review_request', lambda *a: {
        'response_format': {'type': 'json_schema', 'json_schema': {'schema': {'type': 'object'}}}})
    monkeypatch.setattr(reaudit.v6, 'review_result', lambda *a: dict(status='valid', effective_keep=keep,
        semantic_keep=keep, deterministic_pass=True, deterministic_checks=[]))
    async def call(key, stage, payload, schema, *args):
        calls.append((stage, payload, schema))
        state = dict(status=status, output={'valid': True}, raw={'content': '{"valid":true}', 'finish_reason': 'stop'},
                     request_sha256=digest(payload))
        write_json(folder / 'requests' / f'{key}-review.json', {'request': payload, 'schema': schema})
        write_json(folder / 'stages' / f'{key}-review.json', state)
        return state
    return SimpleNamespace(call=call), calls


def test_review_only_accept_receipt_and_import_validation(tmp_path, monkeypatch):
    store, key, folder, candidate = make_job(tmp_path, monkeypatch)
    stages, calls = client(monkeypatch, folder)
    receipt = asyncio.run(reaudit.process(tmp_path, store.claim(), stages, 'endpoint', 16384, reviewer(), object()))
    store.finish(key, receipt)
    assert len(calls) == 1 and calls[0][0] == 'review'
    assert calls[0][1]['temperature'] == 0 and calls[0][1]['frequency_penalty'] == .5
    assert 'json' in calls[0][1]['structured_outputs']
    assert receipt['status'] == 'accepted' and receipt['eligible_for_quarter_import']
    assert not receipt['training_admission'] and not receipt['generation_authorized']
    actual, checked = reaudit.validate_accepted(tmp_path, key, renderer=object(), review=reviewer())
    assert actual == candidate and checked == receipt
    store.close()


@pytest.mark.parametrize('keep,status,expected', [(False, 'complete', 'rejected'), (True, 'invalid_output', 'review_invalid_output')])
def test_rejection_or_loop_terminal_no_retry(tmp_path, monkeypatch, keep, status, expected):
    store, key, folder, _ = make_job(tmp_path, monkeypatch)
    stages, calls = client(monkeypatch, folder, keep, status)
    receipt = asyncio.run(reaudit.process(tmp_path, store.claim(), stages, 'endpoint', 16384, reviewer(), object()))
    store.finish(key, receipt)
    assert receipt['status'] == expected and receipt['terminal']
    assert not receipt['eligible_for_quarter_import'] and len(calls) == 1
    assert not (folder / 'accepted' / f'{key}.json').exists()
    with pytest.raises(ValueError, match='terminal accepted'):
        reaudit.validate_accepted(tmp_path, key, renderer=object(), review=reviewer())
    store.close()


def test_accepted_drift_detected(tmp_path, monkeypatch):
    store, key, folder, _ = make_job(tmp_path, monkeypatch)
    stages, _ = client(monkeypatch, folder)
    receipt = asyncio.run(reaudit.process(tmp_path, store.claim(), stages, 'endpoint', 16384, reviewer(), object()))
    store.finish(key, receipt)
    write_json(folder / 'accepted' / f'{key}.json', {'messages': 'rewritten'})
    with pytest.raises(ValueError, match='evidence drift'):
        reaudit.validate_accepted(tmp_path, key, renderer=object(), review=reviewer())
    store.close()


def test_orphan_accepted_file_after_crash_cannot_be_imported(tmp_path, monkeypatch):
    store, key, folder, _ = make_job(tmp_path, monkeypatch)
    stages, _ = client(monkeypatch, folder)
    asyncio.run(reaudit.process(tmp_path, store.claim(), stages, 'endpoint', 16384, reviewer(), object()))
    store.recover()
    with pytest.raises(ValueError, match='terminal accepted'):
        reaudit.validate_accepted(tmp_path, key, renderer=object(), review=reviewer())
    store.close()


def test_path_traversal_rejected(tmp_path):
    with pytest.raises(ValueError, match='receipt key'):
        reaudit.directory(tmp_path, '../bad')
