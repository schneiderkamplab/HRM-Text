import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'eval_scheduler'))
from eval_scheduler.runtime import euroeval_language_args


def test_existing_euroeval_filter_unchanged():
    assert euroeval_language_args(SimpleNamespace(metadata={})) == [
        '--language', 'da', '--language', 'en']


def test_multilingual_result_filter_is_explicit():
    assert euroeval_language_args(SimpleNamespace(metadata={'euroeval_languages': ['nb','nn']})) == [
        '--language', 'nb', '--language', 'nn']
    assert euroeval_language_args(SimpleNamespace(metadata={'euroeval_languages': ['pt-pt']})) == [
        '--language', 'pt-pt']


@pytest.mark.parametrize('value', ['nl', [], ['--flag'], [None]])
def test_bad_language_filter_fails_closed(value):
    with pytest.raises(ValueError):
        euroeval_language_args(SimpleNamespace(metadata={'euroeval_languages': value}))


def test_multilingual_merge_pools_samples_not_shard_f1():
    from scripts.merge_dfm_eval_shards import task_metrics, wandb_task_name
    samples = [{'target': target, 'output': {'completion': prediction},
        'scores': {'linguistic-acceptability': {'metadata': {
        'target': target, 'prediction': prediction}}}} for target,prediction in
        [('correct','correct'),('incorrect','incorrect'),('incorrect',None)]]
    assert task_metrics('dala_nl',samples)==task_metrics('dala',samples)
    assert task_metrics('dala_nl',samples)['linguistic-acceptability/n']==3
    assert wandb_task_name('dala_nl')=='dala_nl'


def test_multilingual_gec_merge_retains_exact_match():
    from scripts.merge_dfm_eval_shards import task_metrics
    samples=[{'scores':{'gec_dala_scorer':{'value':{'exact_match':1.0}}}},
             {'scores':{'gec_dala_scorer':{'value':{'exact_match':0.0}}}}]
    assert task_metrics('gec_dala_en',samples)['exact_match/mean']==0.5
