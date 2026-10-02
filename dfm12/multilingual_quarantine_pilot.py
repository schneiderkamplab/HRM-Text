"""One-attempt 700-slot diagnostic generation; never admits or exports training data."""
import argparse
import asyncio
from collections import Counter
import copy
import json
import os
from pathlib import Path
import shutil
import time
import xml.etree.ElementTree as ET

import jsonschema

from .identity_gpu import training_renderer
from .io import atomic, digest, file_hash, load, lock, write_json
from .jobs import validate_audit
from .multilingual_diagnose import PromptBudget, RawResponseWriter, captured_query
from .multilingual_pilot import student_validate
from .multilingual_prepare_calibrated import QUOTAS, IMPLEMENTATIONS, unused_snapshot
from .multilingual_review_routed import request as review_request, keeps
from .multilingual_seeds import LANGUAGES
from .multilingual_tasks import AUDIT, MODEL, assemble, audit_schema, request, spec_for

DONOR = Path('data/dfm12/multilingual-pilot-20260926-v3')
CALIBRATION = Path('data/dfm12/multilingual-routed-v5-20260927')
POLICY = 'quarantined-diagnostic-only-v1'


def validate_endpoint_models(document):
    matches = [m for m in document.get('data', []) if m.get('id') == MODEL]
    if len(matches) != 1 or matches[0].get('max_model_len', 0) < 8192:
        raise ValueError('Borrowed endpoint must serve exact authorized MODEL with >=8192 context')
    return matches[0]


def compact_request(payload):
    """Preserve schema validation on CPU while avoiding flexible whitespace loops."""
    import xgrammar
    payload = copy.deepcopy(payload)
    original = payload.pop('response_format', None)
    if original is None:
        return payload, None
    schema = original['json_schema']['schema']
    grammar_schema = copy.deepcopy(schema)
    def visit(node):
        if isinstance(node, dict):
            if node.get('type') == 'string':
                node.pop('minLength', None)
                node.pop('maxLength', None)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
    visit(grammar_schema)
    payload['structured_outputs'] = {'grammar': str(xgrammar.Grammar.from_json_schema(
        grammar_schema, any_whitespace=False, indent=None, separators=(',', ':')))}
    return payload, schema


def prepare(root, tests):
    suites = list(ET.parse(tests).getroot().iter('testsuite'))
    if (not suites or sum(int(s.get('tests',0)) for s in suites)<1
            or any(int(s.get(k, 0)) for s in suites for k in ('failures','errors','skipped'))):
        raise ValueError('Passing CPU test receipt required')
    snapshot = unused_snapshot(DONOR)
    for name, expected in load(DONOR/'seeds-ready.json').items():
        if file_hash(DONOR/name) != expected:
            raise ValueError('Donor pin drift: ' + name)
    calibration = load(CALIBRATION/'report.json')
    root.mkdir(parents=True, exist_ok=False)
    for name in [*(f'seeds-{lang}.json' for lang in (*LANGUAGES,'openhermes')),
                 'previous-hashes.json','training-template.json']:
        shutil.copy2(DONOR/name,root/name)
    training_renderer(root)
    config = dict(contract_version=3,cohort=root.name,quotas=QUOTAS,languages=list(LANGUAGES),
        calibration_policy=POLICY, diagnostic_only=True, second_review=True,
        generator_model=MODEL,reviewer_model=MODEL,max_candidate_attempts=1,target_slots=700,
        admission_authorized=False,bulk_authorized=False,automatic_bulk_resume=False,
        diagnostic_followup=True,review_options={'variant':'routed4096'})
    write_json(root/'pilot-config.json',config)
    seeds = {lang:load(root/f'seeds-{lang}.json') for lang in (*LANGUAGES,'openhermes')}
    # Interleave languages/families so an interruption does not finish only one language.
    specs = [spec_for(lang,family,slot,0,seeds,config) for slot in range(max(QUOTAS.values()))
             for lang in LANGUAGES for family,count in QUOTAS.items() if slot<count]
    assert len(specs)==700
    budget = PromptBudget()
    preflight = {}
    for spec in specs:
        try:
            preflight[spec_id(spec)] = {'prompt_tokens': budget.measure(request(spec))}
        except ValueError as exc:
            preflight[spec_id(spec)] = {'error':str(exc)}
    write_json(root/'specifications.json',specs)
    write_json(root/'generation-preflight.json',preflight)
    write_json(root/'calibration-evidence.json',dict(path=str(CALIBRATION.resolve()),
        report_sha256=file_hash(CALIBRATION/'report.json'),passed=calibration['passed'],
        relationship='Existing frozen v5 result, not a fresh calibration run; all pilot outputs quarantined.'))
    write_json(root/'donor-evidence.json',dict(root=str(DONOR.resolve()),snapshot=snapshot))
    modules = set(IMPLEMENTATIONS) | {'multilingual_quarantine_pilot.py','multilingual_tool_calibration.py','io.py'}
    write_json(root/'manifest.json',dict(policy=POLICY,target_slots=700,max_generation_calls=700,
        max_total_calls=2100,transport_retries=0,max_concurrency=8,calibration_passed=calibration['passed'],
        admission_authorized=False,bulk_authorized=False,tests=str(tests.resolve()),tests_sha256=file_hash(tests),
        tests_passed=sum(int(s.get('tests',0)) for s in suites),
        implementation_pins={n:file_hash(Path(__file__).with_name(n)) for n in sorted(modules)},
        input_pins={p.name:file_hash(p) for p in root.iterdir() if p.is_file()}))


def spec_id(spec):
    return f"{spec['language_code']}-{spec['family']}-{spec['slot']}"


def audit_record(candidate):
    record = {k:candidate[k] for k in ('language','family','messages','tools')}
    record['language_name'] = LANGUAGES[candidate['language']]
    spec = candidate['provenance']
    record['requested_subtype'] = spec['subtype']
    if candidate['family']=='openhermes':
        record['source_messages'] = spec['source']['messages']
    for field in ('reference','scenario'):
        if field in spec:
            record[field] = spec[field]
    return record


async def process_slot(root, spec, renderer, query, seen):
    key = spec_id(spec)
    result = dict(id=key,language=spec['language_code'],family=spec['family'],spec=spec,
        status='generating',admission='quarantined',admission_authorized=False,
        would_keep_by_both_audits=False,errors={})
    path = root/'outcomes'/f'{key}.json'
    def save():
        write_json(path,result)
    save()
    preflight_path = root/'generation-preflight.json'
    if preflight_path.exists() and 'error' in load(preflight_path).get(key, {}):
        result['status'] = 'invalid_preflight'
        result['errors']['source_preflight'] = load(preflight_path)[key]['error']
        save()
        return result
    try:
        result['generator_output'] = await query(request(spec),'generate',key)
        save()
        result['candidate'] = assemble(spec,result['generator_output'])
        save()
        result['candidate'] = await asyncio.to_thread(student_validate,renderer,result['candidate'])
    except Exception as exc:
        result.update(status='invalid_generation')
        result['errors']['generate_or_validate'] = repr(exc)
        save()
        return result
    candidate = result['candidate']
    fingerprint = digest({'messages':candidate['messages'],'tools':candidate['tools']})
    result['duplicate'] = fingerprint in seen
    seen.add(fingerprint)
    record = audit_record(candidate)
    result['status'] = 'auditing'
    save()
    primary_valid = review_valid = False
    review_keep = False
    try:
        result['primary_audit'] = await query(dict(model=MODEL,temperature=0,max_tokens=512,
            chat_template_kwargs={'enable_thinking':False},response_format=audit_schema(),
            messages=[{'role':'system','content':AUDIT},
                      {'role':'user','content':json.dumps(record,ensure_ascii=False)}]),'primary_audit',key)
        validate_audit(result['primary_audit'])
        primary_valid = True
    except Exception as exc:
        result['errors']['primary_audit'] = repr(exc)
    save()
    # Diagnostic coverage includes the independent review even after primary rejection.
    try:
        result['review'] = await query(review_request(record),'review',key)
        review_keep = keeps(result['review'],record)
        review_valid = True
    except Exception as exc:
        result['errors']['review'] = repr(exc)
    result.update(primary_audit_valid=primary_valid,review_valid=review_valid,
        reviewer_keep=review_keep,would_keep_by_both_audits=bool(primary_valid and review_valid
        and result['primary_audit']['keep'] and review_keep and not result['duplicate']),
        status='quarantined_reviewed' if primary_valid and review_valid else 'quarantined_audit_invalid')
    save()
    return result


def summarize(root, complete=False, error=None):
    outcomes = [load(p) for p in sorted((root/'outcomes').glob('*.json'))]
    summary = dict(policy=POLICY,completed=complete,time=time.time(),error=error,
        target_slots=700,recorded_slots=len(outcomes),counts=dict(Counter(o['status'] for o in outcomes)),
        terminal_slots=sum(o['status'] not in ('generating','auditing') for o in outcomes),
        active_slots=sum(o['status'] in ('generating','auditing') for o in outcomes),
        by_language={lang:dict(Counter(o['status'] for o in outcomes if o['language']==lang)) for lang in LANGUAGES},
        assembled_candidates=sum('candidate' in o for o in outcomes),
        would_keep_by_both_audits=sum(o['would_keep_by_both_audits'] for o in outcomes),
        duplicate_candidates=sum(o.get('duplicate',False) for o in outcomes),
        diagnostic_rendered_tokens=sum(o.get('candidate',{}).get('rendered_training_tokens',0) for o in outcomes),
        admitted_rows=0,added_training_tokens=0,bulk_authorized=False,admission_authorized=False,
        successor_authorized=False,diagnostic_only=True,
        calibration_passed=load(root/'calibration-evidence.json')['passed']
            if (root/'calibration-evidence.json').exists() else False)
    write_json(root/'progress.json',summary)
    if complete or error:
        with atomic(root/'quarantine'/'candidates.jsonl') as handle:
            for outcome in outcomes:
                if 'candidate' in outcome:
                    handle.write(json.dumps(outcome,ensure_ascii=False)+'\n')
        write_json(root/'completion.json',summary)
    return summary


async def run(root,endpoints,concurrency):
    import aiohttp
    manifest = load(root/'manifest.json')
    if manifest['policy']!=POLICY or manifest['admission_authorized'] or not 1<=concurrency<=8:
        raise ValueError('Invalid quarantine policy')
    for name,expected in manifest['implementation_pins'].items():
        if file_hash(Path(__file__).with_name(name))!=expected:
            raise ValueError('Implementation drift: '+name)
    for name,expected in manifest['input_pins'].items():
        if file_hash(root/name)!=expected:
            raise ValueError('Input drift: '+name)
    if file_hash(manifest['tests'])!=manifest['tests_sha256']:
        raise ValueError('Test receipt drift')
    calibration=load(root/'calibration-evidence.json')
    if file_hash(Path(calibration['path'])/'report.json')!=calibration['report_sha256']:
        raise ValueError('Calibration evidence drift')
    renderer,budget,writer = training_renderer(root),PromptBudget(),RawResponseWriter(root/'raw')
    seen = set(load(root/'previous-hashes.json'))
    specs = iter(load(root/'specifications.json'))
    write_json(root/'status.json',dict(phase='generating_quarantined',pid=os.getpid(),endpoints=endpoints,
        concurrency=concurrency,admission_authorized=False))
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),
            connector=aiohttp.TCPConnector(limit=concurrency)) as session:
        endpoint_checks = {}
        for endpoint in endpoints:
            async with session.get(endpoint.rstrip('/')+'/models') as response:
                response.raise_for_status()
                endpoint_checks[endpoint] = validate_endpoint_models(await response.json())
        write_json(root/'endpoint-verification.json',endpoint_checks)
        async def worker(index):
            endpoint = endpoints[index%len(endpoints)]
            async def query(payload,stage,key):
                count = budget.measure(payload)
                transport,schema = compact_request(payload)
                output = await captured_query(session,endpoint,transport,writer,
                    dict(case_id=key,stage=stage,prompt_tokens=count,diagnostic_only=True))
                write_json(root/'decoded'/f'{key}-{stage}.json',output)
                if schema is not None:
                    jsonschema.validate(output,schema)
                return output
            for spec in specs:
                await process_slot(root,spec,renderer,query,seen)
                summarize(root)
        try:
            await asyncio.wait_for(asyncio.gather(*(worker(i) for i in range(concurrency))),timeout=6*3600)
        except BaseException as exc:
            summarize(root,error=repr(exc))
            write_json(root/'status.json',dict(phase='interrupted',pid=os.getpid(),error=repr(exc),admission_authorized=False))
            raise
    summarize(root,complete=True)
    write_json(root/'status.json',dict(phase='completed_quarantined',pid=os.getpid(),admission_authorized=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--tests',type=Path)
    parser.add_argument('--endpoints',nargs='+')
    parser.add_argument('--concurrency',type=int,default=8,choices=range(1,9))
    args=parser.parse_args()
    if args.action=='prepare':
        if args.tests is None:
            parser.error('prepare requires --tests')
        prepare(args.root,args.tests)
    else:
        if not args.endpoints or len(args.endpoints)>8:
            parser.error('run requires 1..8 borrowed endpoints')
        with lock(args.root/'.quarantine.lock'):
            if (args.root/'status.json').exists():
                raise ValueError('Immutable diagnostic already started')
            asyncio.run(run(args.root,args.endpoints,args.concurrency))
