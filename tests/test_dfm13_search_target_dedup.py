from scripts import dfm13_search_target_dedup as dedup


def test_same_target_deduplicated_across_masks_and_later_messages():
    row = dict(tools=[], messages=[dict(role='user',content='question'), dict(role='assistant',content='answer'),
                                  dict(role='user',content='later'), dict(role='assistant',content='later answer')],
               target_message_indices=[1,3])
    first = dict(dedup.target_fingerprints(row))[1]
    other = dict(row, target_message_indices=[1], messages=row['messages'][:2])
    assert first == dict(dedup.target_fingerprints(other))[1]


def test_different_target_text_not_deduplicated():
    first = dict(tools=[], messages=[dict(role='user',content='q'),dict(role='assistant',content='a')],target_message_indices=[1])
    other = dict(first,messages=[dict(role='user',content='q'),dict(role='assistant',content='b')])
    assert dict(dedup.target_fingerprints(first))[1] != dict(dedup.target_fingerprints(other))[1]
