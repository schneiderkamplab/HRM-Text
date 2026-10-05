import json
import pytest
from dfm12 import baltic_semantic_review as revised
from scripts import calibrate_baltic_semantic_review as calibration


def test_only_system_prompt_changes():
    row=calibration.controls()[0]['record']
    old=revised.baseline.request(row);new=revised.request(row)
    assert old['messages'][1:]==new['messages'][1:]
    assert old['response_format']==new['response_format']
    old['messages'][0]=new['messages'][0]
    assert old==new


def test_controls_balanced_and_hidden():
    cases=calibration.controls()
    assert len(cases)==12
    assert sum(c['expected']==['keep'] for c in cases)==6
    for c in cases:
        data=json.loads(revised.request(c['record'])['messages'][1]['content'])
        assert 'expected' not in data and 'prior_outcome' not in data


def test_no_nv_promotion_or_schema_weakening():
    assert revised.schema()==revised.baseline.schema()
    for verdict in ('needs_verification','repair','reject'):
        assert not revised.keeps(dict(verdict=verdict,issues=['incorrect'],reason='Missing essential fact.'),{},False)
    with pytest.raises(ValueError):
        revised.validate(dict(verdict='keep',issues=['incorrect'],reason='Contradiction.'))


def test_sample_reproducible_and_stratified():
    rows=[(str(i),lang,family,'path','{}') for lang in ('lt','lv')
          for family in ('summary-rewrite','multiturn') for i in range(10)]
    a=calibration.sample(rows)
    assert a==calibration.sample(list(reversed(rows)))
    assert len(a)==8
