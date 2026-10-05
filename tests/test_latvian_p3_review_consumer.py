import copy
import json

import pytest

from dfm12.jobs import Queue
from dfm12.io import file_hash, write_json
from dfm12.latvian_p3_review_consumer import (
    AUDIT_STAGE, DIMENSIONS, REPAIR_STAGE, REAUDIT_STAGE, prepare, stage_reaudits,
    validate_repair, validate_review,
)


def record():
    return {'messages': [{'role': 'user', 'content': 'Kurs?'},
                         {'role': 'assistant', 'content': 'A'}],
            'english_candidates': [{'candidate_id': 'ref', 'question': 'Which?'}]}


def decision():
    return dict(candidate_id='ref', alignment='supported', keep=True,
        pairing_checks={'english_to_latvian': 'pass', 'latvian_to_english': 'pass'},
        pairing_evidence=[dict(english_quote='Which?', latvian_quote='Kurs?', explanation='Corresponding question.')],
        literal_evidence='Question and answer compared.', reason='Supported.',
        **dict.fromkeys(DIMENSIONS, 'pass'))


def test_review_is_independent_dimensions_and_literal_pairing():
    validate_review(decision(), record())
    for field in DIMENSIONS:
        d = decision(); d[field] = 'uncertain'
        with pytest.raises(ValueError): validate_review(d, record())
    d = decision(); d['pairing_evidence'][0]['english_quote'] = 'Invented'
    with pytest.raises(ValueError): validate_review(d, record())
    d = decision(); d['pairing_checks']['latvian_to_english'] = 'uncertain'
    with pytest.raises(ValueError): validate_review(d, record())


def test_null_pairing_is_valid_hold_not_certificate():
    d = decision(); d.update(candidate_id=None, alignment='uncertain', keep=False, pairing_evidence=[])
    validate_review(d, record())
    d['alignment'] = 'supported'
    with pytest.raises(ValueError): validate_review(d, record())


def test_repair_full_messages_and_literal_change_ledger():
    repaired = copy.deepcopy(record()['messages']); repaired[-1]['content'] = 'B'
    result = dict(status='proposed_correction', messages=repaired,
                  changes=[dict(original='A', replacement='B', evidence='Source choice B')], reason='Correct answer')
    validate_repair(result, record())
    result['messages'] = repaired[-1:]
    with pytest.raises(ValueError): validate_repair(result, record())
    validate_repair(dict(status='hold', messages=None, reason='Uncertain source'), record())


def test_reaudit_reconciliation_idempotent_and_unprimed(tmp_path):
    q = Queue(tmp_path / 'q.sqlite')
    payload = dict(record=record(), request={'max_tokens': 8192, 'model': '31b'})
    key = q.add(REPAIR_STAGE, payload)
    claimed = q.claim(REPAIR_STAGE, 'owner')
    assert claimed[0] == key
    q.finish(key, 'owner', 1, result={'decision': dict(status='proposed_correction',
        messages=record()['messages'], reason='DO NOT PRIME REAUDIT')})
    stage_reaudits(q); stage_reaudits(q)
    jobs = list(q.db.execute('SELECT payload FROM jobs WHERE stage=?', (REAUDIT_STAGE,)))
    assert len(jobs) == 1
    assert 'DO NOT PRIME REAUDIT' not in jobs[0][0]
    assert 'original_messages' in jobs[0][0]
    assert '"automatic_admission": false' in jobs[0][0]
    q.close()


def test_prepare_preserves_source_and_resumes_without_reset(tmp_path):
    source = tmp_path / 'source'; source.mkdir()
    packet = dict(job_id='parent', record=record(), request=dict(model='31b',
        messages=[dict(role='system', content='original rubric'), dict(role='user', content='full source')]))
    path = source / 'requests.jsonl'
    path.write_text(json.dumps(packet) + '\n')
    original = file_hash(path)
    write_json(source / 'manifest.json', {'files': {'requests.jsonl': original}})
    root = tmp_path / 'consumer'
    first = prepare(root, source)
    q = Queue(root / 'review.sqlite'); job = q.claim(AUDIT_STAGE, 'owner')
    q.finish(job[0], 'owner', 1, result={'decision': decision()}); q.close()
    second = prepare(root, source)
    assert first == second
    assert file_hash(path) == original
    payload = json.loads((root / 'requests.jsonl').read_text())
    assert payload['request']['messages'][1]['content'] == 'full source'
    assert payload['record'] == record()
    q = Queue(root / 'review.sqlite')
    assert q.db.execute('SELECT count(*),sum(attempts) FROM jobs').fetchone() == (1, 1)
    assert q.status()[0]['status'] == 'done'
    q.close()


def test_repair_needs_external_pairing_receipt(tmp_path):
    from dfm12.latvian_p3_review_consumer import enqueue_repairs
    root = tmp_path
    q = Queue(root / 'review.sqlite')
    source = dict(record(), record_sha256='hash')
    payload = dict(record=source, request={'model': '31b'})
    key = q.add(AUDIT_STAGE, payload); q.claim(AUDIT_STAGE, 'owner')
    d = decision(); d['keep'] = False; d['source_fidelity'] = 'fail'
    q.finish(key, 'owner', 1, result={'decision': d}); q.close()
    receipts = root / 'pairings.jsonl'; receipts.write_text('')
    assert enqueue_repairs(root, receipts)['eligible_repair_jobs'] == 0
    receipts.write_text(json.dumps(dict(record_sha256='hash', independently_verified=False)) + '\n')
    with pytest.raises(ValueError): enqueue_repairs(root, receipts)


def test_consumer_retains_raw_response_without_certification(tmp_path, monkeypatch):
    import io
    import sys
    import types
    from dfm12.latvian_p3_review_consumer import run
    source = tmp_path / 'source'; source.mkdir()
    request = dict(model='31b', max_tokens=8192,
        messages=[dict(role='system', content='rubric'), dict(role='user', content='evidence')])
    path = source / 'requests.jsonl'
    path.write_text(json.dumps(dict(job_id='parent', record=record(), request=request)) + '\n')
    write_json(source / 'manifest.json', {'files': {'requests.jsonl': file_hash(path)}})
    root = tmp_path / 'consumer'; prepare(root, source)
    tokenizer = tmp_path / 'tokenizer'; tokenizer.mkdir()
    tokenfile = tokenizer / 'tokenizer.json'; tokenfile.write_text('{}')
    write_json(root / 'native-render-preflight.json', dict(requests_sha256=file_hash(root / 'requests.jsonl'),
        blocked_job_ids=[], context_budget=32768, tokenizer_files={str(tokenfile): file_hash(tokenfile)}))
    fake = types.SimpleNamespace(apply_chat_template=lambda *a, **k: [1, 2, 3])
    monkeypatch.setitem(sys.modules, 'transformers', types.SimpleNamespace(
        AutoTokenizer=types.SimpleNamespace(from_pretrained=lambda *a, **k: fake)))
    raw = dict(choices=[dict(finish_reason='stop', message={'content': json.dumps(decision())})])
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: io.BytesIO(json.dumps(raw).encode()))
    assert run(root, 'http://mock-only', AUDIT_STAGE, tokenizer)[0]['status'] == 'done'
    assert len(list((root / 'raw').glob('*.json'))) == 1
    q = Queue(root / 'review.sqlite')
    result = list(q.completed(AUDIT_STAGE))[0][2]
    assert result['pairing_certified'] is False
    assert result['automatic_admission'] is False
    q.close()
