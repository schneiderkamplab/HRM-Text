import copy

import pytest

from dfm12 import multilingual_review_routed as routed
from dfm12 import multilingual_review_structured as text_review
from dfm12 import multilingual_review_tools as tool_review
from dfm12.multilingual_review import calibration_cases
from dfm12.multilingual_tool_calibration import routed_cases


def test_text_request_is_v3_plus_only_bullet_clarification():
    for case in calibration_cases():
        record = case['record']
        expected = text_review.request(record)
        expected['messages'][0]['content'] += routed.BULLETS
        assert routed.request(record) == expected
        assert not routed.uses_tools(record)
        assert 'Reject factual claims about current real-world' in expected['messages'][0]['content']
        assert 'A final JSON object is a legitimate' not in expected['messages'][0]['content']


def test_tool_definitions_alone_do_not_route_to_tool_rubric():
    record = copy.deepcopy(calibration_cases()[-1]['record'])
    record['tools'] = [{'type':'function','function':{'name':'unused','parameters':{'type':'object'}}}]
    assert not routed.uses_tools(record)
    assert routed.request(record)['messages'][0]['content'].endswith(routed.BULLETS)


def test_tool_request_is_v4_plus_review_literal_instruction():
    case = routed_cases()[-2]
    record = case['record']
    expected = tool_review.request(record)
    expected['messages'][0]['content'] += routed.LITERALS
    assert routed.request(record)==expected
    assert routed.uses_tools(record)
    assert 'not bare digits' in expected['messages'][0]['content']


def test_v5_all_inspected_controls_are_exposed():
    cases = routed_cases()
    assert len(cases)==242
    assert len({c['name'] for c in cases})==242
    assert all(c['split']=='exposed_regression' for c in cases[:228])
    assert sum(c['expected_keep'] for c in cases[228:])==7
    assert all(c['split']=='fresh_variant' for c in cases[228:])
    for case in cases[228:]:
        checks = routed.deterministic_checks(case['record'])
        assert all(c['passed'] for c in checks)==case['expected_keep']


def test_text_review_still_rejects_placeholders_and_preserves_decisions():
    record = calibration_cases()[-1]['record']
    review = dict(message_index=1,literal_quote='15',back_translation='The number fifteen.',
                  language_correct=True,meaning_correct=True,constraints_met=True,issues=[])
    assert routed.keeps(review,record)
    for text in ('15','N/A','Looks good.'):
        with pytest.raises(ValueError):
            routed.keeps(dict(review,back_translation=text),record)
