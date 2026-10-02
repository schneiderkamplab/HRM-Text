"""Independent bounded false-accept probes for the opt-in tool reviewer."""
import copy
from unittest.mock import patch

import pytest

from dfm12 import multilingual_review_tools as target


def record(arguments):
    return {'messages': [
        {'role': 'user', 'content': 'USER_ONLY: request two items.'},
        {'role': 'assistant', 'content': '', 'tool_calls': [
            {'id': 'call_1', 'type': 'function', 'function': {
                'name': 'reserve', 'arguments': arguments}}]}],
        'tools': [{'type': 'function', 'function': {'name': 'reserve',
            'parameters': {'type': 'object', 'properties': {
                'count': {'type': 'integer', 'minimum': 1}},
                'required': ['count'], 'additionalProperties': False}}}]}


def approval(candidate):
    span = target.evidence(candidate)[0]
    return dict(message_index=span['message_index'], pointer=span['pointer'],
                literal_quote=span['text'],
                back_translation='The argument supplies the requested item count.',
                language_correct=True, meaning_correct=True, constraints_met=True,
                issues=dict(language_correct=None, meaning_correct=None,
                            constraints_met=None))


def rejected(candidate, review=None):
    try:
        return target.keeps(review or approval(candidate), candidate) is False
    except ValueError:
        return True


@pytest.mark.parametrize('arguments', [{'count': 2}, '{"count":2}'])
def test_positive_representations_without_mutation(arguments):
    candidate = record(arguments)
    original = copy.deepcopy(candidate)
    assert target.keeps(approval(candidate), candidate) is True
    assert candidate == original


@pytest.mark.parametrize('arguments', [
    '{invalid', '[2]', '"two"', [], 'null', '{"count":1,"count":2}',
    {'count': '2'}, {'count': True}, {}, {'count': 2, 'extra': 3},
])
def test_malformed_or_schema_invalid_arguments(arguments):
    assert rejected(record(arguments))


@pytest.mark.parametrize('arguments', ['{"count":NaN}', {'count': float('nan')}])
def test_nonfinite_is_not_a_json_number(arguments):
    candidate = record(arguments)
    candidate['tools'][0]['function']['parameters']['properties']['count'] = {'type': 'number'}
    assert rejected(candidate)


@pytest.mark.parametrize('change', [
    {'pointer': '/messages/0/content', 'message_index': 0,
     'literal_quote': 'USER_ONLY'},
    {'pointer': '/messages/1/tool_calls/99/function'},
    {'literal_quote': 'invented'},
    {'message_index': True},
    {'back_translation': 'N/A'}, {'meaning_correct': 1},
])
def test_bad_evidence_and_boolean_integer_confusion(change):
    candidate = record({'count': 2})
    review = dict(approval(candidate), **change)
    assert rejected(candidate, review)


def test_false_dimension_requires_its_issue():
    candidate = record({'count': 2})
    review = dict(approval(candidate), meaning_correct=False)
    assert rejected(candidate, review)


def test_external_reference_never_fetches():
    candidate = record({'count': 2})
    candidate['tools'][0]['function']['parameters'] = {
        '$ref': 'https://example.invalid/untrusted-schema.json'}
    with patch('urllib.request.urlopen', side_effect=RuntimeError('network prohibited')) as network:
        try:
            result = rejected(candidate)
        finally:
            assert network.call_count == 0
        assert result
