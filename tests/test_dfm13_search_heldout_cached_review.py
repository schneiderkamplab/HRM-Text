import pytest
from scripts import dfm13_search_heldout_cached_review as review


def test_payload_uses_original_date_and_no_manual_or_model_label():
    packet = dict(sample=dict(prompt='original', original_timestamp='2025-01-01'), answer='same',
        candidate=dict(messages=[dict(role='assistant', content='same')]), pages={},
        manual_review='reject', model_review='keep')
    value = review.payload(packet)
    assert value['requirements']['original_timestamp'] == '2025-01-01'
    assert 'manual_review' not in value and 'model_review' not in value
    packet['answer'] = 'different'
    with pytest.raises(ValueError, match='mismatch'):
        review.payload(packet)
