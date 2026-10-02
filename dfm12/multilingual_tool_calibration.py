"""Frozen tool-repair calibration: exposed regressions plus fresh paired controls."""
import argparse
import asyncio
import copy
import json
import os
import re
from pathlib import Path
import time

from .io import file_hash, load, lock, write_json
from .multilingual_calibration import calibration_cases, score_reviews, TEXT
from .multilingual_diagnose import PromptBudget, RawResponseWriter, captured_query
from .multilingual_review_tools import request, keeps, deterministic_checks, VERSION, _location
from .multilingual_seeds import LANGUAGES


def fresh_cases():
    cases = copy.deepcopy(calibration_cases())
    for case in cases:
        if case['split'] != 'regression':
            case['split'] = 'exposed_regression'
    for language in LANGUAGES:
        for family in ('tool_identifier', 'tool_quantity', 'tool_argument_schema', 'tool_result_binding'):
            for negative in (False, True):
                quantity, event = 6, 'event-965'
                args = dict(event_id=event, quantity=quantity)
                if negative and family == 'tool_identifier':
                    args['event_id'] = 'event-956'
                if negative and family == 'tool_quantity':
                    args['quantity'] = 7
                if negative and family == 'tool_argument_schema':
                    args['quantity'] = '6'
                parameters = dict(type='object', properties=dict(event_id=dict(type='string'),
                    quantity=dict(type='integer', minimum=1)), required=['event_id', 'quantity'], additionalProperties=False)
                # A new two-call trajectory checks absolute indices, call IDs, and final JSON.
                messages = [dict(role='user', content=TEXT[language][4].replace('2 ', '6 ').replace('event-731', event))]
                for index, arguments in enumerate((dict(event_id=event, quantity=quantity), args)):
                    identifier = f'fresh_call_{index}'
                    content = json.dumps(dict(arguments, status='reserved'), ensure_ascii=False)
                    encoded = json.dumps(arguments) if index == 1 else arguments
                    messages.extend([dict(role='assistant', content='', tool_calls=[dict(id=identifier, type='function',
                        function=dict(name='allocate_seats', arguments=encoded))]),
                        dict(role='tool', tool_call_id=('foreign_call' if negative and family == 'tool_result_binding' and index == 1 else identifier),
                             name='allocate_seats', content=content)])
                    if index == 0:
                        messages.extend([dict(role='assistant', content=content),
                            dict(role='user', content=TEXT[language][4].replace('2 ', '6 ').replace('event-731', event))])
                messages.append(dict(role='assistant', content=content))
                dimensions = dict(language_correct=None, meaning_correct=True, constraints_met=True)
                if negative:
                    dimensions = dict(language_correct=None, meaning_correct=None, constraints_met=False)
                    if family in ('tool_identifier', 'tool_quantity'):
                        dimensions['meaning_correct'] = False
                cases.append(dict(name=f'fresh-tools-v4:{language}:{family}:{negative}', split='fresh_heldout',
                    group=family, polarity='negative' if negative else 'positive', expected_keep=not negative,
                    expected_dimensions=dimensions, native_gold=False,
                    label_basis='Fresh frozen two-call controls; reused native prompt template, not independent native-language gold.',
                    record=dict(language=language, language_name=LANGUAGES[language], family='tool-dialogue', messages=messages,
                        tools=[dict(type='function', function=dict(name='allocate_seats', description='Fictional seat allocation.', parameters=parameters))])))
    return cases


def routed_cases():
    cases = fresh_cases()
    for case in cases:
        case['split'] = 'exposed_regression'
    for language in LANGUAGES:
        base = next(c for c in cases if c['name']==f'fresh-tools-v4:{language}:tool_argument_schema:False')
        def transform(value):
            if isinstance(value, dict):
                return {k:transform(v) for k,v in value.items()}
            if isinstance(value, list):
                return [transform(v) for v in value]
            if type(value) is int and value==6:
                return 9
            if isinstance(value, str):
                return re.sub(r'\b6\b', '9', value.replace('event-965','event-624').replace('fresh_call','v5_call'))
            return value
        for negative in (False, True):
            case = copy.deepcopy(base)
            case.update(name=f'fresh-tools-v5:{language}:required_argument:{negative}',
                        split='fresh_variant', group='required_argument', expected_keep=not negative,
                        polarity='negative' if negative else 'positive')
            case['record'] = transform(case['record'])
            if negative:
                messages = case['record']['messages']
                call = messages[5]['tool_calls'][0]['function']
                args = json.loads(call['arguments'])
                del args['quantity']
                call['arguments'] = json.dumps(args)
                for index in (6,7):
                    content = json.loads(messages[index]['content'])
                    del content['quantity']
                    messages[index]['content'] = json.dumps(content)
                case['expected_dimensions'] = dict(language_correct=None, meaning_correct=None, constraints_met=False)
            cases.append(case)
    return cases


def prepare(root, variant='tools4096'):
    root.mkdir(parents=True, exist_ok=False)
    routed = variant == 'routed4096'
    from . import multilingual_review_routed
    review_request = multilingual_review_routed.request if routed else request
    cases, budget = routed_cases() if routed else fresh_cases(), PromptBudget()
    requests = [dict(name=c['name'], request=(payload := review_request(c['record'])),
                     prompt_tokens=budget.measure(payload)) for c in cases]
    write_json(root / 'controls.json', cases)
    write_json(root / 'requests.json', requests)
    modules = ('multilingual_tool_calibration.py', 'multilingual_review_tools.py', 'multilingual_review_structured.py',
               'multilingual_review.py', 'multilingual_calibration.py', 'multilingual_diagnose.py', 'multilingual_review_routed.py')
    write_json(root / 'manifest.json', dict(contract=multilingual_review_routed.VERSION if routed else VERSION,
        variant=variant, cases=len(cases), fresh_controls=14 if routed else 56,
        exposed_controls=228 if routed else 172, max_total_tokens=max(r['prompt_tokens'] for r in requests)+4096,
        implementation_pins={n: file_hash(Path(__file__).with_name(n)) for n in modules},
        input_pins={n: file_hash(root/n) for n in ('controls.json', 'requests.json')},
        retries=0, concurrency=2, model_evaluated=False, generation_authorized=False,
        holdout_caveat='Fresh two-call instances and failure locations; related tool task template is exposed. Not independent linguistic gold.'))


async def run(root, endpoint):
    import aiohttp
    manifest = load(root / 'manifest.json')
    from . import multilingual_review_routed
    routed = manifest.get('variant') == 'routed4096'
    review_keeps = multilingual_review_routed.keeps if routed else keeps
    deterministic = multilingual_review_routed.deterministic_checks if routed else deterministic_checks
    for name, expected in manifest['implementation_pins'].items():
        if file_hash(Path(__file__).with_name(name)) != expected:
            raise ValueError('Implementation drift: ' + name)
    for name, expected in manifest['input_pins'].items():
        if file_hash(root/name) != expected:
            raise ValueError('Input drift: ' + name)
    cases, requests = load(root/'controls.json'), load(root/'requests.json')
    reviews, errors = {}, {}
    writer, semaphore = RawResponseWriter(root/'raw'), asyncio.Semaphore(2)
    write_json(root/'status.json', dict(phase='calibrating', pid=os.getpid(), generation_authorized=False))
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600), connector=aiohttp.TCPConnector(limit=2)) as session:
        async def one(item):
            async with semaphore:
                try:
                    reviews[item['name']] = await captured_query(session, endpoint, item['request'], writer,
                        dict(name=item['name'], prompt_tokens=item['prompt_tokens']))
                except Exception as exc:
                    errors[item['name']] = repr(exc)
                write_json(root/'progress.json', dict(responses=len(reviews), errors=errors, total=len(cases)))
        await asyncio.gather(*(one(item) for item in requests))
    reviewer = score_reviews(cases, reviews, validator=lambda r,c: review_keeps(r,c,deterministic=False))
    effective = score_reviews(cases, reviews, validator=review_keeps)
    mismatches = [dict(name=c['name'], language=c['record']['language'],
        dimensions=[k for k,v in c['expected_dimensions'].items() if v is not None and reviews[c['name']].get(k) != v])
        for c in cases if isinstance(reviews.get(c['name']), dict)]
    mismatches = [m for m in mismatches if m['dimensions']]
    checks = {c['name']: deterministic(c['record']) for c in cases}
    spans = {}
    for case in cases:
        review = reviews.get(case['name'])
        if not isinstance(review, dict):
            continue
        if routed and not multilingual_review_routed.uses_tools(case['record']):
            spans[case['name']] = {'evidence_contract': 'v3 indexed text quote'}
            continue
        try:
            spans[case['name']] = dict(literal=_location(review, case['record'], 'literal_quote'),
                issues={key: _location(issue, case['record'], 'quote')
                        for key, issue in review['issues'].items() if issue is not None})
        except (ValueError, KeyError, TypeError, AttributeError):
            spans[case['name']] = {'invalid_evidence': True}
    passed = not errors and not mismatches and all(
        d['status']=='valid' and d['actual_keep']==d['expected_keep'] for s in (reviewer,effective) for d in s['details'])
    write_json(root/'report.json', dict(passed=passed, reviewer_only=reviewer, effective=effective,
        deterministic_checks=checks, evidence_offsets=spans, dimension_mismatches=mismatches, reviews=reviews, errors=errors,
        generation_authorized=False, pilot_gate_eligible=passed))
    write_json(root/'status.json', dict(phase='passed' if passed else 'blocked', pid=os.getpid(), time=time.time(),
                                      generation_authorized=False, pilot_gate_eligible=passed))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('action', choices=('prepare','run'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--endpoint', default='http://127.0.0.1:8600/v1')
    parser.add_argument('--variant', choices=('tools4096','routed4096'), default='tools4096')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.root, args.variant)
    else:
        with lock(args.root/'.calibration.lock'):
            if (args.root/'status.json').exists():
                raise ValueError('Immutable run already started')
            asyncio.run(run(args.root,args.endpoint))
