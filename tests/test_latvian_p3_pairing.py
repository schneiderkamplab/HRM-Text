import json

import pytest

from dfm12.io import digest, file_hash, load, write_json
from dfm12.jobs import Queue
from dfm12 import latvian_p3_pairing as p


def decision(record, key, keep=True):
    candidate = next((c for c in record['english_candidates'] if c['candidate_id'] == key), None)
    return dict(candidate_id=key, alignment='supported' if key else 'uncertain', keep=bool(key) and keep,
        pairing_checks=dict(english_to_latvian='pass' if key else 'uncertain', latvian_to_english='pass' if key else 'uncertain'),
        pairing_evidence=[dict(english_quote=candidate['question'], latvian_quote=record['messages'][0]['content'],
            explanation='Matched content')] if key else [], literal_evidence='Checked complete source', reason='Comparison',
        **dict.fromkeys(p.consumer.DIMENSIONS, 'pass'))


def finish(q, key, d):
    payload = json.loads(q.db.execute('SELECT payload FROM jobs WHERE id=?', (key,)).fetchone()[0])
    result = dict(decision=d, request_sha256=digest(payload['request']), automatic_admission=False)
    q.db.execute("UPDATE jobs SET status='done',result=?,attempts=1 WHERE id=?", (json.dumps(result), key))


@pytest.fixture
def prepared(tmp_path):
    source = tmp_path / 'source'; source.mkdir(); packets = []
    for group in range(4):
        refs = [dict(candidate_id=f'{group}-{i}', config=str(group), question=f'Question {group} {i}',
            source_answers=['answer'], retrieval_origins=['positional_unverified'], pairing_verified=True) for i in range(5)]
        for i in range(5):
            record = dict(id=f'{group}-{i}', record_sha256=f'hash-{group}-{i}', english_candidates=refs,
                verified_manual_candidate_id=f'{group}-{i}', semantic_rank=['secret'],
                translated_source={'question': 'Original untranslated drift evidence', 'answer': 'original answer'},
                messages=[dict(role='user', content=f'Latvian {group} {i}'), dict(role='assistant', content='answer')])
            packets.append(dict(job_id=record['id'], record=record))
    source_path = source / 'requests.jsonl'
    source_path.write_text(''.join(json.dumps(r) + '\n' for r in packets))
    write_json(source / 'manifest.json', {'files': {'requests.jsonl': file_hash(source_path)}})
    root = tmp_path / 'prepared'; p.prepare(root, source)
    return root, source


def complete_calibration(root, false_accept=False):
    q = Queue(root / 'review.sqlite')
    for label in load(root / 'calibration-labels.json'):
        for key in label['jobs'].values():
            payload = json.loads(q.db.execute('SELECT payload FROM jobs WHERE id=?', (key,)).fetchone()[0])
            selected = label['expected_candidate_id']
            if false_accept and selected is None:
                selected = payload['record']['english_candidates'][0]['candidate_id']; false_accept = False
            finish(q, key, decision(payload['record'], selected))
    q.close()


def test_blind_evidence_whitelist_and_control_labels_outside_prompts(prepared):
    root, source = prepared
    assert load(root / 'manifest.json')['calibration_controls'] == 140
    for line in (root / 'requests.jsonl').read_text().splitlines():
        request = json.loads(line)['request']
        text = request['messages'][1]['content']
        assert json.loads(text)['translated_source'] == {'question': 'Original untranslated drift evidence', 'answer': 'original answer'}
        for field in ('expected_candidate_id', 'retrieval_origins', 'pairing_verified', 'semantic_rank', 'verified_manual_candidate_id'):
            assert field not in text
    before = file_hash(root / 'requests.jsonl'); p.prepare(root, source)
    assert file_hash(root / 'requests.jsonl') == before
    labels = load(root / 'calibration-labels.json')
    dev = {r['anchor_id'] for r in labels if r['split'] == 'development'}
    held = {r['anchor_id'] for r in labels if r['split'] == 'heldout'}
    assert not dev & held


def test_calibration_blocks_false_supported_and_missing_results(prepared):
    root, _ = prepared
    assert p.reconcile(root)['counts'] == {'pending_calibration': 20}
    complete_calibration(root, false_accept=True)
    assert p.reconcile(root)['counts'] == {'rejected_calibration_failure': 20}


def test_disagreement_terminal_and_truthful_model_receipt(prepared):
    root, _ = prepared; complete_calibration(root)
    q = Queue(root / 'review.sqlite'); items = load(root / 'inventory.json')
    for index, item in enumerate(items):
        for stage, key in item['jobs'].items():
            payload = json.loads(q.db.execute('SELECT payload FROM jobs WHERE id=?', (key,)).fetchone()[0])
            selected = item['id']
            if index == 0 and stage == p.BLIND:
                selected = next(c['candidate_id'] for c in payload['record']['english_candidates'] if c['candidate_id'] != selected)
            finish(q, key, decision(payload['record'], selected))
    q.close(); result = p.reconcile(root)
    assert result['terminal'] == 20
    assert result['counts']['rejected_blind_disagreement'] == 1
    receipts = list(p.rows(root / 'model-pairings.jsonl'))
    assert len(receipts) == 19
    assert all(r['verification_kind'] == 'model_verified' and not r['human_verified'] for r in receipts)
    assert p.reconcile(root) == result


def test_ambiguous_answers_rejected():
    r = {'english_candidates': [dict(candidate_id='x', question='q', source_answers=['A', 'B'])]}
    d = dict(alignment='supported', candidate_id='x')
    assert p.agreement(d, d, r)[1] == 'unresolved_duplicate_or_answer_alternatives'


def test_one_repair_then_fresh_reaudit_no_rationale(prepared):
    root, _ = prepared; complete_calibration(root)
    q = Queue(root / 'review.sqlite'); item = load(root / 'inventory.json')[0]
    for key in item['jobs'].values():
        payload = json.loads(q.db.execute('SELECT payload FROM jobs WHERE id=?', (key,)).fetchone()[0])
        d = decision(payload['record'], item['id'], keep=False); d['source_fidelity'] = 'fail'
        finish(q, key, d)
    p.reconcile(root); p.reconcile(root)
    repairs = list(q.db.execute('SELECT id,payload FROM jobs WHERE stage=?', (p.consumer.REPAIR_STAGE,)))
    assert len(repairs) == 1
    key, encoded = repairs[0]; record = json.loads(encoded)['record']
    messages = [dict(m) for m in record['messages']]; messages[-1]['content'] = 'corrected'
    finish(q, key, dict(status='proposed_correction', messages=messages,
        changes=[dict(original='answer', replacement='corrected', evidence='source')], reason='SECRET REPAIR RATIONALE'))
    p.reconcile(root)
    audits = list(q.db.execute('SELECT id,payload FROM jobs WHERE stage=?', (p.consumer.REAUDIT_STAGE,)))
    assert len(audits) == 1 and 'SECRET REPAIR RATIONALE' not in audits[0][1]
    key, encoded = audits[0]; record = json.loads(encoded)['record']
    finish(q, key, decision(record, item['id'], keep=False))
    assert p.reconcile(root)['counts']['rejected_reaudit'] == 1
    assert q.db.execute('SELECT count(*) FROM jobs WHERE stage=?', (p.consumer.REPAIR_STAGE,)).fetchone()[0] == 1
    q.close()


def test_wrong_endpoint_prevents_dispatch(prepared, monkeypatch, tmp_path):
    from dfm12 import wave31_endpoint_health
    root, _ = prepared; ready = tmp_path / 'ready.json'
    write_json(ready, dict(model=p.MODEL, all_files_verified=True, snapshot=str(tmp_path)))
    def reject(*a, **k): raise ValueError('Wrong model/context')
    monkeypatch.setattr(wave31_endpoint_health, 'check', reject)
    monkeypatch.setattr(p.consumer, 'run', lambda *a, **k: pytest.fail('Must not dispatch'))
    with pytest.raises(ValueError, match='Wrong model/context'):
        p.run(root, 'http://mock-only', p.CALIBRATION, tmp_path, ready)
