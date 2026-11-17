"""English production batches; isolated from immutable development experiments."""
import argparse
import asyncio
import os
from pathlib import Path

import httpx
from audit_pipeline.runtime import run
from dfm12.io import file_hash, load, lock, rows, write_json
from scripts.dfm16_story_calibration import immutable, immutable_rows
from scripts.dfm16_staged_stories import StagedGenerate, initial_request, POLICY
from scripts.dfm16_staged_validation_campaign import BASE, ROOT as VALIDATION
from scripts.dfm16_experiment_transport import Budget, ExperimentClient
from scripts.dfm16_staged_experiment import MODELS
from scripts.queue_dfm16_stories_qwen import prepare_stage, audited_records
from scripts.dfm16_specialist_audit_v13 import SCOPES, Specialist, evidence, verification_jobs
from scripts.dfm16_validation_audit import whole_vote

ROOT = Path('data/dfm16/english-production-v1-20261030')


def prepare(root):
    records = []
    pins = {}
    for path in sorted((VALIDATION/'en/validation/source-review').glob('*.json')):
        assessment = load(path)
        if 'generation_input' not in assessment:
            continue
        source = assessment['generation_input']
        identifier = 'production-v1/' + source['id']
        record = dict(source, id=identifier, audit_id=identifier, cohort='production',
                      source_review_origin=str(path))
        initial_request(record)
        records.append(record)
        pins[str(path)] = file_hash(path)
    if not records or len({r['family'] for r in records}) != len(records):
        raise ValueError('missing or duplicate reviewed source families')
    immutable(root/'authorization.json', dict(language='en', user_instruction='go ahead with production.',
        production_authorized=True, statistically_qualified=False,
        accepted_target=300000, initial_candidate_target=450000, maximum_candidates=600000,
        initial_batch=len(records), source_process='Reuse explicitly reviewed English sources; generate fresh responses. This is production, not an untouched evaluation.',
        expansion='Additional source families require explicit source/slot review; do not cycle this bank to inflate volume.',
        other_languages='held', local_gpu_use=False, requested_capacity_split='4/4 when available',
        odin_concurrency=64, aggregate_odin_requests_per_rolling_minute=100,
        admission_policy='pending user selection; no default admission',
        correction_budget=1, historical_experiments_immutable=True,
        pins={**pins, **{str(p):file_hash(p) for p in [Path(__file__),
            Path('scripts/dfm16_staged_stories.py'), Path('scripts/dfm16_specialist_audit_v13.py'),
            Path('scripts/dfm16_experiment_transport.py'), Path('audit_pipeline/runtime.py')]}}))
    immutable_rows(root/'sources.jsonl', records)
    immutable_rows(root/'generation/inputs.jsonl', records)
    prepare_stage(root/'generation', records, POLICY)
    return records


def verify(root):
    for path, digest in load(root/'authorization.json')['pins'].items():
        if file_hash(Path(path)) != digest:
            raise ValueError('changed production dependency: '+path)


async def execute_stage(root, name, cls, records=None):
    verify(root)
    path = root/name
    if records is not None:
        immutable_rows(path/'inputs.jsonl', records)
        prepare_stage(path, records, POLICY)
    model, endpoint = MODELS['odin']
    adapter = cls(path, path/'audit', endpoint)
    adapter.model = model
    budget = Budget(BASE/'odin-requests.sqlite')
    client = ExperimentClient(budget, headers={'Authorization':'Bearer '+os.environ['ODIN_API_KEY']},
        timeout=900, trust_env=False, limits=httpx.Limits(max_connections=64))
    write_json(root/'status.json', dict(phase=name, production_authorized=True, qualified=False))
    try:
        await run(adapter, endpoint, 64, client=client, prefetch=1)
        for job in load(path/'manifest.json')['chunks']:
            adapter.verify_receipt(job, path/'audit'/job['job_id'])
        write_json(path/'audit/pipeline/state.json', dict(phase='complete'))
        immutable(path/'completed.json', dict(verified=True))
    finally:
        await client.aclose()
        write_json(root/'aggregate-odin-usage.json', budget.summary(6.25,25))
    return list(audited_records(path))


async def generate(root):
    await asyncio.to_thread(prepare, root)
    results = await execute_stage(root, 'generation', StagedGenerate)
    parents = [dict(r, messages=v['messages']) for r,v in results if v['status']=='generated']
    immutable_rows(root/'parents.jsonl', parents)
    immutable_rows(root/'generation-outcomes.jsonl', [dict(id=r['id'], status=v['status'],
        first_attempt_contract_clear=v.get('first_attempt_contract_clear')) for r,v in results])
    write_json(root/'status.json', dict(phase='generated_awaiting_audit', candidates=len(results),
        generated=len(parents), admitted=0, production_authorized=True, qualified=False))


async def audit(root):
    parents = list(rows(root/'parents.jsonl'))
    jobs = [dict(id=p['id']+'/'+scope, audit_id=p['id']+'/'+scope, parent_id=p['id'],
                 specialty=scope, evidence=evidence(p)) for p in parents for scope in SCOPES]
    results = await execute_stage(root, 'specialists', Specialist, jobs)
    screen, _ = verification_jobs(parents, results)
    immutable(root/'screen.json', screen)
    immutable_rows(root/'specialist-decisions.jsonl', [dict(id=p['id'],
        decision=whole_vote(screen[p['id']+'/'+s]['decision'] for s in SCOPES)) for p in parents])
    write_json(root/'status.json', dict(phase='audited_awaiting_policy', admitted=0,
        production_authorized=True, qualified=False))


def materialize(root):
    """Only an explicitly selected policy can admit; no implicit self-review waiver."""
    verify(root)
    policy = load(root/'selected-policy.json')
    if policy.get('policy') != 'odin_specialists' or policy.get('self_review_authorized') is not True:
        raise ValueError('explicit Odin specialist production selection required')
    stage = root/'specialists'
    adapter = Specialist(stage, stage/'audit', MODELS['odin'][1]); adapter.model=MODELS['odin'][0]
    for job in load(stage/'manifest.json')['chunks']:
        adapter.verify_receipt(job, stage/'audit'/job['job_id'])
    parents = list(rows(root/'parents.jsonl'))
    screen, _ = verification_jobs(parents, list(audited_records(stage)))
    accepted = [p for p in parents if whole_vote(screen[p['id']+'/'+s]['decision'] for s in SCOPES)=='accept']
    immutable_rows(root/'accepted/conversations.jsonl', [dict(id=p['id'], family=p['family'],
        language='en', task=p['task'], messages=p['messages'], source_review_origin=p['source_review_origin']) for p in accepted])
    immutable(root/'accepted/receipt.json', dict(count=len(accepted), policy=policy,
        sha256=file_hash(root/'accepted/conversations.jsonl'), statistically_qualified=False,
        production_authorized=True, provenance=str(root)))
    write_json(root/'status.json', dict(phase='materialized', admitted=len(accepted),
        production_authorized=True, qualified=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare','generate','audit','materialize'])
    parser.add_argument('--root', type=Path, default=ROOT)
    args=parser.parse_args()
    with lock(BASE/'.controller.lock'), lock(args.root/'.controller.lock'):
        if args.action=='prepare': prepare(args.root)
        elif args.action=='materialize': materialize(args.root)
        else: asyncio.run((generate if args.action=='generate' else audit)(args.root))
