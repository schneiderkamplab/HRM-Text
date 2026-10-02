from dfm12.review_norwegian_benchmarks import compare, flattened


def test_context_overlap_is_not_question_leakage():
    train = [{"context": "shared\n passage", "question": "Training question?"},
             {"context": "other", "question": "Other?"}]
    refs = [{"context": "shared passage", "question": "Test question?"}]
    result = compare(train, refs + refs)
    assert result["train_context_matches"] == 1
    assert result["train_question_matches"] == 0
    assert result["train_context_question_matches"] == 0


def test_only_answerable_source_rows_are_counted():
    payload = {"data": [{"paragraphs": [{"context": "Text", "qas": [
        {"question": "Yes?", "answers": [{"text": "Yes"}]},
        {"question": "No?", "answers": []},
        {"question": "Impossible?", "answers": [{"text": "No"}], "is_impossible": True},
    ]}]}]}
    assert flattened(payload) == [{"context": "Text", "question": "Yes?"}]
