import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('step,epoch,expected', [(100,10,'valid'),(0,10,'checkpoint_mismatch'),(99,10,'checkpoint_mismatch'),
                                               (0,9,'checkpoint_mismatch'),(False,10,'checkpoint_mismatch')])
def test_legacy_duplicate_root_zero_step_epoch_binding(tmp_path, step, epoch, expected):
    root = tmp_path/'epoch_10'
    key = 'euroeval/en/sentiment-classification/sst5/macro_f1'
    put(root, 'epoch_2/sst5/merged_metrics.json', {key:75,'euroeval/train_step':step,'euroeval/epoch':epoch})
    artifacts = registry.Artifacts(cli.PopulationItem(100,10,[],[],[root/'epoch_10']))
    value, detail = artifacts.resolve(dict(suite='euroeval',key=key,scale='percent'))
    assert detail['status'] == expected
    assert artifacts.root_recoveries == [{'requested':str(root/'epoch_10'),'resolved':str(root)}]
    if expected == 'valid':
        assert value == .75 and detail['checkpoint_binding'] == 'requested_root'


def test_no_campaign_fallback_or_unbound_zero_step(tmp_path):
    root = tmp_path/'campaign'
    key = 'euroeval/en/sentiment-classification/sst5/macro_f1'
    put(root, 'epoch_2/merged_metrics.json', {key:75,'euroeval/train_step':0,'euroeval/epoch':10})
    binding = dict(suite='euroeval',key=key,scale='percent')
    unbound = registry.Artifacts(cli.PopulationItem(100,10,[],[],[root]))
    assert unbound.resolve(binding)[1]['status'] == 'checkpoint_mismatch'
    missing = registry.Artifacts(cli.PopulationItem(100,10,[],[],[root/'epoch_10']))
    assert missing.resolve(binding)[1]['status'] == 'missing'
    assert not missing.root_recoveries

from scripts import headline_population_registry as registry
from scripts import log_multilingual_headline_averages as cli
from scripts import log_dfm5_headline_averages as legacy


LANGUAGES = 'nb nn sv is fo nl pl de fr es it pt fi et lv lt cs sk uk'.split()


def manifest(languages=None, kind='multilingual'):
    languages = list(languages or LANGUAGES)
    tasks = ['la', 'gec']
    identifier = {'multilingual': 'multilingual_v1', 'english_dfm': 'english_dfm_v1', 'english': 'english_v2'}[kind]
    return {'schema_version': 1, 'populations': [dict(id=identifier, kind=kind, languages=languages, required_tasks=tasks,
        metrics={lang: {task: dict(suite='dfm', key=f'dfm_eval/{lang}-{task}/accuracy', scale='fraction') for task in tasks}
                 for lang in languages})]}


def put(root, relative, values):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values))
    return path


def item(root):
    return cli.PopulationItem(100, 1.5, [root/'standard'], [root/'dfm'], [root/'euro'])


def complete(root, value=.6):
    return put(root/'dfm', 'nested/tasks/merged_metrics.json', {'metrics': {
        f'dfm_eval/{lang}-{task}/accuracy': value for lang in LANGUAGES for task in ('la','gec')}})


def test_complete_equal_language_mean(tmp_path):
    path = complete(tmp_path)
    data = json.loads(path.read_text())
    data['metrics']['dfm_eval/nb-la/accuracy'] = 1
    data['metrics']['dfm_eval/nb-gec/accuracy'] = 1
    path.write_text(json.dumps(data))
    row, _ = registry.build_population_row(item(tmp_path), manifest())
    assert row['avg_population/multilingual_v1/score'] == pytest.approx((1+18*.6)/19)
    assert row['avg_population/multilingual_v1/complete_languages'] == 19
    assert row['avg_population/multilingual_v1/expected_metrics'] == 38


def test_one_missing_no_partial_population_score(tmp_path):
    path = complete(tmp_path)
    data = json.loads(path.read_text())
    del data['metrics']['dfm_eval/nb-la/accuracy']
    path.write_text(json.dumps(data))
    row, report = registry.build_population_row(item(tmp_path), manifest())
    assert 'avg_population/multilingual_v1/score' not in row
    assert 'avg_population/multilingual_v1/languages/nb/score' not in row
    assert row['avg_population/multilingual_v1/valid_metrics'] == 37
    assert report['populations']['multilingual_v1']['languages']['nb']['la']['status'] == 'missing'


@pytest.mark.parametrize('bad',[True, False, '0.9', float('nan'), float('inf'), -1, 101, {}, []])
def test_invalid_numbers_not_clamped_or_coerced(bad):
    assert registry.normalize(bad, 'fraction') is None
    assert registry.normalize(bad, 'percent') is None


def test_units_explicit_even_for_small_percent():
    assert registry.normalize(.5, 'percent') == .005
    assert registry.normalize(.5, 'fraction') == .5
    assert registry.normalize(1.01, 'fraction') is None


def test_source_collision_cannot_overwrite(tmp_path):
    complete(tmp_path)
    put(tmp_path/'dfm', 'other/merged_metrics.json', {'dfm_eval/nb-la/accuracy': .6})
    row, report = registry.build_population_row(item(tmp_path), manifest())
    assert 'avg_population/multilingual_v1/score' not in row
    assert report['populations']['multilingual_v1']['languages']['nb']['la']['status'] == 'ambiguous'
    resolved = manifest()
    resolved['populations'][0]['metrics']['nb']['la']['artifact'] = 'nested/tasks/merged_metrics.json'
    row, _ = registry.build_population_row(item(tmp_path), resolved)
    assert row['avg_population/multilingual_v1/score'] == pytest.approx(.6)


def test_other_suite_cannot_supply_missing_metric(tmp_path):
    put(tmp_path/'euro', 'x/merged_metrics.json', {'dfm_eval/nb-la/accuracy': .7})
    _, report = registry.build_population_row(item(tmp_path), manifest())
    assert report['populations']['multilingual_v1']['languages']['nb']['la']['status'] == 'missing'


def test_english_pair_separate_namespace_and_additional_roots(tmp_path):
    roots = item(tmp_path)
    second = tmp_path/'older'
    roots = cli.PopulationItem(100, 1.5, [], roots.dfm_root+[second], [])
    put(tmp_path/'dfm', 'la/merged_metrics.json', {'dfm_eval/en-la/accuracy': .9})
    put(second, 'gec/merged_metrics.json', {'dfm_eval/en-gec/accuracy': .7})
    row, _ = registry.build_population_row(roots, manifest(['en'], 'english_dfm'))
    assert row['avg_population/english_dfm_v1/score'] == pytest.approx(.8)
    assert not any(key.startswith('avg/') for key in row)


def test_null_binding_prevents_complete(tmp_path):
    complete(tmp_path)
    data = manifest()
    data['populations'][0]['metrics']['nb']['la'] = None
    row, report = registry.build_population_row(item(tmp_path), data)
    assert row['avg_population/multilingual_v1/complete'] == 0
    assert report['populations']['multilingual_v1']['languages']['nb']['la']['status'] == 'unavailable'


@pytest.mark.parametrize('mutation', ['duplicate_language','da','missing_task','duplicate_metric','wrong_suite','path','english_old'])
def test_manifest_fail_closed(mutation):
    data = manifest()
    pop = data['populations'][0]
    if mutation == 'duplicate_language': pop['languages'][-1] = 'nb'
    elif mutation == 'da': pop['languages'][-1] = 'da'
    elif mutation == 'missing_task': del pop['metrics']['nb']['la']
    elif mutation == 'duplicate_metric': pop['metrics']['nb']['gec'] = pop['metrics']['nb']['la']
    elif mutation == 'wrong_suite': pop['metrics']['nb']['la']['suite'] = 'standard'
    elif mutation == 'path': pop['metrics']['nb']['la']['artifact'] = '../escape.json'
    else: data = manifest(['en'], 'english'); data['populations'][0]['id'] = 'english_v1'
    with pytest.raises(ValueError): registry.validate_registry(data)


def test_checkpoint_mismatch(tmp_path):
    complete(tmp_path)
    path = tmp_path/'dfm/nested/tasks/merged_metrics.json'
    data = json.loads(path.read_text())
    data['metrics']['dfm_eval/train_step'] = 99
    path.write_text(json.dumps(data))
    row, report = registry.build_population_row(item(tmp_path), manifest())
    assert row['avg_population/multilingual_v1/complete'] == 0
    assert report['populations']['multilingual_v1']['languages']['nb']['la']['status'] == 'checkpoint_mismatch'


def test_duplicate_json_keys_rejected(tmp_path):
    path = tmp_path/'bad.json'
    path.write_text('{"schema_version":1,"schema_version":1,"populations":[]}')
    with pytest.raises(ValueError, match='Duplicate'): registry.load_registry(path)


def test_euroeval_percent_not_inferred(tmp_path):
    data = manifest()
    complete(tmp_path)
    data['populations'][0]['metrics']['nb']['la'] = dict(suite='euroeval', key='euroeval/nb/la/dataset/f1', scale='percent')
    put(tmp_path/'euro', 'epoch_1/test/merged_metrics.json', {'euroeval/nb/la/dataset/f1': .5})
    row, _ = registry.build_population_row(item(tmp_path), data)
    assert row['avg_population/multilingual_v1/languages/nb/score'] == pytest.approx((.005+.6)/2)


def test_legacy_population_unchanged(tmp_path):
    before = copy.deepcopy(legacy.SECTION_KEYS)
    baseline = legacy.build_row(legacy.EvalItem(100,1.5,tmp_path/'s',tmp_path/'d',tmp_path/'e'), metric_prefix='avg')
    registry.build_population_row(item(tmp_path), manifest())
    assert legacy.SECTION_KEYS == before
    assert legacy.build_row(legacy.EvalItem(100,1.5,tmp_path/'s',tmp_path/'d',tmp_path/'e'), metric_prefix='avg') == baseline


def test_wandb_atomic_explicit_registration_only_mock():
    calls = []
    fake = SimpleNamespace(init=lambda **kw: SimpleNamespace(finish=lambda: calls.append(('finish',))),
        define_metric=lambda *a, **kw: calls.append(('define',a,kw)), log=lambda *a, **kw: calls.append(('log',a,kw)))
    row = {'avg_population/epoch':1, 'avg_population/english_dfm_v1/complete':0}
    cli.log_atomic(fake,row,project='test',run_id='test',run_name='test')
    assert len([c for c in calls if c[0]=='log']) == 1
    assert {c[1][0] for c in calls if c[0]=='define'} == set(row)
    assert next(c for c in calls if c[0]=='log')[2]['commit'] is True


def test_cli_dry_run_never_imports_wandb(tmp_path, monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, 'wandb', None)
    complete(tmp_path)
    path = tmp_path/'manifest.json'
    path.write_text(json.dumps(manifest()))
    result = cli.main(['--manifest',str(path),'--dfm-root',str(tmp_path/'dfm'),'--step','100','--epoch','1.5','--dry-run'])
    assert result['row']['avg_population/multilingual_v1/complete'] == 1


def test_concrete_registry_preserves_sources_exclusions_and_english_population():
    import yaml
    base = Path(__file__).resolve().parents[1]
    actual = registry.load_registry(base/'config/multilingual_headline_populations_20260930.json')
    dfm = json.loads((base/'config/dfm_dala_heldout_20260930.json').read_text())
    euro = yaml.safe_load((base/'config/euroeval_dfm12_multilingual.yaml').read_text())
    multilingual, pair, english = actual['populations']
    assert multilingual['languages'] == dfm['multilingual_languages']
    assert 'pt_pt' in multilingual['languages']
    for entry in euro['entries']:
        bound = multilingual['metrics'][entry['language']].get('euroeval_'+entry['category'])
        if bound is not None:
            assert bound['key'] == entry['metric_key'] and bound['scale'] == 'percent'
            assert entry.get('catalog_status', entry['status']) == 'supported'
        else:
            assert not entry['include_in_average']
    assert {b['key'] for b in english['metrics']['en'].values()} == set(legacy.ENGLISH_KEYS) | {
        'dfm_eval/dala_en/linguistic-acceptability/dfm_evals_macro_f1',
        'dfm_eval/gec_dala_en/exact_match/mean'}
    assert len(english['required_tasks']) == 17


def test_concrete_registry_requires_all_available_clean_tasks(tmp_path):
    data = registry.load_registry(Path(__file__).resolve().parents[1]/'config/multilingual_headline_populations_20260930.json')
    values = {s: {} for s in registry.SUITES}
    for pop in data['populations']:
        for tasks in pop['metrics'].values():
            for bound in tasks.values():
                if bound:
                    values[bound['suite']][bound['key']] = 50 if bound['scale']=='percent' else .5
    roots = {'dfm':'dfm','standard':'standard','euroeval':'euro'}
    for suite, metrics in values.items():
        put(tmp_path/roots[suite], 'merged_metrics.json', metrics)
    row, _ = registry.build_population_row(item(tmp_path), data)
    assert row['avg_population/multilingual_v1/score'] == .5
    assert row['avg_population/multilingual_v1/expected_metrics'] == 177
    assert row['avg_population/english_v2/score'] == .5
    assert row['avg_population/english_dfm_v1/score'] == .5


def test_unequal_task_denominators_equal_language_weight(tmp_path):
    data = manifest()
    pop = data['populations'][0]
    pop['required_tasks'] = {lang:['la','gec'] for lang in LANGUAGES}
    pop['required_tasks']['nb'] = ['la']
    del pop['metrics']['nb']['gec']
    path = complete(tmp_path, 0)
    values = json.loads(path.read_text())
    values['metrics']['dfm_eval/nb-la/accuracy'] = 1
    path.write_text(json.dumps(values))
    row, _ = registry.build_population_row(item(tmp_path), data)
    assert row['avg_population/multilingual_v1/score'] == pytest.approx(1/19)
    del values['metrics']['dfm_eval/nn-la/accuracy']
    path.write_text(json.dumps(values))
    row, _ = registry.build_population_row(item(tmp_path), data)
    assert 'avg_population/multilingual_v1/score' not in row
