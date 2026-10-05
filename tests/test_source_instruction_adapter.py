from copy import deepcopy

import pytest

from dfm12 import source_instruction_adapter as adapter


@pytest.mark.parametrize('model', [adapter.DEFAULT_MODEL, 'google/gemma-4-31B-it', 'verified-local-alias'])
def test_model_only_selection_does_not_change_contract(monkeypatch, model):
    envelope = {'request': {'model': 'historical-31B', 'messages': []}, 'schema': {'type': 'object'}}
    monkeypatch.setattr(adapter.core, 'request', lambda spec, historical: deepcopy(historical))
    output = adapter.request({}, envelope, model=model)
    assert output['request']['model'] == model
    assert output['schema'] == envelope['schema']
    assert envelope['request']['model'] == 'historical-31B'


def test_default_does_not_silently_inherit_31b(monkeypatch):
    monkeypatch.setattr(adapter.core, 'request', lambda spec, historical: deepcopy(historical))
    output = adapter.request({}, {'request': {'model': 'google/gemma-4-31B-it'}})
    assert output['request']['model'] == 'google/gemma-4-26B-A4B-it'


def test_empty_model_rejected():
    with pytest.raises(ValueError):
        adapter.model_name('')
