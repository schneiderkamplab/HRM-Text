"""DFM14-only bounded generation and whole-conversation review contract."""
import copy
import json

from dfm12.wave_synthetic_runtime import decoder_schema, generation_request
from dfm14.synthetic_quality import output_schema, constraints
from dfm14 import synthetic_review

VERSION = 'dfm14-whole-conversation-quality-v7-schema-no-thinking'


def json_transport(payload, schema):
    """Constrain decoding to the schema and independently validate on CPU."""
    payload.pop('structured_outputs', None)
    payload['response_format'] = {'type': 'json_schema', 'json_schema': {
        'name': 'dfm14_response', 'strict': True, 'schema': copy.deepcopy(schema)}}
    payload['chat_template_kwargs'] = {'enable_thinking': False}
    def shape(node):
        if node['type'] == 'object':
            return {k: shape(v) for k,v in node['properties'].items()}
        if node['type'] == 'array':
            return [shape(node['items']) for _ in range(node['minItems'])]
        return '|'.join(node['enum']) if 'enum' in node else 'REPLACE_WITH_ACTUAL_TEXT'
    payload['messages'][0]['content'] += (
        '\nOutput exactly ONE JSON object with this field layout. Replace text placeholders '
        'with actual content, choose exactly one permitted status, and output no schema or extra fields:\n'
        + json.dumps(shape(schema), ensure_ascii=False))
    return payload


def compact_grammar(payload, schema):
    payload.pop('response_format', None)
    # Explicit escape-aware bounded strings avoid JSON-schema lowering bugs and
    # prevent unbounded whitespace inside strings as well as between fields.
    rules = [r'json-char ::= [^\x00-\x1f"\\] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F]{4})']
    def literal(value):
        return json.dumps(json.dumps(value, ensure_ascii=False))
    def visit(node, name):
        if 'enum' in node:
            expr = ' | '.join(literal(x) for x in node['enum'])
        elif node['type'] == 'string':
            expr = '\"\\\"\" json-char{' + str(node.get('minLength', 1)) + ',' + str(node['maxLength']) + '} \"\\\"\"'
        elif node['type'] == 'object':
            fields = []
            for i, (key, value) in enumerate(node['properties'].items()):
                child = f'{name}-f{i}'
                visit(value, child)
                fields.append(json.dumps(json.dumps(key) + ':') + ' ' + child)
            expr = '\"{\" ' + ' \",\" '.join(fields) + ' \"}\"'
        elif node['type'] == 'array' and node['minItems'] == node['maxItems']:
            child = name + '-item'
            visit(node['items'], child)
            expr = '\"[\" ' + ' \",\" '.join([child] * node['minItems']) + ' \"]\"'
        else:
            raise ValueError('Unsupported bounded grammar node')
        rules.append(name + ' ::= ' + expr)
    visit(schema, 'root')
    payload['structured_outputs'] = {'grammar': '\n'.join(rules)}
    return payload


def generation_payload(spec, generation, model):
    payload = generation_request(spec, generation,
        endpoint_models={'data': [dict(id=model, max_model_len=32768)]})
    schema = output_schema(spec, payload['response_format']['json_schema']['schema'])
    payload.pop('structured_outputs', None)
    payload['response_format']['json_schema']['schema'] = decoder_schema(schema)
    payload.update(temperature=.3, repetition_penalty=1.1, max_tokens=4096)
    # The schema is supplied to constrained decoding, not as text to reproduce.
    system = payload['messages'][0]['content'].split('\nReturn exactly this JSON structure')[0]
    if constraints(spec):
        system = system.replace('Return {"user":"the request (without copying passage)","assistant":"correct response"}.',
                                'Return user and answer_parts only, as specified below.')
    system += ('\nProduce an INSTANCE of the response schema, never the schema itself. '
               'All required text fields must be nonempty natural text. Use concise native-language '
               'sentences; no English scaffolding except code and structural identifiers. '
               'For numerical math include the literal LaTeX format marker \\boxed{...} in the user request, '
               'correctly JSON-escaped; never translate boxed notation into square brackets. '
               'The explanation must not contain any boxed answer: the CPU appends the final answer. '
               'Use the supplied source as the subject, never the generic topic label. '
               'Keep each user request under 700 characters, each answer under 1600 characters '
               'where possible, while preserving the complete meaning and every source turn. '
               'For tool results, fill the final field with a concise statement of the actual '
               'terminal result, including failure when applicable; do not leave it empty.')
    payload['messages'][0]['content'] = system
    payload['messages'][0]['content'] += (
        '\nOnly student-facing answers belong in assistant/final/explanation fields. '
        'Never append an explanation of how you followed these generation instructions. '
        'Never refer to a CPU, checker, reference test, contract, task subtype or the user in third person. '
        'The math/code explanation is a short DIRECT explanation to the learner, NOT code, '
        'test outputs, execution instructions or a repeated solution; the verified code is appended separately. '
        'Do not invent extra output constraints or copy source text into generated prompts. '
        'Deliver requested drafts/rewrites in the current reply; never promise later work. '
        'Do not invent service rules or user interfaces. Use explicit hypothetical framing where appropriate. '
        'For tool clarification, do not put lookup results in user replies. '
        'For multi-action tools, user must explicitly request the actual action, not just availability/status.')
    if 'authorization_quote' in schema['properties']:
        payload['messages'][0]['content'] += (
            '\nReturn authorization_quote as an exact substring of the user request containing the action intent; '
            'this metadata will NOT be part of the learner conversation.')
    if constraints(spec):
        payload['messages'][0]['content'] += (
            '\nFor this constrained summary return user and answer_parts, NOT assistant. '
            'Each part is exactly one requested sentence or bullet, without numbering, bullet markers, '
            'newlines, headings or commentary. The CPU adds separators. Constraints: '
            + json.dumps(constraints(spec)))
    return json_transport(payload, schema), schema


def review_payload(record, model):
    payload = synthetic_review.request(record, model)
    schema = synthetic_review.schema(record)
    return json_transport(payload, schema)
