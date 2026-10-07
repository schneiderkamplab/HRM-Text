import copy
import json
from types import SimpleNamespace

import pytest

from scripts import log_expanded_dala_v2_averages as module


def full():
    recipe = module.definition()
    keys = set(recipe['dfm']).union(*(set(k) for k in recipe['sections'].values()))
    metrics = {k: 50 if k.startswith('euroeval/') else .5 for k in keys}
    return recipe, metrics


def test_exact_membership_and_old_policy_unchanged():
    old = copy.deepcopy(module.legacy.SECTION_KEYS)
    recipe, metrics = full()
    assert len(recipe['added']) == 68
    assert len(recipe['sections']['danish']) == 20
    assert len(recipe['sections']['english']) == 17
    assert len(recipe['dfm']) == len(module.legacy.SUITE_KEYS['dfm'])+68
    assert module.legacy.STRICT_DALA_KEY in recipe['sections']['danish']
    assert module.legacy.SEMANTIC_DALA_KEY not in recipe['sections']['danish']
    assert module.OLD_TALEMAADER not in recipe['dfm']
    assert module.TALEMAADER in recipe['dfm']
    row, report = module.compute(metrics, SimpleNamespace(epoch=10, step=300), recipe)
    assert report['complete']
    assert row[module.HEADLINE+'/overall'] == .5
    assert row[module.SUITE+'/dfm'] == .5
    assert module.legacy.SECTION_KEYS == old
    assert not any('talemaader_v2/' in k or k.startswith('avg_population') for k in row)


@pytest.mark.parametrize('bad', [None, float('nan'), float('inf'), True, -1, 1.01])
def test_invalid_new_input_excluded_with_coverage(bad):
    recipe, metrics = full()
    metrics[recipe['added'][-1]] = bad
    metrics[module.OLD_TALEMAADER] = 1
    row, report = module.compute(metrics, SimpleNamespace(epoch=10, step=300), recipe)
    assert not report['complete']
    assert row[module.SUITE+'/dfm'] == .5
    assert row[module.SUITE+'/dfm/count'] == 98
    assert row[module.SUITE+'/dfm/expected'] == 99
    assert row[module.SUITE+'/dfm/coverage'] == pytest.approx(98/99)
    assert row[module.SUITE+'/dfm/complete'] is False
    assert recipe['added'][-1] in report['missing_or_invalid']
    if type(bad) is float and not module.math.isfinite(bad):
        assert report['excluded_inputs'][recipe['added'][-1]] == 'nonfinite'


def test_missing_old_input_or_v2_has_no_fallback():
    for missing in (module.TALEMAADER, module.legacy.STRICT_DALA_KEY):
        recipe, metrics = full()
        metrics.pop(missing)
        metrics[module.OLD_TALEMAADER] = 1
        metrics[module.legacy.SEMANTIC_DALA_KEY] = 1
        row, report = module.compute(metrics, SimpleNamespace(epoch=10, step=300), recipe)
        assert row[module.HEADLINE+'/danish'] == .5
        assert row[module.HEADLINE+'/danish/count'] == 19
        assert missing in report['missing_or_invalid']


def test_empty_has_coverage_but_no_scores():
    row, report = module.compute({}, SimpleNamespace(epoch=10, step=300))
    for key in (module.HEADLINE+'/danish', module.HEADLINE+'/english',
                module.HEADLINE+'/overall', module.SUITE+'/dfm'):
        assert key not in row
        assert row[key+'/count'] == 0
        assert row[key+'/coverage'] == 0
        assert row[key+'/complete'] is False
    assert not report['complete']


def test_sparse_means_available_sections_without_zero_fill():
    metrics = {'eval/ARC/acc': .8, 'dfm_eval/dala_v2_da/semantic_v1/macro_f1': .4}
    row, _ = module.compute(metrics, SimpleNamespace(epoch=10, step=300))
    assert row[module.HEADLINE+'/english'] == .8
    assert row[module.HEADLINE+'/danish'] == .4
    assert row[module.HEADLINE+'/overall'] == pytest.approx(.6)
    assert row[module.HEADLINE+'/overall/section_count'] == 2
    assert row[module.SUITE+'/dfm'] == .4


def test_overall_equal_sections_not_all_languages_or_all_tasks():
    recipe, metrics = full()
    key = 'dfm_eval/dala_v2_da/semantic_v1/macro_f1'
    metrics[key] = 1
    row, _ = module.compute(metrics, SimpleNamespace(epoch=10, step=300), recipe)
    assert row[module.HEADLINE+'/overall'] == pytest.approx(.5 + .5/20/8)
    assert row[module.HEADLINE+'/english'] == .5
    assert row[module.SUITE+'/dfm'] == pytest.approx(.5+.5/len(recipe['dfm']))


def test_additional_roots_and_checkpoint_conflict(tmp_path):
    recipe, metrics = full()
    roots = {s: tmp_path/s for s in ('standard', 'dfm', 'euroeval')}
    extra = tmp_path/'new-dfm'
    sets = {**{s: {} for s in roots}, 'extra': {}}
    for k, v in metrics.items():
        dest = 'extra' if k in recipe['added'] else 'standard' if k.startswith('eval/') else 'euroeval' if k.startswith('euroeval/') else 'dfm'
        sets[dest][k] = v
    sets['dfm'][module.TALEMAADER.rsplit('/', 1)[0]+'/n'] = 808
    for label, values in sets.items():
        root = extra if label == 'extra' else roots[label]
        root.mkdir()
        (root/'merged_metrics.json').write_text(json.dumps(dict(metrics=values, epoch=10, step=300, num_samples=808)))
    item = module.PopulationItem(300, 10, [roots['standard']], [roots['dfm'], extra], [roots['euroeval']])
    collected, evidence = module.collect(item, recipe)
    assert module.compute(collected, item, recipe)[1]['complete']
    p = extra/'merged_metrics.json'
    d = json.loads(p.read_text()); d['step'] = 301; p.write_text(json.dumps(d))
    collected, evidence = module.collect(item, recipe)
    assert not module.compute(collected, item, recipe)[1]['complete']
    assert evidence[recipe['added'][0]]['status'] == 'checkpoint_mismatch'


def test_log_one_row_explicit_metrics():
    recipe, metrics = full()
    row, _ = module.compute(metrics, SimpleNamespace(epoch=10, step=300), recipe)
    calls = []
    fake = SimpleNamespace(init=lambda **kw: SimpleNamespace(finish=lambda: calls.append(('finish',))),
                           define_metric=lambda *a, **k: calls.append(('define', a, k)),
                           log=lambda *a, **k: calls.append(('log', a, k)))
    module.log_atomic(fake, row, SimpleNamespace(project='p', run_id='r', run_name='n', entity='e'))
    assert len([c for c in calls if c[0] == 'log']) == 1
    assert {c[1][0] for c in calls if c[0] == 'define'} == set(row)
    logged = next(c for c in calls if c[0] == 'log')
    assert logged[2] == {'commit': True}
    assert {k.split('/')[0] for k in logged[1][0]} == module.PREFIXES
    for c in calls:
        if c[0] == 'define' and not c[1][0].endswith('/epoch'):
            assert c[2]['step_metric'] == c[1][0].split('/')[0]+'/epoch'


@pytest.mark.parametrize('paired', [False, True])
def test_scheduler_exact_opt_in_dispatch(monkeypatch, tmp_path, paired):
    monkeypatch.syspath_prepend(str(module.ROOT/'eval_scheduler'))
    from eval_scheduler import runtime
    commands = []
    monkeypatch.setattr(runtime, 'python_bin', lambda j: 'python')
    monkeypatch.setattr(runtime, 'eval_step', lambda j: '300')
    monkeypatch.setattr(runtime, 'run_command', lambda argv, **k: commands.append(argv) or 0)
    job = SimpleNamespace(log_dir=str(tmp_path), metadata=dict(
        average_prefix=module.HEADLINE, log_root='standard', dfm_log_root='dfm',
        euroeval_log_root='euro', ckpt_tag='step_300', eval_epoch=10,
        log_wandb=False, additional_dfm_roots=['new13', 'old21'],
        multilingual_manifest='must-not-select-population-dispatch'))
    if paired:
        job.metadata['extra_average_prefixes'] = [module.SUITE]
    assert runtime.run_average(job) == 0
    assert commands[0][1] == 'scripts/log_expanded_dala_v2_averages.py'
    assert commands[0].count('--additional-dfm-root') == 2
    assert '--dry-run' in commands[0]
    assert ('--metric-prefix' not in commands[0]) is paired


def test_scheduler_rejects_unsupported_prefix_combination(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(module.ROOT/'eval_scheduler'))
    from eval_scheduler import runtime
    monkeypatch.setattr(runtime, 'python_bin', lambda j: 'python')
    monkeypatch.setattr(runtime, 'eval_step', lambda j: '300')
    job = SimpleNamespace(log_dir=str(tmp_path), metadata=dict(
        average_prefix=module.HEADLINE, extra_average_prefixes=['headline_avg_talemaader_v2'],
        log_root='standard', dfm_log_root='dfm', euroeval_log_root='euro',
        ckpt_tag='step_300', eval_epoch=10))
    with pytest.raises(ValueError, match='prefix combination'):
        runtime.run_average(job)
