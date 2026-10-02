"""Frozen, opt-in structured evidence contract; never selects a larger model."""
import json

from .multilingual_review import review_request
from .multilingual_review_evidence import FLAGS, assistant_spans

VERSION = 'structured-issues-indexed-v3'
INSTRUCTION = '''
Return evidence, not a reasoning trace. Use exactly the supplied object schema.
message_index is the explicit absolute message_index printed in
indexed_candidate_assistant_entries, NOT an assistant-only ordinal. Copy it
exactly. User/source turns are context, never candidate evidence. Examine the
assistant text even when a user instruction looks like a better translation.
literal_quote must be an exact nonempty span from that assistant message's content
or tool arguments. back_translation states its literal meaning and compares with
the request/source, without silently correcting the candidate. For every false
dimension emit exactly one issue object with dimension, message_index, quote,
explanation. Each issue quote must occur in its indexed candidate message; it may
be different from literal_quote. Explain the defect and conflicting requirement.
Do NOT repeat quotes mechanically in explanations. True dimensions have no issues.
Judge dimensions independently. N/A, generic approval, and punctuation-only
explanations are invalid. All true requires issues []. Source-only restrictions
are constraints as well as meaning requirements. Do not invent defects.
Bounds: quotes 1..240 characters; back_translation at most 600 characters with
at least eight meaningful letters; issue explanations 24..360 characters.
For a numeric answer, give an English sentence explaining its literal number
and relation to the question, not just digits. For code, describe its literal
operation and compare with the requirement, not merely repeat the code.
These are explanations of visible content, not a reasoning trace.
'''


def schema(record=None):
    index_schema = {'type': 'integer', 'minimum': 0}
    if record is not None:
        indices = [i for i, m in enumerate(record['messages']) if m.get('role') == 'assistant']
        if not indices:
            raise ValueError('No candidate assistant messages')
        index_schema = {'type': 'integer', 'enum': indices}
    issue = {'type': 'object', 'properties': {
        'dimension': {'type': 'string', 'enum': list(FLAGS)},
        'message_index': index_schema,
        'quote': {'type': 'string'}, 'explanation': {'type': 'string'}},
        'required': ['dimension', 'message_index', 'quote', 'explanation'],
        'additionalProperties': False}
    properties = {'message_index': index_schema,
                  'literal_quote': {'type': 'string'}, 'back_translation': {'type': 'string'},
                  **{key: {'type': 'boolean'} for key in FLAGS},
                  'issues': {'type': 'array', 'maxItems': 3, 'items': issue}}
    return {'type': 'object', 'properties': properties, 'required': list(properties),
            'additionalProperties': False}


def request(record):
    import xgrammar
    payload = review_request(record)
    payload.pop('response_format')
    # Replace the old string-issue instruction, keeping the independent criteria.
    base = payload['messages'][0]['content'].split('In issues prefix each finding')[0]
    payload['messages'][0]['content'] = base + INSTRUCTION + '\n' + VERSION + '\n' + json.dumps(schema(record))
    payload['messages'][1]['content'] = json.dumps({
        'record': record,
        'indexed_candidate_assistant_entries': [dict(message_index=i, message=m)
            for i, m in enumerate(record['messages']) if m.get('role') == 'assistant']}, ensure_ascii=False)
    grammar = xgrammar.Grammar.from_json_schema(schema(record), any_whitespace=False,
                                               indent=None, separators=(',', ':'))
    payload.update(max_tokens=4096, structured_outputs={'grammar': str(grammar)})
    return payload


def _text(value, minimum, maximum):
    return (isinstance(value, str) and minimum <= len(value) <= maximum
            and sum(c.isalpha() for c in value) >= 8
            and value.strip().lower().rstrip('.!') not in (
                'n/a', 'none', 'not applicable', 'looks good', 'correct answer',
                'all correct', 'approved', 'no issues', 'good answer',
                'the answer is correct', 'everything is correct'))


def _quote(record, index, quote):
    messages = record['messages']
    if (type(index) is not int or not 0 <= index < len(messages)
            or messages[index].get('role') != 'assistant'
            or not isinstance(quote, str) or not 1 <= len(quote) <= 240
            or not any(c.isalnum() for c in quote)
            or not any(quote in span for span in assistant_spans({'messages': [messages[index]]}))):
        raise ValueError('Quote must occur in the indexed candidate assistant message')


def deterministic_checks(record):
    """Only directly applicable structural checks; never infer semantic labels."""
    checks = []
    source = record.get('source_messages')
    if source is not None:
        checks.append({'check': 'source_turn_roles', 'passed':
                       [m.get('role') for m in source] == [m.get('role') for m in record['messages']]})
    for index, message in enumerate(record['messages']):
        for call in message.get('tool_calls', []):
            arguments = call.get('function', {}).get('arguments')
            try:
                valid = isinstance(arguments, str) and isinstance(json.loads(arguments), dict)
            except (ValueError, TypeError):
                valid = False
            checks.append({'check': 'tool_arguments_json_object', 'message_index': index, 'passed': valid})
    return checks


def keeps(review, record):
    if (not isinstance(review, dict) or set(review) != set(schema()['required'])
            or any(type(review.get(key)) is not bool for key in FLAGS)
            or not isinstance(review.get('issues'), list)):
        raise ValueError('Invalid structured evidence schema')
    _quote(record, review['message_index'], review['literal_quote'])
    if not _text(review['back_translation'], 1, 600):
        raise ValueError('Missing meaningful literal translation')
    false = {key for key in FLAGS if not review[key]}
    seen = set()
    for issue in review['issues']:
        if not isinstance(issue, dict) or set(issue) != {'dimension', 'message_index', 'quote', 'explanation'}:
            raise ValueError('Invalid structured issue')
        dimension = issue['dimension']
        if not isinstance(dimension, str) or dimension not in false or dimension in seen:
            raise ValueError('Issue dimension contradicts flags or repeats')
        _quote(record, issue['message_index'], issue['quote'])
        if not _text(issue['explanation'], 24, 360):
            raise ValueError('Missing meaningful issue explanation')
        seen.add(dimension)
    if seen != false:
        raise ValueError('Every false dimension requires exactly one issue')
    return not false and all(check['passed'] for check in deterministic_checks(record))
