import pytest

from scripts.merge_dfm_eval_shards import task_metrics


def test_judgment_only_metrics_are_versioned():
    samples = [{'scores': {'model_graded_fact_v2': {'value': v}}} for v in (0, 0.5, 1)]
    result = task_metrics('generative_talemaader', samples)
    assert result['model_graded_fact_v2/accuracy'] == 0.5
    assert result['model_graded_fact_v2/n'] == 3
    assert 'model_graded_fact/accuracy' not in result


def test_missing_versioned_score_is_not_silently_wrong_or_omitted():
    samples = [{'scores': {'model_graded_fact_v2': {'value': 1}}}, {'scores': {}}]
    with pytest.raises(ValueError, match='Incomplete'):
        task_metrics('generative_talemaader', samples)


def test_legacy_scores_are_not_relabelled():
    result = task_metrics('generative_talemaader', [{'scores': {'model_graded_fact': {'value': 'C'}}}])
    assert result['model_graded_fact/accuracy'] == 1
    assert 'model_graded_fact_v2/accuracy' not in result
