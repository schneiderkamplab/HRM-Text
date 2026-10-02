import asyncio
import json
import sqlite3

import pytest

from dfm12.io import load, write_json
from dfm12.multilingual_calibration import calibration_cases
from dfm12.multilingual_prepare_calibrated import QUOTAS, certify, unused_snapshot
from dfm12 import multilingual_trial as trial


def control_review(case):
    review = dict(language_correct=True, meaning_correct=True, constraints_met=True,
                  issues=[], back_translation='Diagnostic review')
    for key, value in case['expected_dimensions'].items():
        if value is not None:
            review[key] = value
    if not case['expected_keep']:
        review['issues'] = ['Known diagnostic failure']
    return review


@pytest.mark.parametrize('mode', ['pass', 'false_accept', 'error', 'invalid', 'dimension'])
def test_all_controls_gate(tmp_path, monkeypatch, mode):
    cases = calibration_cases()
    write_json(tmp_path / 'calibration/controls.json', cases)
    monkeypatch.setattr(trial, 'verify_inputs', lambda _: None)
    active = peak = 0
    async def query(session, endpoint, payload):
        nonlocal active, peak
        case = next(c for c in cases if c['record'] == json.loads(payload['messages'][1]['content']))
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        review = control_review(case)
        if case == cases[1]:
            if mode == 'error':
                raise RuntimeError('transport failure')
            if mode == 'invalid':
                return None
            if mode == 'false_accept':
                return dict(language_correct=True, meaning_correct=True, constraints_met=True, issues=[], back_translation='x')
            if mode == 'dimension':
                review['meaning_correct'] = True
        return review
    if mode == 'pass':
        asyncio.run(trial.gate(tmp_path, None, ['replica'], query))
    else:
        with pytest.raises(RuntimeError, match='zero generation'):
            asyncio.run(trial.gate(tmp_path, None, ['replica'], query))
    result = load(tmp_path / 'review-calibration.json')
    assert result['passed'] == (mode == 'pass')
    assert 1 < peak <= 16
    assert len(result['details']) == len(cases)
    assert result['bulk_authorized'] is False


def test_quotas_and_unused_donor(tmp_path):
    assert sum(QUOTAS.values()) == 100
    db = sqlite3.connect(tmp_path / 'pilot.sqlite')
    db.executescript('CREATE TABLE slots(status TEXT,attempts INT,candidate TEXT); CREATE TABLE events(x); CREATE TABLE accepted_hashes(hash TEXT);')
    db.executemany('INSERT INTO slots VALUES (?,?,?)', [('pending', 0, None)] * 35000)
    db.commit()
    write_json(tmp_path / 'previous-hashes.json', [])
    write_json(tmp_path / 'review-calibration.json', {'checks': [{'expected_keep': False, 'actual_keep': True}]})
    assert unused_snapshot(tmp_path)['events'] == 0
    db.execute('INSERT INTO events VALUES (1)')
    db.commit()
    with pytest.raises(ValueError, match='unused'):
        unused_snapshot(tmp_path)
    db.close()


def test_certify_rejects_failed_tests(tmp_path):
    report = tmp_path / 'tests.xml'
    report.write_text('<testsuite tests="3" failures="1" errors="0"/>')
    with pytest.raises(ValueError, match='Tests did not all pass'):
        certify(tmp_path, report)
    assert not (tmp_path / 'cpu-preflight-passed.json').exists()


def test_outcomes_contain_accepted_text_and_dimensions(tmp_path):
    from dfm12.multilingual_pilot import Store
    write_json(tmp_path / 'pilot-config.json', {'quotas': {'math-code': 1}, 'languages': ['fo'], 'calibration_policy': trial.POLICY})
    write_json(tmp_path / 'previous-hashes.json', [])
    store = Store(tmp_path)
    row = {'id': 'example', 'messages': [{'role': 'assistant', 'content': 'Actual Faroese sample'}]}
    audit = dict(language_quality=4, coherence=5, usefulness=4, second_review={'language_correct': True, 'meaning_correct': False, 'constraints_met': True})
    store.save(('fo', 'math-code', 0), status='accepted', candidate=json.dumps(row), audit=json.dumps(audit))
    store.event(('fo', 'math-code', 0), 0, 'accepted', {'id': 'example', 'audit': audit})
    trial.outcomes(store)
    inspection = json.loads((tmp_path / 'trial-inspection.jsonl').read_text())
    assert inspection['candidate']['messages'] == row['messages']
    assert load(tmp_path / 'trial-outcomes.json')['groups'][0]['dimensions']['meaning_correct'] == {'false': 1}
    store.db.close()


def test_failed_gate_cannot_generate(tmp_path, monkeypatch):
    from dfm12 import multilingual_pilot as pilot
    from dfm12.multilingual_seeds import LANGUAGES
    write_json(tmp_path / 'pilot-config.json', {'quotas': {'math-code': 1}, 'languages': list(LANGUAGES),
        'second_review': True, 'calibration_policy': trial.POLICY})
    write_json(tmp_path / 'previous-hashes.json', [])
    for language in (*LANGUAGES, 'openhermes'):
        write_json(tmp_path / f'seeds-{language}.json', [])
    monkeypatch.setattr(pilot, 'training_renderer', lambda _: None)
    async def fail(*args):
        raise RuntimeError('blocked calibration')
    monkeypatch.setattr(trial, 'gate', fail)
    with pytest.raises(RuntimeError, match='blocked calibration'):
        asyncio.run(pilot.execute(tmp_path, ['http://127.0.0.1:1/v1'], concurrency=1))
    with sqlite3.connect(tmp_path / 'pilot.sqlite') as db:
        assert db.execute('SELECT count(*) FROM events').fetchone()[0] == 0
        assert db.execute('SELECT sum(attempts) FROM slots').fetchone()[0] == 0
    assert load(tmp_path / 'trial-outcomes.json')['groups']


def test_policy_or_model_removal_fails_closed(tmp_path):
    from dfm12.multilingual_tasks import MODEL
    config = dict(calibration_policy=trial.POLICY, second_review=True,
                  generator_model=MODEL, reviewer_model=MODEL, bulk_authorized=False)
    for key in config:
        altered = dict(config)
        del altered[key]
        write_json(tmp_path / 'pilot-config.json', altered)
        with pytest.raises(ValueError, match='policy/model'):
            trial.verify_inputs(tmp_path)


def test_preparation_allocates_700_and_pins_inputs(tmp_path, monkeypatch):
    from dfm12 import multilingual_prepare_calibrated as prep
    from dfm12.multilingual_seeds import LANGUAGES
    previous, root = tmp_path / 'donor', tmp_path / 'trial'
    previous.mkdir()
    for language in (*LANGUAGES, 'openhermes'):
        write_json(previous / f'seeds-{language}.json', [dict(id=f'{language}-{i}', text='Source',
            messages=[{'role': 'user', 'content': 'Q'}, {'role': 'assistant', 'content': 'A'}]) for i in range(3010)])
    write_json(previous / 'previous-hashes.json', [])
    write_json(previous / 'training-template.json', {})
    write_json(previous / 'seeds-ready.json', {})
    monkeypatch.setattr(prep, 'unused_snapshot', lambda _: {'events': 0})
    monkeypatch.setattr(prep, 'training_renderer', lambda _: None)
    def calibration(output, tokenizer):
        write_json(output / 'controls.json', calibration_cases())
        write_json(output / 'render-inspection/inspection.json', {'pins': {}, 'tokenizer_dir': str(tmp_path)})
    monkeypatch.setattr(prep, 'prepare_calibration', calibration)
    prep.prepare(previous, root)
    coverage = load(root / 'allocation-coverage.json')
    assert len(coverage['groups']) == 42
    assert sum(g['slots'] for g in coverage['groups']) == 700
    assert coverage['unique_allocated_sources'] == 490
    assert load(root / 'ready.json')['slots_per_language'] == dict.fromkeys(LANGUAGES, 100)
    assert not (root / 'cpu-preflight-passed.json').exists()
    write_json(root / 'pilot-config.json', {})
    with pytest.raises(ValueError):
        trial.verify_inputs(root, require_receipt=False)
    with pytest.raises(FileExistsError):
        prep.prepare(previous, root)


def test_runner_drift_fails_before_gpu_discovery(tmp_path, monkeypatch):
    from dfm12 import multilingual_run as runner
    (tmp_path / 'calibration').mkdir()
    monkeypatch.setattr(runner.signal, 'signal', lambda *args: None)
    def fail(_):
        raise ValueError('implementation drift')
    def forbidden(*args, **kwargs):
        pytest.fail('GPU discovery/server launch before verification')
    monkeypatch.setattr(trial, 'verify_inputs', fail)
    monkeypatch.setattr(runner.subprocess, 'check_output', forbidden)
    monkeypatch.setattr(runner.subprocess, 'Popen', forbidden)
    with pytest.raises(ValueError, match='implementation drift'):
        runner.run(tmp_path)


def test_measurement_only_root_cannot_generate(tmp_path, monkeypatch):
    from dfm12 import multilingual_pilot as pilot
    write_json(tmp_path / 'pilot-config.json', {'calibration_measurement_only': True})
    with pytest.raises(ValueError, match='cannot generate'):
        asyncio.run(pilot.execute(tmp_path, ['http://127.0.0.1:1/v1'], 2))
    assert not (tmp_path / 'pilot.sqlite').exists()


def test_evidence_gate_blocks_placeholder_despite_correct_booleans(tmp_path, monkeypatch):
    case = calibration_cases()[0]
    write_json(tmp_path / 'calibration/controls.json', [case])
    monkeypatch.setattr(trial, 'verify_inputs', lambda _: {
        'diagnostic_followup': True, 'review_options': {'variant': 'evidence4096'}})
    async def query(*args):
        return dict(literal_quote='15', back_translation='N/A', language_correct=True,
                    meaning_correct=True, constraints_met=True, issues=[])
    with pytest.raises(RuntimeError, match='zero generation'):
        asyncio.run(trial.gate(tmp_path, None, ['mock'], query))
    report = load(tmp_path / 'review-calibration.json')
    assert report['details'][0]['actual_keep'] is True
    assert report['passed'] is False and report['generation_authorized'] is False
    assert 'Missing meaningful literal evidence' in report['errors'][case['name']]
