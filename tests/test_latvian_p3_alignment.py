from dfm12 import latvian_p3_alignment as m


def test_exact_question_match_not_ordinal_or_casefold():
    a = dict(question='Does it contain DNA?'); b = dict(question='Does it NOT contain DNA?')
    index = {m.question_key('arc', a['question']): [a], m.question_key('arc', b['question']): [b]}
    assert m.english_match('arc', b['question'], index) == b
    assert m.english_match('other', b['question'], index) is None
    assert m.english_match('arc', 'does it contain dna?', index) is None
    index[m.question_key('arc', a['question'])].append(dict(a))
    assert m.english_match('arc', a['question'], index) is None


def test_transport_whitespace_only():
    assert m.question_key('x', ' A\r\nB ') == m.question_key('x', 'A\nB')
    assert m.question_key('x', 'A B') != m.question_key('x', 'AB')


def test_31b_requests_preserve_full_target_and_no_expected_label():
    import json
    record = dict(messages=[dict(role='assistant', content='Full answer. '*1000)],
                  source_alignment_status='unverified_bilingual_proposal_not_ordinal_proof')
    for repair in (False, True):
        request = m.request(record, repair)
        assert request['model'] == 'google/gemma-4-31B-it'
        assert json.loads(request['messages'][1]['content']) == record
        assert 'expected' not in request
