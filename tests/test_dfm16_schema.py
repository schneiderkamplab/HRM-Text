import jsonschema
import pytest
from scripts.dfm16_schema import checked_schema


def test_legacy_bounds_preserve_semantics():
    s = checked_schema({'type': 'number', 'minimum': 0, 'exclusiveMinimum': True})
    jsonschema.validate(1, s)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(0, s)


def test_required_const_and_data_untouched():
    s = checked_schema({'type': 'object', 'properties': {'x': {'const': 2, 'required': True}},
                        'examples': [{'required': True, 'exclusiveMinimum': True}]})
    assert s['examples'][0]['exclusiveMinimum'] is True
    for value in ({}, {'x': 3}):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(value, s)
    jsonschema.validate({'x': 2}, s)


def test_declared_draft_four():
    s = checked_schema({'$schema': 'http://json-schema.org/draft-04/schema#',
                        'minimum': 0, 'exclusiveMinimum': True})
    assert s['exclusiveMinimum'] is True


def test_malformed_bound_held():
    with pytest.raises(ValueError):
        checked_schema({'exclusiveMinimum': True})
