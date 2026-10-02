import copy
import json
from types import SimpleNamespace

import pytest

from scripts.prepare_cross_language_average import registry
from scripts.headline_population_registry import build_population_row, validate_registry


def test_equal_languages_czech_four_and_explicit_scales(tmp_path):
    definition=registry()
    population=definition['populations'][0]
    roots={s:tmp_path/s for s in ('standard','dfm','euroeval')}
    metrics={s:{} for s in roots}
    for lang,bindings in population['metrics'].items():
        assert len(bindings)==(4 if lang=='cs' else 5)
        for binding in bindings.values():
            value=0.4 if lang=='cs' else 0.8
            metrics[binding['suite']][binding['key']]=value*(100 if binding['scale']=='percent' else 1)
    for suite,root in roots.items():
        root.mkdir()
        (root/'merged_metrics.json').write_text(json.dumps(metrics[suite]))
    item=SimpleNamespace(step=2900000,epoch=10.05,**{s+'_root':[p] for s,p in roots.items()})
    row,_=build_population_row(item,definition)
    base='avg_population/cross_language_v1'
    assert row[base+'/expected_metrics']==104
    assert row[base+'/languages/cs/score']==pytest.approx(0.4)
    assert row[base+'/score']==pytest.approx((20*0.8+0.4)/21)
    missing=population['metrics']['da']['scala']['key']
    del metrics['euroeval'][missing]
    (roots['euroeval']/'merged_metrics.json').write_text(json.dumps(metrics['euroeval']))
    row,_=build_population_row(item,definition)
    assert base+'/score' not in row
    assert base+'/languages/da/score' not in row
    assert base+'/languages/cs/score' in row


def test_czech_omission_is_only_allowed_omission():
    definition=copy.deepcopy(registry())
    p=definition['populations'][0]
    del p['metrics']['da']['multiwikiqa']
    p['required_tasks']['da'].remove('multiwikiqa')
    with pytest.raises(ValueError,match='four for Czech'):
        validate_registry(definition)
