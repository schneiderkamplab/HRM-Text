import pytest
from scripts import audit_fars_final_strict as audit


def test_only_actual_source_answer_sent():
    messages = [{'role': 'user', 'content': 'source'}, {'role': 'assistant', 'content': 'summary'}]
    import json
    assert json.loads(audit.request(messages)['messages'][1]['content']) == {'messages': messages}


def test_uncertainty_and_blank_comparison_cannot_pass():
    row = dict(comparison='Supported', **{f: 'pass' for f in audit.FIELDS})
    assert audit.passes(row)
    for f in audit.FIELDS:
        assert not audit.passes(dict(row, **{f: 'uncertain'}))
        assert not audit.passes(dict(row, **{f: 'fail'}))
    assert not audit.passes(dict(row, comparison=' '))


def test_false_accept_or_technical_blocks_calibration():
    cases = [dict(id=str(i), expected=i >= 7) for i in range(16)]
    outcomes = {c['id']: dict(status='complete', output=dict(comparison='Evidence',
        source_fidelity='pass' if c['expected'] else 'fail', required_coverage='pass',
        persian_readability='pass')) for c in cases}
    assert audit.assess(cases, outcomes)['calibrated']
    outcomes['0']['output']['source_fidelity'] = 'pass'
    assert not audit.assess(cases, outcomes)['calibrated']
    outcomes.pop('0')
    assert audit.assess(cases, outcomes)['technical'] == 1
    assert not audit.assess(cases, outcomes)['calibrated']
