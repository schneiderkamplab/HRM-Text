from scripts.dfm13_search_budgeted_batch1 import filtered_paragraphs, SELECTION, INSTRUCTION


def test_eight_only_and_known_holds_excluded():
    assert len(SELECTION) == 8
    assert not set(SELECTION) & {'0bdd931b', '64b59e0d', 'bfd8c382', '032d2d0c'}


def test_filter_preserves_exact_supported_paragraph():
    body = 'This complete paragraph describes the actual historical event and gives enough substantive detail to distinguish it from navigation.'
    payload = {'data': [{'url': 'https://example.org', 'title': 'Title', 'content': 'Please subscribe to our newsletter and read our privacy policy.\n\n' + body}]}
    chunks = filtered_paragraphs(payload, ['https://example.org'])
    assert len(chunks) == 1
    assert chunks[0]['text'] == body
    assert payload['data'][0]['content'][chunks[0]['start']:chunks[0]['end']] == body
    assert not filtered_paragraphs(payload, ['https://other.org'])


def test_instruction_requires_variant_and_date_discipline():
    assert 'Base versus Instruct/post-trained' in INSTRUCTION
    assert 'original question date' in INSTRUCTION
    assert 'not independent verification' in INSTRUCTION
