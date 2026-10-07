"""DFM14-only fail-closed checks around the unchanged native v4 assembler.

These checks complement semantic review; they do not certify language or intent.
No answer text is silently stripped or repaired.
"""
import copy
import re

from dfm12.multilingual_calibration_v6 import generation_assemble


class QualityFailure(ValueError):
    pass


def source_issues(spec):
    text = spec.get('source', {}).get('text')
    if not text:
        return []
    issues = []
    if '\ufffd' in text or re.search(r'[A-Za-z]\s*[¢¿∆]\s*[A-Za-z]', text):
        issues.append('damaged_source_encoding')
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    # A conservative prose-seed gate, not a universal corpus quality classifier.
    prose = [line for line in lines if len(line) >= 80 and re.search(r'[.!?。！？]', line)]
    if not prose:
        issues.append('no_substantive_prose_seed')
    if re.search(r'<(?:div|table|ref|script)\b|\{\{|\}\}', text, re.I):
        issues.append('unresolved_source_markup')
    return issues


def constraints(spec):
    if spec['family'] != 'summary-rewrite':
        return {}
    return {
        'one-sentence summary': {'sentences': 1},
        'two-sentence summary': {'sentences': 2},
        'summary with exactly three bullets': {'bullets': 3},
    }.get(spec['subtype'], {})


def output_schema(spec, base):
    schema = copy.deepcopy(base)
    bound = constraints(spec)
    if bound:
        count = next(iter(bound.values()))
        schema['properties'].pop('assistant')
        schema['properties']['answer_parts'] = dict(type='array', minItems=count, maxItems=count,
            items=dict(type='string', minLength=1, maxLength=1800))
        schema['required'] = ['user', 'answer_parts']
    if spec['family'] == 'tool-dialogue' and spec['subtype'] == 'multi':
        schema['properties']['authorization_quote'] = dict(type='string', minLength=4, maxLength=700)
        schema['required'].append('authorization_quote')
    return schema


def sentences(text):
    # Conservative diagnostic: decimals/initials are not boundaries. Ambiguous
    # abbreviations may be held for review rather than silently accepted.
    clean = re.sub(r'(?<=\d)\.(?=\d)|(?<=\b[A-Z])\.(?=\s+[A-Z])', '', text)
    return [part.strip() for part in re.split(r'[.!?。！？।؟]+(?:["\u201d\u2019]*)', clean) if part.strip()]


def answer_issues(text):
    issues = []
    if re.search(r'(?im)^\s*(?:[\'*# ]*)(?:explanation|final_answer|final result|result: success)\s*:', text):
        issues.append('assistant_metadata_leak')
    if "'explanation':" in text or '"explanation":' in text:
        issues.append('assistant_schema_leak')
    return issues


def assemble(spec, output, generation):
    result = copy.deepcopy(output)
    bound = constraints(spec)
    if bound:
        parts = result.pop('answer_parts')
        if len(parts) != next(iter(bound.values())):
            raise QualityFailure('wrong_answer_parts_count')
        if any('\n' in part.strip() or re.match(r'^\s*(?:[-*\u2022]|\d+[.)])\s', part) for part in parts):
            raise QualityFailure('answer_parts_must_be_plain_single_lines')
        if 'sentences' in bound and any(len(sentences(part)) != 1 for part in parts):
            raise QualityFailure('answer_part_not_one_sentence')
        result['assistant'] = (' '.join(parts) if 'sentences' in bound else
                               '\n'.join('- ' + part for part in parts))
    quote = result.pop('authorization_quote', None)
    if spec['family'] == 'tool-dialogue' and spec['subtype'] == 'multi':
        if not isinstance(quote, str) or len(quote.strip()) < 4 or quote not in result['user']:
            raise QualityFailure('missing_verbatim_user_authorization_quote')
        if re.search(r'[{}\[\]`]', quote):
            raise QualityFailure('authorization_must_be_prose_not_argument_json')
    if spec['family'] == 'math-code':
        explanation = result['explanation']
        if spec['subtype'] == 'math' and '\\boxed{' not in result['user']:
            raise QualityFailure('math_prompt_missing_literal_boxed_contract')
        if '```' in explanation or re.search(r'\bdef\s+solve\s*\(|\\boxed\s*\{|final_answer|\bCPU\b', explanation):
            raise QualityFailure('math_explanation_contains_reference_or_scaffolding')
    candidate = generation_assemble(spec, result, generation)
    for message in candidate['messages']:
        if message['role'] == 'assistant':
            issues = answer_issues(message.get('content', ''))
            if issues:
                raise QualityFailure(','.join(issues))
    # Metadata stays outside the student conversation and outside the review.
    candidate['quality_contract'] = dict(version='dfm14-quality-v1', constraints=bound,
        authorization_quote=quote, semantic_intent_review_required=quote is not None)
    return candidate
