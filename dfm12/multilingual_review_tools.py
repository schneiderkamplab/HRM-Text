"""Tool-aware review with canonical evidence and per-dimension issue obligations."""
import copy
import itertools
import json

import jsonschema
from referencing import Registry
from referencing.exceptions import NoSuchResource, Unresolvable

from .multilingual_review import review_request
from .multilingual_review_evidence import FLAGS
from .multilingual_review_structured import _text

VERSION = 'tool-evidence-v4'


def _no_retrieval(uri):
    raise NoSuchResource(ref=uri)


INSTRUCTION = '''
Assess actual requirements, never invent a requirement for extra prose. A valid
tool call may have empty assistant content. A final JSON object is a legitimate
response when natural-language prose was not explicitly requested. JSON keys,
function names, identifiers and numeric values are not foreign-language errors.
Judge language in natural-language text that is actually present. Do not penalize
missing optional prose or rewrite a JSON response into an imagined requirement.
Both object-valued and JSON-string tool arguments are valid representations.
Still check the actual tool schema, requested quantities, exact identifiers,
call/result linkage and all explicit source/format restrictions independently.

Use canonical_candidate_evidence, which contains ONLY assistant evidence, never
source/user data. Copy an absolute message_index and JSON pointer from that list.
quote must be an exact contiguous span of that entry's text. JSON pointers refer
to the canonical candidate view; JSON-string arguments are decoded there only.
Do not invent quotes or repair wrong quantities, identifiers or types.
Give a brief literal back_translation and comparison, not a reasoning trace.
It needs at least eight letters; short meaningful number explanations are valid.

Return exactly: message_index, pointer, literal_quote,
back_translation, language_correct, meaning_correct, constraints_met, issues.
issues is an object with exactly language_correct, meaning_correct, constraints_met.
For a true flag its issue is null. For a false flag its issue MUST be an object
with message_index, pointer, quote, explanation. Give an independent
finding for EVERY false dimension. Never change a false flag to true merely to
avoid supplying evidence. Explanations describe the defect and relevant request;
no mechanical repetition of quotes is needed. Quotes 1..240 characters;
back_translation <=600 characters; explanations 24..360 characters. No placeholders.
Hyphen bullet lines such as '- A' and '- B' are valid bullet points unless the
request explicitly requires a different marker. Never invent a bullet glyph rule.
'''


def arguments(value):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError('Duplicate JSON argument key')
            result[key] = item
        return result
    def constant(_):
        raise ValueError('Nonfinite JSON argument')
    if isinstance(value, str):
        value = json.loads(value, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise ValueError('Tool arguments must be an object or JSON object string')
    json.dumps(value, allow_nan=False)  # Also reject nonfinite dictionary arguments.
    return value


def canonical_messages(record):
    messages = copy.deepcopy(record['messages'])
    for message in messages:
        for call in message.get('tool_calls', []):
            function = call.get('function', {})
            try:
                function['arguments'] = arguments(function.get('arguments'))
            except (ValueError, TypeError):
                pass  # Invalid arguments remain visible evidence, never repaired.
    return messages


def evidence(record):
    entries = []
    def add(index, pointer, value):
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        if text:
            entries.append(dict(message_index=index, pointer=pointer, text=text))
        if isinstance(value, dict):
            for key, child in value.items():
                add(index, pointer + '/' + key.replace('~', '~0').replace('/', '~1'), child)
        elif isinstance(value, list):
            for j, child in enumerate(value):
                add(index, pointer + '/' + str(j), child)
    for i, message in enumerate(canonical_messages(record)):
        if message.get('role') != 'assistant':
            continue
        if message.get('content'):
            add(i, f'/messages/{i}/content', message['content'])
        for j, call in enumerate(message.get('tool_calls', [])):
            add(i, f'/messages/{i}/tool_calls/{j}/function', call.get('function', {}))
    return entries


def schema(record):
    entries = evidence(record)
    if not entries:
        raise ValueError('No candidate evidence')
    location = {'message_index': {'type': 'integer', 'enum': sorted({e['message_index'] for e in entries})},
                'pointer': {'type': 'string', 'enum': [e['pointer'] for e in entries]}}
    def obj(properties):
        return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}
    issue = obj({**location, 'quote': {'type': 'string'}, 'explanation': {'type': 'string'}})
    # Eight disjoint flag combinations enforce missing-issue obligations in decoding.
    variants = []
    for values in itertools.product((True, False), repeat=3):
        variants.append(obj({**location, 'literal_quote': {'type': 'string'},
            'back_translation': {'type': 'string'},
            **{k: {'const': v} for k, v in zip(FLAGS, values)},
            'issues': obj({k: {'type': 'null'} if v else {'$ref': '#/$defs/issue'}
                           for k, v in zip(FLAGS, values)})}))
    return {'$defs': {'issue': issue}, 'anyOf': variants}


def request(record):
    import xgrammar
    payload = review_request(record)
    payload.pop('response_format')
    base = payload['messages'][0]['content'].split('In issues prefix each finding')[0]
    payload['messages'][0]['content'] = base + INSTRUCTION + '\nContract: ' + VERSION
    payload['messages'][1]['content'] = json.dumps(dict(record=record,
        canonical_candidate_evidence=evidence(record)), ensure_ascii=False)
    grammar = xgrammar.Grammar.from_json_schema(schema(record), any_whitespace=False,
                                               indent=None, separators=(',', ':'))
    payload.update(max_tokens=4096, structured_outputs={'grammar': str(grammar)})
    return payload


def deterministic_checks(record):
    checks = []
    source = record.get('source_messages')
    if source is not None:
        checks.append(dict(check='source_turn_roles', passed=[m.get('role') for m in source]
                           == [m.get('role') for m in record['messages']]))
    tools = {t['function']['name']: t['function']['parameters'] for t in record.get('tools', [])}
    calls = {}
    for i, message in enumerate(record['messages']):
        for call in message.get('tool_calls', []):
            name = call.get('function', {}).get('name')
            try:
                args = arguments(call.get('function', {}).get('arguments'))
                parameters = tools[name]
                def local_refs(value):
                    if isinstance(value, dict):
                        for key, child in value.items():
                            if key in ('$ref', '$dynamicRef') and (not isinstance(child, str) or not child.startswith('#')):
                                raise ValueError('External schema references are not permitted')
                            local_refs(child)
                    elif isinstance(value, list):
                        for child in value:
                            local_refs(child)
                local_refs(parameters)
                jsonschema.Draft202012Validator.check_schema(parameters)
                jsonschema.Draft202012Validator(parameters, registry=Registry(retrieve=_no_retrieval)).validate(args)
                valid, error = True, None
            except (ValueError, TypeError, KeyError, jsonschema.ValidationError, jsonschema.SchemaError, Unresolvable) as exc:
                valid, error = False, type(exc).__name__
            checks.append(dict(check='tool_argument_schema', message_index=i, passed=valid, error=error))
            identifier = call.get('id')
            checks.append(dict(check='unique_call_id', message_index=i,
                               passed=isinstance(identifier, str) and bool(identifier) and identifier not in calls))
            calls[identifier] = name
        if message.get('role') == 'tool':
            identifier = message.get('tool_call_id')
            checks.append(dict(check='tool_result_link', message_index=i, passed=identifier in calls
                and (not message.get('name') or message['name'] == calls[identifier])))
    return checks


def _location(value, record, quote_key):
    quote = value[quote_key]
    entries = [e for e in evidence(record) if e['pointer'] == value['pointer']
               and e['message_index'] == value['message_index']]
    if (type(value['message_index']) is not int
            or len(entries) != 1 or not isinstance(quote, str) or not 1 <= len(quote) <= 240
            or quote not in entries[0]['text']):
        raise ValueError('Canonical indexed evidence pointer/span does not match')
    text = entries[0]['text']
    return [dict(start=i, end=i+len(quote)) for i in range(len(text)) if text.startswith(quote, i)]


def keeps(review, record, deterministic=True):
    required = {'message_index', 'pointer', 'literal_quote', 'back_translation', *FLAGS, 'issues'}
    if (not isinstance(review, dict) or set(review) != required
            or any(type(review.get(k)) is not bool for k in FLAGS)
            or not isinstance(review['issues'], dict) or set(review['issues']) != set(FLAGS)):
        raise ValueError('Invalid tool-aware review schema')
    _location(review, record, 'literal_quote')
    if not _text(review['back_translation'], 1, 600):
        raise ValueError('Missing meaningful literal evidence')
    for key in FLAGS:
        issue = review['issues'][key]
        if review[key]:
            if issue is not None:
                raise ValueError('True dimension has an issue')
        else:
            if not isinstance(issue, dict) or set(issue) != {'message_index', 'pointer', 'quote', 'explanation'}:
                raise ValueError('False dimension requires its own structured issue')
            _location(issue, record, 'quote')
            if not _text(issue['explanation'], 24, 360):
                raise ValueError('Invalid issue explanation')
    return all(review[k] for k in FLAGS) and (not deterministic or all(c['passed'] for c in deterministic_checks(record)))
