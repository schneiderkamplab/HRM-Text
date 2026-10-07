from types import SimpleNamespace
import pytest
from scripts.headline_population_registry import (
    load_registry, enable_available_dfm13, build_population_row_from_metrics,
    validate_registry, definition_hash,
)


def test_available_language_weighting_no_imputation_and_explicit_optin():
    source=load_registry('config/multilingual_headline_populations_dfm13_dala_v2_20261006.json')
    registry=enable_available_dfm13(source)
    pop=next(p for p in registry['populations'] if p['id']=='dfm13_all_languages_v2')
    bindings=lambda lang:[b for b in pop['metrics'][lang].values() if b and b['scale']=='fraction']
    da,en=bindings('da'),bindings('en')
    metrics={da[0]['key']:.2,da[1]['key']:.6,en[0]['key']:.9}
    item=SimpleNamespace(step=100,epoch=1)
    row,report=build_population_row_from_metrics(metrics,item,registry)
    base='avg_population/'+pop['id']
    assert row[base+'/languages/da/score']==pytest.approx(.4)
    assert row[base+'/score']==pytest.approx(.65)
    assert row[base+'/available_languages']==2
    assert row[base+'/complete_languages']==0 and row[base+'/complete']==0
    assert row[base+'/definition_sha256']==definition_hash(pop)
    strict,_=build_population_row_from_metrics(metrics,item,source)
    assert base+'/score' not in strict
    empty,_=build_population_row_from_metrics({},item,registry)
    assert base+'/score' not in empty
    assert all('aggregation_policy' not in p for p in source['populations'])


def test_legacy_policy_rejected():
    from tests.test_multilingual_headline_populations import manifest
    old=manifest()
    assert enable_available_dfm13(old)==old
    old['populations'][0]['aggregation_policy']='available_tasks_then_available_languages_v1'
    with pytest.raises(ValueError):validate_registry(old)
