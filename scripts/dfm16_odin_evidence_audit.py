"""Odin-only development ablation while local GPUs are unavailable.

Odin generated these examples: none of its verdicts can independently admit them.
Reuses completed Qwen evidence from v8, comparing matched direct Odin verdicts
against Odin verification with that evidence. Original v7/v8 artifacts stay fixed.
"""
import argparse
import asyncio
import os
import random
import time
from pathlib import Path

import httpx
from audit_pipeline.runtime import run
from dfm12.io import file_hash, load, lock, rows, write_json
from scripts.dfm16_story_calibration import immutable, immutable_rows, metrics
from scripts.dfm16_evidence_audit import (
    ROOT as LOCAL, EvidenceAudit, EvidenceVerifier, requests, VERDICT_PROMPT,
)
from scripts.dfm16_staged_experiment import MODELS
from scripts.dfm16_staged_validation_campaign import BASE
from scripts.dfm16_experiment_transport import Budget, ExperimentClient
from scripts.dfm16_validation_report import usage
from scripts.queue_dfm16_stories_qwen import prepare_stage, audited_records

ROOT = Path('data/dfm16/staged-stories-odin-evidence-v9-20261029')


class OdinVerifier(EvidenceVerifier):
    def prepare(self, row):
        value = super().prepare(row)
        value.pop('max_tokens')
        value.pop('chat_template_kwargs')
        value.update(max_completion_tokens=32, reasoning_effort='none', include_reasoning=False)
        return value


def prepare(root):
    stage = LOCAL / 'evidence/qwen27b'
    model, endpoint = MODELS['qwen27b']
    adapter = EvidenceAudit(stage, stage/'audit', endpoint)
    adapter.model = model
    pins = {}
    for job in load(stage/'manifest.json')['chunks']:
        folder = stage/'audit'/job['job_id']
        adapter.verify_receipt(job, folder)
        pins[str(folder/'receipt.json')] = file_hash(folder/'receipt.json')
    for path in [LOCAL/'design.json', LOCAL/'reference.jsonl', LOCAL/'parents.jsonl',
                 Path(__file__), Path('scripts/dfm16_evidence_audit.py'),
                 Path('scripts/dfm16_staged_audit.py'), Path('scripts/dfm16_experiment_transport.py')]:
        pins[str(path)] = file_hash(path)
    evidence = {r['id']:v.get('review',{}).get('evidence') for r,v in audited_records(stage)}
    parents = list(rows(LOCAL/'parents.jsonl'))
    records = []
    for arm, peer in [('direct',None),('with_evidence',evidence)]:
        for r in requests(parents, peer):
            identifier = f'{r["id"]}/{arm}'
            records.append(dict(r, parent_id=r['id'], arm=arm, id=identifier, audit_id=identifier))
    random.Random(202610290901).shuffle(records)
    immutable(root/'design.json',dict(pins=pins, prompt=VERDICT_PROMPT,
        model='odin-2-large', evidence_model='qwen27b', generator='odin-2-large',
        scope='paired adaptive development only; generator self-review cannot admit data',
        qualified=False, production_authorized=False, missing_evidence='unresolved',
        actual_requests_per_rolling_minute=100, concurrency=64, retries=1,
        seed=202610290901, evidence_usable=sum(bool(v) for v in evidence.values()),
        evidence_total=len(evidence), arms=['direct','with_evidence'],
        ledger=str(BASE/'odin-requests.sqlite')))
    immutable_rows(root/'reference.jsonl',rows(LOCAL/'reference.jsonl'))
    immutable_rows(root/'audit-stage/inputs.jsonl', records)
    prepare_stage(root/'audit-stage', records, 'odin_evidence_development')
    actual=[r for job in load(root/'audit-stage/manifest.json')['chunks']
            for r in rows(root/'audit-stage'/job['input'])]
    if actual!=records:raise ValueError('changed stage inputs')
    return records


def report(root):
    for path,digest in load(root/'design.json')['pins'].items():
        if file_hash(Path(path))!=digest:raise ValueError('changed experiment evidence')
    stage=root/'audit-stage'
    model,endpoint=MODELS['odin']
    adapter=OdinVerifier(stage,stage/'audit',endpoint);adapter.model=model
    pins={}
    for job in load(stage/'manifest.json')['chunks']:
        folder=stage/'audit'/job['job_id']
        adapter.verify_receipt(job,folder)
        pins[str(folder/'receipt.json')]=file_hash(folder/'receipt.json')
    observed={'direct':{},'with_evidence':{}};attempts={'direct':[],'with_evidence':[]}
    for r,v in audited_records(stage):
        observed[r['arm']][r['parent_id']]=v.get('review',{}).get('decision','unresolved')
        attempts[r['arm']].extend(v['attempts'])
    reference=list(rows(root/'reference.jsonl'));scored={};reports={}
    for arm,decisions in observed.items():
        scored[arm]=[dict(r,votes={'odin':decisions.get(r['id'],'unresolved')},
            decision=decisions.get(r['id'],'unresolved') if r['deterministic_pass'] else 'reject') for r in reference]
        value=metrics(scored[arm])
        value.update(generated_only=metrics([r for r in scored[arm] if r['deterministic_pass']]),
            tasks={task:metrics([r for r in scored[arm] if r['task']==task]) for task in sorted({r['task'] for r in reference})})
        reports[arm]=value
        immutable_rows(root/'scored'/f'{arm}.jsonl',scored[arm])
    paired={}
    for label in ('bad','clear','borderline'):
        pairs=[(a,b) for a,b in zip(scored['direct'],scored['with_evidence']) if a['label']==label]
        paired[label]=dict(direct_accept_evidence_reject=sum(a['decision']=='accept' and b['decision']=='reject' for a,b in pairs),
            direct_accept_evidence_unresolved=sum(a['decision']=='accept' and b['decision']=='unresolved' for a,b in pairs),
            direct_reject_evidence_accept=sum(a['decision']=='reject' and b['decision']=='accept' for a,b in pairs))
    usage_by_arm={arm:usage(a) for arm,a in attempts.items()}
    for v in usage_by_arm.values():v['estimated_DKK']=(v['prompt_tokens']*6.25+v['completion_tokens']*25)/1e6
    output=dict(results=reports, paired=paired, usage=usage_by_arm,
        frozen_v7_baseline=metrics(reference),qualified=False,production_authorized=False,
        reference='provisional assistant-manual, reused development sample',
        caveat='Odin generator self-review; no independent admission or qualification. Evidence produced by Qwen. Historical DKK estimates exclude local evidence-production costs.')
    immutable(root/'report.json',output)
    for p in [root/'design.json',root/'report.json',root/'reference.jsonl']:
        pins[str(p)]=file_hash(p)
    immutable(root/'receipt.json',dict(pins=pins,qualified=False,production_authorized=False))
    return output


async def execute(root):
    prepare(root)
    stage=root/'audit-stage';model,endpoint=MODELS['odin']
    adapter=OdinVerifier(stage,stage/'audit',endpoint);adapter.model=model
    budget=Budget(BASE/'odin-requests.sqlite')
    started=time.monotonic()
    write_json(stage/'audit/pipeline/state.json',dict(phase='running'))
    client=ExperimentClient(budget,headers={'Authorization':'Bearer '+os.environ['ODIN_API_KEY']},
        timeout=900,trust_env=False,limits=httpx.Limits(max_connections=64))
    try:
        await run(adapter,endpoint,64,client=client,prefetch=1)
        for job in load(stage/'manifest.json')['chunks']:
            adapter.verify_receipt(job,stage/'audit'/job['job_id'])
        write_json(stage/'audit/pipeline/state.json',dict(phase='complete'))
        immutable(root/'timing.json',dict(seconds=time.monotonic()-started))
        report(root)
        write_json(root/'status.json',dict(phase='development_complete',qualified=False,production_authorized=False))
    finally:
        await client.aclose()
        write_json(root/'aggregate-odin-usage.json',budget.summary(6.25,25))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run','report'])
    parser.add_argument('--root',type=Path,default=ROOT);args=parser.parse_args()
    with lock(BASE/'.controller.lock'),lock(args.root/'.controller.lock'):
        if args.action=='prepare':prepare(args.root)
        elif args.action=='report':report(args.root)
        else:asyncio.run(execute(args.root))
