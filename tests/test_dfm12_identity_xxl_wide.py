import copy

import pytest

from dfm12.identity_xxl_wide import adapt, PROFILE, PROFILE_TEXT, WIDTH_QA, DIMENSION_REPAIRS


def test_profile_conversion_preserves_historical_and_team_claims():
    row = dict(id='parent', language='en', profile='xl-full-bp',
        messages=[dict(role='user', content='Describe your XL profile.'),
                  dict(role='assistant', content='XL has 16 layers in L and 16 in H. Mimir v1 used five backpropagation steps. Peter Schneider-Kamp leads the team.')],
        audit_context=dict(facts={'v1': 'five steps'}, profile={}), rendered_tokens=10)
    original = copy.deepcopy(row)
    result = adapt(row)
    assert row == original
    assert result['profile'] == PROFILE
    assert result['messages'][1]['content'] == original['messages'][1]['content'].replace('XL', 'XXL-wide')
    assert result['audit_context']['facts'] == original['audit_context']['facts']
    assert 'rendered_tokens' not in result
    assert result['id'] != row['id']
    assert '2560' in PROFILE_TEXT and 'num_heads=20' in PROFILE_TEXT


def test_reject_other_profiles_and_cover_all_languages():
    with pytest.raises(ValueError):
        adapt({'profile': 'generic'})
    from dfm12.identity_multilingual_queue import LANGUAGES
    assert set(WIDTH_QA) == set(LANGUAGES)
    assert len(WIDTH_QA) == 21
    for question, answer in WIDTH_QA.values():
        assert question and all(x in answer for x in ('2560', '20', '128'))


def test_known_unknown_dimension_claims_are_corrected_not_left_to_judge():
    for old, replacement in DIMENSION_REPAIRS.items():
        record = dict(id='parent', language='en', profile='xl-full-bp',
                      messages=[dict(role='assistant', content=old)], audit_context={'profile': {}})
        assert adapt(record)['messages'][0]['content'] == replacement
