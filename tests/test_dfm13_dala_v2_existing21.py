from copy import deepcopy
import json
from scripts.prepare_dfm13_dala_v2_existing21 import ROOT,LANGUAGES,average_definitions
from scripts.merge_dfm_eval_shards import task_metrics,wandb_task_name
from scripts.headline_population_registry import build_population_row
from scripts.log_multilingual_headline_averages import PopulationItem


def test_successor_keeps_historical_bindings_and_requires_both_versions():
    original=json.loads((ROOT/'config/multilingual_headline_populations_dfm13_20261006.json').read_text())
    before=deepcopy(original);new=average_definitions(original)
    assert original==before
    for old,pop in zip(original['populations'],new['populations']):
        for language,metrics in old['metrics'].items():
            assert all(pop['metrics'][language][k]==v for k,v in metrics.items())
            if language in LANGUAGES:
                assert set(pop['metrics'][language])-set(metrics)=={'dfm_la_v2','dfm_gec_v2'}
                assert pop['id'].endswith('_v2')
            else:assert pop['metrics'][language]==metrics
    assert len(LANGUAGES)==21


def test_versioned_merge_preserves_namespace_and_historical_semantics():
    for language in LANGUAGES:
        samples=[dict(target=t,metadata={'language':language},output={'completion':t})
                 for t in ('correct','incorrect')]
        name='dala_v2_'+language
        assert task_metrics(name,samples)==task_metrics('dala_'+language,samples)
        assert task_metrics(name,samples)['semantic_v1/macro_f1']==1
        assert wandb_task_name(name)==name
        gec=[dict(scores={'gec_dala_scorer':{'value':{'exact_match':1}}})]
        assert task_metrics('gec_dala_v2_'+language,gec)['exact_match/mean']==1


def test_old_scores_alone_cannot_complete_successor(tmp_path):
    original=json.loads((ROOT/'config/multilingual_headline_populations_dfm13_20261006.json').read_text())
    successor=average_definitions(original)
    values={b['key']:(100 if b['scale']=='percent' else 1)
            for pop in original['populations'] for metrics in pop['metrics'].values() for b in metrics.values()}
    (tmp_path/'merged_metrics.json').write_text(json.dumps(values))
    row,_=build_population_row(PopulationItem(1,1,[],[tmp_path],[tmp_path]),successor)
    assert 'avg_population/dfm13_all_languages_v2/score' not in row
    assert 'avg_population/dfm13_multilingual_v2/score' not in row
    assert row['avg_population/dfm13_new_languages_v1/score']==1
    for pop in successor['populations']:
        for bindings in pop['metrics'].values():
            for b in bindings.values():values[b['key']]=100 if b['scale']=='percent' else 1
    (tmp_path/'merged_metrics.json').write_text(json.dumps(values))
    row,_=build_population_row(PopulationItem(1,1,[tmp_path],[tmp_path],[tmp_path]),successor)
    assert row['avg_population/dfm13_all_languages_v2/score']==1
    assert row['avg_population/dfm13_multilingual_v2/score']==1
