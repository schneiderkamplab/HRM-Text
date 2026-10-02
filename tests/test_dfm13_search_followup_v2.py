from collections import Counter

import pytest

from scripts import dfm13_search_followup_v2 as module


def test_eight_workers_per_endpoint():
    endpoints = [f'http://127.0.0.1:{8800+i}' for i in range(8)]
    slots = module.worker_slots(endpoints, 8)
    assert len(slots) == 64
    assert Counter(slots) == dict.fromkeys(endpoints, 8)


@pytest.mark.parametrize('value', [0, -1, 9, True, '8'])
def test_invalid_concurrency(value):
    with pytest.raises(ValueError):
        module.worker_slots(['endpoint'], value)


def test_tail_evidence_keeps_exact_offsets():
    body = 'Unrelated navigation text. ' * 600 + 'Zebratest camera has 200 megapixels. ' * 30
    pages = module.excerpts({'data': [{'url': 'https://example.org/article', 'content': body}]},
                            'Zebratest camera megapixels', max_chunks=2)
    page = pages['https://example.org/article']
    assert '200 megapixels' in page['body']
    assert any(c['start'] > 10000 for c in page['excerpts'])
    for chunk in page['excerpts']:
        assert body[chunk['start']:chunk['end']] == chunk['text']


def test_blocked_content_not_evidence():
    assert not module.excerpts({'data': [{'url': 'https://example.org',
        'content': 'Access denied ' * 100}]}, 'example')
