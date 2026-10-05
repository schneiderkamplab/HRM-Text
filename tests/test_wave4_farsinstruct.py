from dfm12.wave4_farsinstruct import SELECTIONS, messages


def test_only_direct_templates():
    assert set(SELECTIONS) == {'farstail', 'pn_sum', 'wiki_sum', 'persian_qa', 'parsinlu_comp'}
    assert messages({'template': 'generate_reason'}, 'summarize_the_article') is None


def test_preserves_question_and_answer():
    row = {'template': 'answer_Q_A', 'inputs': 'passage and question', 'outputs': 'answer'}
    assert messages(row, 'answer_Q_A') == [
        {'role': 'user', 'content': row['inputs']},
        {'role': 'assistant', 'content': row['outputs']}]
