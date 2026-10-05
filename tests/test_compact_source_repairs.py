from copy import deepcopy
import pytest
from jsonschema import ValidationError
from scripts import run_compact_source_repairs as repair


def test_assistant_only_repair_retains_source_and_user(monkeypatch):
    record=dict(language='lv',messages=[dict(role='user',content='Exact question'),dict(role='assistant',content='Wrong')],source=dict(text='Evidence'))
    original=deepcopy(record)
    _,schema=repair.repair_request(record,'Correct the fact')
    def validate(renderer,row): row['rendered_training_tokens']=25
    monkeypatch.setattr(repair,'student_validate',validate)
    new,tokens=repair.apply(record,{'1':'Correct'},schema,None)
    assert record==original and new['source']==record['source']
    assert new['messages'][0]==record['messages'][0] and tokens==25
    with pytest.raises(ValidationError): repair.apply(record,{'0':'Changed question','1':'Correct'},schema,None)


def test_noop_and_template_repairs_fail():
    record=dict(messages=[dict(role='assistant',content='Original')])
    _,schema=repair.repair_request(record,'Fix')
    with pytest.raises(ValueError,match='Unchanged'): repair.apply(record,{'0':'Original'},schema,None)
    with pytest.raises(ValueError,match='template'): repair.apply(record,{'0':'<start_of_turn>bad'},schema,None)
