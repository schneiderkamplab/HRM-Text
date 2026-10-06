from copy import deepcopy
import json
from pathlib import Path
import pytest
from scripts.prepare_dfm13_multilingual_evals import LANGUAGES, euro_registry
from scripts.headline_population_registry import validate_registry, build_population_row, Artifacts
from scripts.log_multilingual_headline_averages import PopulationItem


def population():
    metrics={l:{'dfm_la':dict(suite='dfm',key=f'dfm_eval/dala_{l}/f1',scale='fraction')} for l in LANGUAGES}
    return dict(schema_version=1,populations=[dict(id='dfm13_new_languages_v1',kind='dfm13_new_languages',
        languages=list(LANGUAGES),required_tasks=['dfm_la'],metrics=metrics)])


def test_scope_and_gaps_are_explicit():
    r=euro_registry()
    assert len(r['entries'])==130
    assert len(set(LANGUAGES))==13
    assert all(e['dataset'] is None for e in r['entries'] if e['language']=='fa')
    assert all(e['dataset'] is None for e in r['entries'] if e['task']=='tool-calling')
    assert all(e['metric_key'].startswith('euroeval/') for e in r['entries'] if e['dataset'])


def test_new_population_cannot_shrink_or_reuse_old_identifier():
    r=population();validate_registry(r)
    r['populations'][0]['id']='multilingual_v2'
    with pytest.raises(ValueError):validate_registry(r)
    r=population();r['populations'][0]['languages'].pop()
    with pytest.raises(ValueError):validate_registry(r)


def test_incomplete_population_never_emits_partial_mean(tmp_path):
    r=population()
    values={b['dfm_la']['key']:.8 for l,b in r['populations'][0]['metrics'].items() if l!='fa'}
    (tmp_path/'merged_metrics.json').write_text(json.dumps(values))
    row,_=build_population_row(PopulationItem(1,1,[],[tmp_path],[]),r)
    assert 'avg_population/dfm13_new_languages_v1/score' not in row
    assert row['avg_population/dfm13_new_languages_v1/expected_languages']==13


def test_complete_equal_language_weighting(tmp_path):
    r=population();values={b['dfm_la']['key']:(1 if l=='fa' else .5) for l,b in r['populations'][0]['metrics'].items()}
    (tmp_path/'merged_metrics.json').write_text(json.dumps(values))
    row,_=build_population_row(PopulationItem(1,1,[],[tmp_path],[]),r)
    assert row['avg_population/dfm13_new_languages_v1/score']==pytest.approx(7/13)


def test_versioned_talemaader_does_not_replace_legacy(tmp_path):
    old='dfm_eval/generative-talemaader/model_graded_fact/accuracy'
    new='dfm_eval/generative-talemaader/model_graded_fact_v2/accuracy'
    (tmp_path/'merged_metrics.json').write_text(json.dumps({old:.1}))
    (tmp_path/'merged_metrics_v2.json').write_text(json.dumps({new:.75,'dfm_eval/train_step':3150000}))
    a=Artifacts(PopulationItem(3150000,10,[],[tmp_path],[]))
    assert a.resolve(dict(suite='dfm',key=old,scale='fraction'))[0]==.1
    assert a.resolve(dict(suite='dfm',key=new,scale='fraction'))[0]==.75
    mismatch=Artifacts(PopulationItem(3200000,10,[],[tmp_path],[]))
    assert mismatch.resolve(dict(suite='dfm',key=new,scale='fraction'))[1]['status']=='checkpoint_mismatch'
