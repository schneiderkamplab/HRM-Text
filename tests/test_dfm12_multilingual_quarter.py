import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dfm12 import multilingual_quarter as quarter
from dfm12.io import digest, load, lock, write_json


class Shortage(Exception):
    pass


class Provider:
    def next_spec(self, language, family, slot):
        return dict(language_code=language, family=family, slot=slot,
                    contract_version=4, cohort='stable-campaign', subtype='math')


def ledger(tmp_path, target=2, groups=None):
    db = quarter.Ledger(tmp_path / 'jobs.sqlite')
    db.initialize(groups or [dict(language='nl', family='math-code', accepted_target=target)])
    return db


def outcome(job, keep=False, fingerprint='a'*64):
    return dict(quarter.pilot.base_outcome(job['spec']), terminal=True,
                status='valid' if keep else 'invalid_output', effective_keep=keep, fingerprint=fingerprint)


def test_reservations_no_overshoot_and_once_only_finish(tmp_path):
    db = ledger(tmp_path)
    first = db.reserve(Provider(), Shortage, tmp_path)
    second = db.reserve(Provider(), Shortage, tmp_path)
    assert db.reserve(Provider(), Shortage, tmp_path) is None
    quarter.Seen(db, first['id']).add('a'*64)
    assert db.finish(first['id'], outcome(first, True))
    assert not db.finish(first['id'], outcome(first, True))
    assert db.reserve(Provider(), Shortage, tmp_path) is None
    db.finish(second['id'], outcome(second))
    replacement = db.reserve(Provider(), Shortage, tmp_path)
    assert replacement['spec']['slot'] == 100002
    quarter.Seen(db, replacement['id']).add('b'*64)
    db.finish(replacement['id'], outcome(replacement, True, 'b'*64))
    assert db.reserve(Provider(), Shortage, tmp_path) is None
    state = db.report(tmp_path, 'test')
    assert state['accepted'] == 2 and state['active'] == 0 and state['candidates'] == 3
    db.close()


def test_six_times_attempt_cap(tmp_path):
    db = ledger(tmp_path, target=1)
    for _ in range(6):
        job = db.reserve(Provider(), Shortage, tmp_path)
        assert job
        db.finish(job['id'], outcome(job))
    assert db.reserve(Provider(), Shortage, tmp_path) is None
    assert db.report(tmp_path, 'test')['budget_exhausted_groups'] == 1
    db.close()


def test_seed_shortage_no_attempt_no_cursor_and_rotate(tmp_path):
    class Partial(Provider):
        def next_spec(self, language, family, slot):
            if family == 'grounded-instruct':
                raise Shortage('waiting')
            return super().next_spec(language, family, slot)
    db = ledger(tmp_path, groups=[dict(language='nl', family=f, accepted_target=1)
                                 for f in ('grounded-instruct', 'math-code')])
    job = db.reserve(Partial(), Shortage, tmp_path)
    assert job['spec']['family'] == 'math-code'
    group = db.db.execute("SELECT * FROM groups WHERE family='grounded-instruct'").fetchone()
    assert group['attempts'] == 0 and group['next_slot'] == 100000 and group['active'] == 0
    assert group['blocked'].startswith('seed_shortage')
    db.close()


def test_fingerprint_global_across_groups_and_crash(tmp_path):
    db = ledger(tmp_path)
    first = db.reserve(Provider(), Shortage, tmp_path)
    quarter.Seen(db, first['id']).add('a'*64)
    db.close()
    db = quarter.Ledger(tmp_path / 'jobs.sqlite')
    assert 'a'*64 in quarter.Seen(db, 'another-job')
    db.recover()
    assert db.db.execute('SELECT status FROM jobs').fetchone()['status'] == 'abort_status_unknown'
    assert db.report(tmp_path, 'test')['active'] == 0
    second = db.reserve(Provider(), Shortage, tmp_path)
    with pytest.raises(ValueError, match='owned unique'):
        db.finish(second['id'], outcome(second, True))
    assert db.report(tmp_path, 'test')['accepted'] == 0
    db.close()


def test_forged_or_nonterminal_outcome_rejected(tmp_path):
    db = ledger(tmp_path)
    job = db.reserve(Provider(), Shortage, tmp_path)
    for invalid in (dict(outcome(job), id='wrong'), dict(outcome(job), terminal=False)):
        with pytest.raises(ValueError, match='identity'):
            db.finish(job['id'], invalid)
    assert db.report(tmp_path, 'test')['active'] == 1
    db.close()


def test_provider_identity_failure_no_reservation(tmp_path):
    db = ledger(tmp_path)
    bad = SimpleNamespace(next_spec=lambda *a: {'language_code': 'wrong'})
    with pytest.raises(ValueError, match='wrong slot'):
        db.reserve(bad, Shortage, tmp_path)
    assert db.report(tmp_path, 'test')['candidates'] == 0
    db.close()


def test_stable_ids_and_sharding():
    assert quarter.candidate_id('campaign', 'fingerprint') == quarter.candidate_id('campaign', 'fingerprint')
    assert quarter.candidate_id('other', 'fingerprint') != quarter.candidate_id('campaign', 'fingerprint')
    assert str(quarter.work_root('root', 'abcde')) == 'root/work/ab/cd'


def test_single_writer_lock(tmp_path):
    with lock(tmp_path / 'controller.lock'):
        with pytest.raises(BlockingIOError):
            with lock(tmp_path / 'controller.lock'):
                pytest.fail('Concurrent writer')


def saved_keep(tmp_path, monkeypatch):
    spec = Provider().next_spec('nl', 'math-code', 100000)
    key = quarter.pilot.slot_key(spec)
    candidate = dict(id='donor-id', messages=[{'role': 'assistant', 'content': 'correct'}], tools=[])
    fingerprint = digest({k: candidate[k] for k in ('messages', 'tools')})
    schema = {'type': 'object', 'required': ['keep'], 'properties': {'keep': {'const': True}}, 'additionalProperties': False}
    request = {'messages': ['strict request']}
    state = dict(status='complete', output={'keep': True}, raw={'content': '{"keep":true}', 'finish_reason': 'stop'},
                 request_sha256=digest(request))
    for stage in ('generate', 'review'):
        write_json(tmp_path / 'stages' / f'{key}-{stage}.json', state)
    write_json(tmp_path / 'candidates' / f'{key}.json', candidate)
    write_json(tmp_path / 'requests' / f'{key}-review.json', {'schema': schema, 'request': request})
    monkeypatch.setattr(quarter.v6, 'generation_assemble', lambda *a: candidate)
    monkeypatch.setattr(quarter.v6, 'audit_record', lambda *a: {})
    monkeypatch.setattr(quarter.v6, 'review_result', lambda *a: {'effective_keep': True})
    adapters = (SimpleNamespace(schema=lambda *a: schema), None)
    monkeypatch.setattr(quarter.v6, 'adapters', lambda: adapters)
    out = dict(quarter.pilot.base_outcome(spec), terminal=True, status='valid', effective_keep=True, fingerprint=fingerprint)
    return spec, key, out, candidate


def test_saved_keep_rechecks_schema_and_raw(tmp_path, monkeypatch):
    spec, key, out, candidate = saved_keep(tmp_path, monkeypatch)
    assert quarter.validate_saved_keep(tmp_path, key, spec, out)[0] == candidate
    path = tmp_path / 'stages' / f'{key}-review.json'
    state = load(path)
    state['raw']['content'] = '{"keep":true,"keep":true}'
    write_json(path, state)
    with pytest.raises(ValueError, match='Duplicate'):
        quarter.validate_saved_keep(tmp_path, key, spec, out)


def test_saved_keep_rejects_simplified_schema(tmp_path, monkeypatch):
    spec, key, out, _ = saved_keep(tmp_path, monkeypatch)
    path = tmp_path / 'requests' / f'{key}-review.json'
    request = load(path)
    request['schema'] = {'type': 'object'}
    write_json(path, request)
    with pytest.raises(ValueError, match='strict schema'):
        quarter.validate_saved_keep(tmp_path, key, spec, out)


def test_saved_keep_rejects_semantic_false(tmp_path, monkeypatch):
    spec, key, out, _ = saved_keep(tmp_path, monkeypatch)
    monkeypatch.setattr(quarter.v6, 'review_result', lambda *a: {'effective_keep': False})
    with pytest.raises(ValueError, match='CPU recheck'):
        quarter.validate_saved_keep(tmp_path, key, spec, out)


def test_recovery_terminal_keep_materializes_before_commit(tmp_path, monkeypatch):
    db = ledger(tmp_path, target=1)
    job = db.reserve(Provider(), Shortage, tmp_path)
    spec, key, out, candidate = saved_keep(job['workdir'], monkeypatch)
    assert key == job['id']
    quarter.Seen(db, key).add(out['fingerprint'])
    write_json(job['workdir'] / 'outcomes' / f'{key}.json', out)
    db.recover('stable-campaign')
    assert db.report(tmp_path, 'test')['accepted'] == 1
    packed = load(job['workdir'] / 'accepted' / f'{key}.json')
    assert packed['id'] == quarter.candidate_id('stable-campaign', out['fingerprint'])
    assert load(job['workdir'] / 'candidates' / f'{key}.json')['id'] == candidate['id']
    db.recover('stable-campaign')
    assert db.report(tmp_path, 'test')['accepted'] == 1
    db.close()


def test_pilot_import_only_strict_keeps_preserves_ids(tmp_path, monkeypatch):
    source = tmp_path / 'donor'
    spec, key, out, candidate = saved_keep(source, monkeypatch)
    write_json(source / 'outcomes' / f'{key}.json', out)
    write_json(source / 'previous-hashes.json', [])
    write_json(source / 'manifest.json', {})
    monkeypatch.setattr(quarter.pilot, 'verify', lambda *a: ({}, [spec], set()))
    db = ledger(tmp_path)
    _, receipt = quarter.pilot_import(db, source, tmp_path, expected=1)
    assert receipt['accepted'] == 1
    assert db.report(tmp_path, 'test')['accepted'] == 1
    assert load(source / 'candidates' / f'{key}.json')['id'] == 'donor-id'
    db.close()


def test_pilot_import_count_failure_rolls_back(tmp_path, monkeypatch):
    source = tmp_path / 'donor'
    spec, key, out, _ = saved_keep(source, monkeypatch)
    write_json(source / 'outcomes' / f'{key}.json', dict(out, effective_keep=False))
    write_json(source / 'previous-hashes.json', [])
    monkeypatch.setattr(quarter.pilot, 'verify', lambda *a: ({}, [spec], set()))
    db = ledger(tmp_path)
    with pytest.raises(ValueError, match='Expected 1'):
        quarter.pilot_import(db, source, tmp_path, expected=1)
    assert db.report(tmp_path, 'test')['accepted'] == 0
    assert db.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0] == 0
    db.close()


def test_targets_exact_authorization():
    import yaml
    from dfm12.multilingual_targets import targets
    rows = targets(yaml.safe_load(quarter.CONFIG.read_text()), 'quarter')
    assert len(rows) == 42 and sum(r['accepted_target'] for r in rows) == 962500


def test_report_does_not_scan_jobs(tmp_path):
    db = ledger(tmp_path)
    statements = []
    db.db.set_trace_callback(statements.append)
    report = db.report(tmp_path, 'test')
    assert not any('FROM JOBS' in sql.upper() for sql in statements)
    assert not report['automatic_upload'] and not report['automatic_export']
    db.close()
