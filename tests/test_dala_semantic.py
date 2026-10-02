import pytest

from scripts.dala_semantic import NATIVE, extract_semantic_label, semantic_pairs
from scripts.merge_dfm_eval_shards import semantic_dala_metrics, task_metrics


@pytest.mark.parametrize('language', list(NATIVE))
def test_native_and_english_labels(language):
    positive, negative = NATIVE[language]
    for label in positive | {'yes', 'correct', 'right'}:
        assert extract_semantic_label('  "'+label.upper()+'."\n', language) == 'correct'
    for label in negative | {'no', 'incorrect', 'wrong'}:
        assert extract_semantic_label('**'+label+'!**', language) == 'incorrect'
    for bad in ['yes/no', 'yes, no', 'yes, it is correct', 'not correct at all', '', '...', 'maybe']:
        assert extract_semantic_label(bad, language) is None


def test_no_first_match_and_truncation():
    assert extract_semantic_label('Ikke korrekt.', 'da') == 'incorrect'
    assert extract_semantic_label('Det er ikke korrekt.', 'da') is None
    sample = dict(target='correct', output=dict(completion='yes',choices=[dict(stop_reason='max_tokens')]))
    assert semantic_pairs([sample], 'en') == [('correct',None)]


def test_invalid_not_removed_from_denominator():
    samples = [dict(target='correct',output=dict(completion='Yes.')),
               dict(target='incorrect',output=dict(completion='unclear'))]
    scores = semantic_dala_metrics(samples, 'en')
    assert scores['semantic_v1/accuracy'] == 0.5
    assert scores['semantic_v1/invalid_rate'] == 0.5
    assert scores['semantic_v1/macro_f1'] == 0.5


def test_merge_preserves_strict_and_adds_semantic():
    samples = [dict(target=target, output=dict(completion=answer),
                    scores={'linguistic-acceptability': {'metadata':
                        {'target': target, 'prediction': '__invalid__'}}})
               for target, answer in [('correct', 'Sí.'), ('incorrect', 'No.')]]
    result = task_metrics('dala_es', samples)
    assert result['linguistic-acceptability/dfm_evals_macro_f1'] == 0
    assert result['linguistic-acceptability/n'] == 2
    assert result['semantic_v1/macro_f1'] == 1
    assert result['semantic_v1/accuracy'] == 1
