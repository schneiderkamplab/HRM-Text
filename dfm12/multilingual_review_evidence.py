"""Development-only evidence-first reviewer variant; no default-policy changes."""
import json
import copy

from .multilingual_review import review_keeps, review_request

VARIANT = 'evidence4096'
VERSION = 'evidence-first-flat-v4'
FLAGS = ('language_correct', 'meaning_correct', 'constraints_met')
INSTRUCTION = '''
Return brief visible evidence, not a reasoning trace. First copy a short exact
literal_quote from a candidate ASSISTANT turn or its tool arguments, not from the
source or user request. Preserve misspellings, words, numbers and identifiers.
Then give a concise back_translation quoting that span and stating its literal
English meaning plus the relevant source/request comparison. For numbers/code,
state their literal value/operation and the supplied constraint. Never repair the
candidate. N/A, punctuation-only text, generic approval and missing evidence are
not valid explanations. Only after those evidence fields emit the three independent
boolean judgments. For EACH false dimension include exactly one issue starting
with that dimension's exact name and colon, quoting literal_quote and briefly
identifying the defect or contradiction. Never assign an issue to a true dimension.
All three true requires an empty issues array. Do not invent a flaw to fill issues.
Keep literal_quote at most 240 characters, back_translation 24..600 characters,
and each issue 32..360 characters. Return only the compact JSON object.
The response must be ONE FLAT OBJECT with exactly these six top-level keys in
this order: literal_quote, back_translation, language_correct, meaning_correct,
constraints_met, issues. No analysis/evidence wrappers, metadata or messages.
issues is an array of STRINGS, never an array of objects. Do not echo the schema.
Repeat literal_quote EXACTLY, including its punctuation, in back_translation AND
in every issue string. Prefer a short decisive span so exact repetition is easy;
do not omit a period or silently shorten the quote when repeating it. The rest
of back_translation briefly states its literal English meaning and comparison.
An explicit instruction to use only a named source/field is also a constraint:
following an untrusted note or a different field violates constraints_met as
well as meaning_correct when it changes the answer. Report these dimensions
independently; correct output formatting alone does not satisfy source limits.
Formatting examples with unrelated toy inputs (do not copy their quotes or
judgments into the actual review):
Request: Say OK. Candidate: OK
{"literal_quote":"OK","back_translation":"OK is the literal acknowledgment requested by the user.","language_correct":true,"meaning_correct":true,"constraints_met":true,"issues":[]}
Request: Return exactly RED. Candidate: BLUE
{"literal_quote":"BLUE","back_translation":"BLUE means blue; the actual request required exactly RED instead.","language_correct":true,"meaning_correct":false,"constraints_met":false,"issues":["meaning_correct: BLUE denotes the wrong color; the request specified RED.","constraints_met: BLUE violates the explicit requirement to return exactly RED."]}
Notice that the identical literal_quote appears in back_translation and in
EVERY issues string, not just in the first issue. Apply this format to the real
candidate's own text and assess its actual meaning independently.
'''


def request(record):
    import xgrammar
    payload = review_request(record)
    original = payload.pop('response_format')['json_schema']['schema']
    properties = {
        # This installed compiler drops escape support for length-bounded string
        # productions. Preserve valid JSON quoting and enforce lengths in keeps.
        'literal_quote': {'type': 'string'},
        'back_translation': {'type': 'string'},
        **{key: original['properties'][key] for key in FLAGS},
        'issues': {'type': 'array', 'maxItems': 3,
                   'items': {'type': 'string'}},
    }
    schema = {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}
    grammar = xgrammar.Grammar.from_json_schema(schema, any_whitespace=False, indent=None, separators=(',', ':'))
    payload.update(max_tokens=4096, structured_outputs={'grammar': str(grammar)})
    prompt_schema = copy.deepcopy(schema)
    prompt_schema['properties']['literal_quote'].update(minLength=1, maxLength=240)
    prompt_schema['properties']['back_translation'].update(minLength=24, maxLength=600)
    prompt_schema['properties']['issues']['items'].update(minLength=32, maxLength=360)
    payload['messages'][0]['content'] += INSTRUCTION + '\nOutput schema (' + VERSION + '):\n' + json.dumps(prompt_schema)
    return payload


def assistant_spans(record):
    spans = []
    for message in record['messages']:
        if message.get('role') != 'assistant':
            continue
        if isinstance(message.get('content'), str):
            spans.append(message['content'])
        calls = message.get('tool_calls', [])
        if calls:
            spans.extend((json.dumps(calls, ensure_ascii=False),
                          json.dumps(calls, ensure_ascii=False, separators=(',', ':'))))
            for call in calls:
                arguments = call.get('function', {}).get('arguments')
                if isinstance(arguments, str):
                    spans.append(arguments)
    return spans


def keeps(review, record):
    keep = review_keeps(review)
    if list(review) != ['literal_quote', 'back_translation', *FLAGS, 'issues']:
        raise ValueError('Review must use the exact evidence-first flat schema')
    quote, evidence = review.get('literal_quote'), review.get('back_translation')
    if (not isinstance(quote, str) or not 1 <= len(quote) <= 240
            or not any(c.isalnum() for c in quote)
            or not any(quote in span for span in assistant_spans(record))):
        raise ValueError('Literal quote is absent from candidate assistant content/arguments')
    if (not 24 <= len(evidence) <= 600 or sum(c.isalpha() for c in evidence) < 8
            or quote not in evidence or evidence.strip().lower() in ('n/a', 'none', 'not applicable')):
        raise ValueError('Missing meaningful literal evidence')
    issues = review['issues']
    false_flags = {key for key in FLAGS if not review[key]}
    if len(issues) != len(false_flags):
        raise ValueError('Issues must match every false dimension exactly once')
    seen = set()
    for issue in issues:
        key, separator, detail = issue.partition(':')
        if (not separator or key not in false_flags or key in seen or not 32 <= len(issue) <= 360
                or quote not in detail or sum(c.isalpha() for c in detail) < 8):
            raise ValueError('Issue lacks literal evidence or contradicts its dimension flag')
        seen.add(key)
    return keep
