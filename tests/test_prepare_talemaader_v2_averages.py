import json
from pathlib import Path

import pytest

from scripts import prepare_talemaader_v2_averages as m


REGISTRY = Path('config/multilingual_headline_populations_dfm13_20261006.json')
POINT = dict(id='step_2877261', train_step=2877261, epoch=10., inputs=['a.eval'], expected_n=808)


def test_definitions_preserve_english_math():
    d = m.definitions()
    for name in ('english', 'math_code', 'math2'):
        assert d['sections'][name] == m.legacy.SECTION_KEYS[name]
    assert m.NEW in d['dfm'] and m.OLD not in d['dfm']
    assert m.legacy.SEMANTIC_DALA_KEY in d['sections']['danish']


def test_no_legacy_keys_or_partial_multilingual_score():
    row, report = m.compute({m.NEW: .5, m.legacy.SEMANTIC_DALA_KEY: .75}, POINT, m.load_registry(REGISTRY))
    assert row[m.HP+'/danish'] == .625
    assert not any(k.startswith('headline_avg_v3/') for k in row)
    assert not any(k.startswith(m.HP+'/english') or k.startswith(m.HP+'/math_code') for k in row)
    assert row['avg_population/dfm13_multilingual_v1/expected_languages'] == 32
    assert row['avg_population/dfm13_all_languages_v1/expected_languages'] == 34
    assert 'avg_population/dfm13_multilingual_v1/score' not in row


@pytest.mark.parametrize('missing', [m.NEW, m.legacy.SEMANTIC_DALA_KEY])
def test_required_replacement_never_falls_back(missing):
    metrics = {m.OLD: 1., m.NEW: .5, m.legacy.SEMANTIC_DALA_KEY: .5, m.legacy.STRICT_DALA_KEY: 1.}
    metrics.pop(missing)
    row, _ = m.compute(metrics, POINT, m.load_registry(REGISTRY))
    assert m.HP+'/danish' not in row and m.HP+'/overall' not in row and m.SP+'/dfm' not in row


def test_population_equal_language_weight_complete():
    reg = m.load_registry(REGISTRY)
    metrics = {}
    for pop in reg['populations']:
        for bindings in pop['metrics'].values():
            for binding in bindings.values():
                if binding:
                    metrics[binding['key']] = 50. if binding['scale'] == 'percent' else .5
    row, _ = m.compute(metrics, POINT, reg)
    for pop in reg['populations']:
        if all(b is not None for bs in pop['metrics'].values() for b in bs.values()):
            assert row['avg_population/'+pop['id']+'/score'] == .5


def test_sparse_namespace_axes_and_epoch10_correction(tmp_path):
    p = tmp_path/'h.jsonl'
    p.write_text(json.dumps({'row': {'dfm_eval/epoch': 10., 'dfm_eval/train_step': 0, m.OLD: .2}}))
    assert m.load_history([p], [POINT])[POINT['id']][m.OLD] == .2


def test_conflicting_history_fails_closed(tmp_path):
    p = tmp_path/'h.jsonl'
    p.write_text('\n'.join(json.dumps({'dfm_eval/epoch': 10., m.OLD: v}) for v in (.2, .3)))
    with pytest.raises(ValueError, match='Conflicting'):
        m.load_history([p], [POINT])


def test_prepare_no_network_and_sample_guard(tmp_path):
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'run_path': m.RUN, 'points': [POINT]}))
    h = tmp_path/'history.jsonl'
    h.write_text(json.dumps({'dfm_eval/epoch': 10., m.legacy.SEMANTIC_DALA_KEY: .75}))
    side = tmp_path/(POINT['id']+'.json')
    doc = {'point': POINT, 'row': {'dfm_eval/epoch': 10., 'dfm_eval/train_step': 2877261,
            m.NEW: .5, m.NEW.rsplit('/',1)[0]+'/n': 808}}
    side.write_text(json.dumps(doc))
    r = m.prepare(manifest, tmp_path, [h], REGISTRY, tmp_path/'out.json')
    assert r['rows'][0][m.HP+'/danish'] == .625
    assert str(side.resolve()) in r['inputs']
    doc['row'][m.NEW.rsplit('/',1)[0]+'/n'] = 807
    side.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match='sample count'):
        m.prepare(manifest, tmp_path, [h], REGISTRY, tmp_path/'other.json')


def test_wrong_run_rejected(tmp_path):
    p = tmp_path/'m.json';p.write_text(json.dumps({'run_path': 'other'}))
    with pytest.raises(ValueError, match='current XL'):
        m.prepare(p, tmp_path, [], REGISTRY, tmp_path/'out.json')


def test_overall_preserves_legacy_section_weighting_excludes_multilingual():
    metrics = {key: .25 for keys in m.definitions()['sections'].values() for key in keys}
    for key in metrics:
        if key.startswith('euroeval/'):
            metrics[key] *= 100
    row, _ = m.compute(metrics, POINT, m.load_registry(REGISTRY))
    assert row[m.HP+'/overall'] == .25
    assert row[m.HP+'/overall/section_count'] == len(m.legacy.SECTION_KEYS)
    for pop in m.load_registry(REGISTRY)['populations']:
        for lang, bindings in pop['metrics'].items():
            if lang in ('da', 'en'):
                continue
            for b in bindings.values():
                if b:
                    metrics[b['key']] = 100 if b['scale'] == 'percent' else 1
    changed, _ = m.compute(metrics, POINT, m.load_registry(REGISTRY))
    assert changed[m.HP+'/overall'] == .25


def test_history_axis_mismatch_rejected(tmp_path):
    p = tmp_path/'history.jsonl'
    p.write_text(json.dumps({'dfm_eval/epoch':10, 'dfm_eval/train_step':123, m.OLD:.5}))
    with pytest.raises(ValueError, match='axes'):
        m.load_history([p], [POINT])


def test_sync_only_at_pause_and_never_while_training(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match='3200K'):
        m.sync_prepared(tmp_path/'absent', 3150000)
    monkeypatch.setattr(m.subprocess, 'check_output', lambda *a, **k: 'python pretrain.py data=dfm13')
    with pytest.raises(RuntimeError, match='Training process'):
        m.sync_prepared(tmp_path/'absent', 3200000)


@pytest.mark.parametrize('pause',[3154500,3200000])
def test_sync_single_writer_new_keys_and_idempotence(tmp_path, monkeypatch,pause):
    monkeypatch.setattr(m.subprocess, 'check_output', lambda *a, **k: '')
    path=tmp_path/'prepared.json'
    rows=[{m.HP+'/epoch':10., m.HP+'/train_step':2877261, m.HP+'/danish':.5}]
    payload=dict(run_path=m.RUN, rows=rows, rows_sha256=m.definition_hash(rows), inputs={},
                 points=[{'rejudge_available':True}])
    path.write_text(json.dumps(payload))
    class Fake:
        def __init__(self): self.logged=[];self.step=3200002;self.finished=0
        def Settings(self, **kw): return kw
        def init(self, **kw): assert kw['resume']=='must';return self
        def define_metric(self,*a,**kw): pass
        def log(self,row,**kw): assert kw=={'commit':True};self.logged.append(row)
        def finish(self): self.finished+=1
    f=Fake();r=m.sync_prepared(path,pause,f)
    assert f.logged==rows and f.finished==1
    assert m.sync_prepared(path,pause,f)==r and f.finished==1


def test_partial_sidecars_never_sync(tmp_path,monkeypatch):
    monkeypatch.setattr(m.subprocess,'check_output',lambda *a,**kw:'')
    p=tmp_path/'p.json';p.write_text(json.dumps(dict(run_path=m.RUN,rows=[],rows_sha256=m.definition_hash([]),
        inputs={},points=[{'rejudge_available':False}])))
    with pytest.raises(ValueError,match='incomplete'):
        m.sync_prepared(p,3200000)


def test_uniform_strict_successor_does_not_require_semantic_or_use_it():
    metrics={m.NEW:.75,m.legacy.STRICT_DALA_KEY:.25,m.legacy.SEMANTIC_DALA_KEY:1.}
    row,report=m.talemaader_only(metrics,POINT)
    assert row[m.THP+'/danish']==.5
    assert row[m.THP+'/danish/count']==2
    assert not row[m.THP+'/danish/complete']
    metrics.pop(m.legacy.SEMANTIC_DALA_KEY)
    assert m.talemaader_only(metrics,POINT)[0]==row
    assert m.legacy.STRICT_DALA_KEY in report['definition']['sections']['danish']
    assert m.legacy.SEMANTIC_DALA_KEY not in report['definition']['sections']['danish']


def test_talemaader_successor_missing_new_score_is_not_old_score_fallback():
    row,_=m.talemaader_only({m.OLD:1,m.legacy.STRICT_DALA_KEY:1},POINT)
    assert m.THP+'/danish' not in row and m.TSP+'/dfm' not in row


def test_fixed_current_recipe_overall_is_eight_sections_no_multilingual():
    metrics={key:.5 for keys in m.legacy.SECTION_KEYS.values() for key in keys}
    for key in metrics:
        if key.startswith('euroeval/'):metrics[key]=50
    metrics[m.NEW]=.5
    row,_=m.talemaader_only(metrics,POINT)
    assert row[m.THP+'/overall']==.5
    assert row[m.THP+'/overall/section_count']==8
    assert row[m.THP+'/overall/complete']==1
