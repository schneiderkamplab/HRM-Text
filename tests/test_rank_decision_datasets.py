from scripts.rank_decision_datasets import dataset_key, scores, render


def test_shards_group_but_subtasks_remain():
    assert dataset_key('foo__train-00001.parquet:native') == 'foo'
    assert dataset_key('flan__niv2_zsopt_data__task12_entailment.parquet') == dataset_key('flan__niv2_fsopt_data__task12_entailment.parquet')
    assert dataset_key('tasksource__snli.parquet') != dataset_key('tasksource__mnli.parquet')


def test_scoring_and_generative_caution():
    s = scores('when2call', 'direct_labels')
    assert s['relevance'] == 5 and s['ease'] == 4
    assert 89 < s['aggregate'] < 90
    assert scores('nli_question_generation', 'direct_labels')['ease'] <= 2
    assert scores('dataset/test', 'direct_labels')['aggregate'] == 0


def test_remote_path_and_unresolved_remain_explicit():
    r = dict(rank=1, dataset='example', cluster='code', **scores('example', 'code'),
             epoch_rows=2, epoch_tokens=100, stored_tokens=100, hf_ids=[],
             text_paths={}, native_repair=True, source_keys=['example__train.jsonl'])
    text = render({'datasets': [r]})
    assert 'UNRESOLVED' in text and 'Representation warning' in text
    assert 'tokens.npy' not in text
