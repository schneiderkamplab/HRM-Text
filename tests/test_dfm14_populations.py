import copy
from types import SimpleNamespace
import pytest
from scripts.headline_population_registry import (
    validate_registry, enable_available_dfm14, build_population_row_from_metrics,
)

NEW = 'ga mt mk eu gl cy ru tr zh ar ja id ko hi vi he'.split()
OLD = 'lt lv sq be bs bg hr hu lb sr sk sl fa nb nn sv is fo nl pl de fr es it cs pt_pt fi et ca el ro uk'.split()


def registry(kind):
    languages = NEW + ([] if kind == 'new_languages' else OLD)
    if kind == 'all_languages': languages += ['da','en']
    p=dict(id=f'dfm14_{kind}_v1',kind=f'dfm14_{kind}',languages=languages,
           required_tasks=['la','gec'],metrics={lang:{task:{'suite':'dfm',
           'key':f'dfm_eval/{task}_{lang}/score','scale':'fraction'}
           for task in ('la','gec')} for lang in languages})
    return {'schema_version':1,'populations':[p]}


@pytest.mark.parametrize('kind,count',[('new_languages',16),('multilingual',48),('all_languages',50)])
def test_exact_population_and_version(kind,count):
    r=registry(kind);validate_registry(r)
    assert len(r['populations'][0]['languages'])==count
    for bad in ('dfm14_'+kind+'_v0','dfm13_'+kind+'_v1'):
        changed=copy.deepcopy(r);changed['populations'][0]['id']=bad
        with pytest.raises(ValueError):validate_registry(changed)
    changed=copy.deepcopy(r);changed['populations'][0]['languages'][0]='xx'
    with pytest.raises(ValueError):validate_registry(changed)


def test_optin_partial_no_zeros_and_no_mutation():
    original=registry('all_languages');r=enable_available_dfm14(original)
    item=SimpleNamespace(step=3250000,epoch=1)
    metrics={'dfm_eval/la_ga/score':.2,'dfm_eval/gec_ga/score':.6,'dfm_eval/la_ja/score':.8}
    strict,_=build_population_row_from_metrics(metrics,item,original)
    row,_=build_population_row_from_metrics(metrics,item,r)
    base='avg_population/dfm14_all_languages_v1'
    assert base+'/score' not in strict
    assert row[base+'/score']==pytest.approx(.6)
    assert row[base+'/available_languages']==2 and row[base+'/complete_languages']==1
    assert row[base+'/valid_metrics']==3 and row[base+'/expected_metrics']==100
    assert row[base+'/coverage']==.03 and row[base+'/complete']==0
    assert base+'/languages/he/score' not in row
    assert 'aggregation_policy' not in original['populations'][0]


def test_dfm14_optin_does_not_change_dfm13():
    from scripts.headline_population_registry import load_registry
    old=load_registry('config/multilingual_headline_populations_dfm13_dala_v2_20261006.json')
    assert enable_available_dfm14(old)==old
