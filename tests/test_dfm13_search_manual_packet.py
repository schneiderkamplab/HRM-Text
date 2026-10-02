import json
import pytest
from scripts import dfm13_search_manual_packet as manual


def test_answer_and_evidence_come_from_same_exact_trajectory():
    evidence = dict(url='https://example.org', body='actual observation')
    candidate = dict(messages=[dict(role='user', content='prompt'),
        dict(role='tool', content=json.dumps(dict(results=[evidence]))),
        dict(role='assistant', content='exact saved answer')])
    result = manual.packet(candidate, dict(id='row'))
    assert result['answer'] == result['candidate']['messages'][-1]['content']
    assert result['pages']['https://example.org'] == evidence
    assert 'review' not in result and 'expected' not in result


def test_url_without_content_is_not_evidence():
    candidate = dict(messages=[dict(role='tool', content='{"results":[{"url":"https://example.org"}]}'),
                               dict(role='assistant', content='answer')])
    with pytest.raises(ValueError, match='no actual delivered'):
        manual.packet(candidate, dict(id='row'))
