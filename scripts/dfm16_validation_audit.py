"""Execute the frozen English audit only after complete blinded labels are sealed."""
import argparse
import asyncio
import time
from pathlib import Path

import httpx
from audit_pipeline.runtime import run
from dfm12.io import file_hash, load, lock, rows, write_json
from scripts.dfm16_story_calibration import immutable, immutable_rows, sha
from scripts.dfm16_staged_audit import StagedAudit, checks
from scripts.dfm16_staged_precision import PrecisionAudit, supplemental_checks
from scripts.dfm16_staged_experiment import MODELS
from scripts.dfm16_staged_validation import verify_freeze, supplementary_trigger
from scripts.dfm16_staged_validation_campaign import ROOT
from scripts.queue_dfm16_stories_qwen import prepare_stage, audited_records


def require_sealed_labels(cohort):
    receipt = load(cohort / 'label-receipt.json')
    for name, key in [('blind-packet.jsonl', 'packet_sha256'),
                      ('manual-labels.jsonl', 'labels_sha256')]:
        if file_hash(cohort / name) != receipt[key]:
            raise ValueError('sealed labeling evidence changed')
    packet = list(rows(cohort / 'blind-packet.jsonl'))
    labels = list(rows(cohort / 'manual-labels.jsonl'))
    if len(packet) != 800 or len(labels) != 800:
        raise ValueError('all 800 blinded labels required')
    if len({r['id'] for r in labels}) != 800 or {r['id'] for r in packet} != {r['id'] for r in labels}:
        raise ValueError('labels do not cover packet')
    if receipt.get('judge_votes_exposed') is not False:
        raise ValueError('blinded labeling required')
    return packet, labels


def prepare(root):
    frozen = verify_freeze(root, 'en')
    if (frozen['generator'], frozen['policy']) != ('odin', 'both'):
        raise ValueError('this driver implements only frozen English Odin/both')
    for path, digest in load(root / 'protocol.json')['software'].items():
        if file_hash(Path(path)) != digest:
            raise ValueError('frozen software changed')
    cohort = root / 'en/validation'
    packet, labels = require_sealed_labels(cohort)
    # This decision is made without reading any audit verdicts.
    blind_counts = [dict(id=r['id'], label=r['final_label']) for r in labels]
    trigger = root / 'en/supplementary-trigger.json'
    if trigger.exists():
        if load(trigger)['labels_sha256'] != sha(blind_counts):
            raise ValueError('supplementary trigger labels changed')
    else:
        supplementary_trigger(root, 'en', blind_counts)
    packet_receipt = load(cohort / 'packet-receipt.json')
    for path, digest in packet_receipt['inputs'].items():
        if file_hash(Path(path)) != digest:
            raise ValueError('packet source evidence changed')
    private = {r['id']: r for r in rows(cohort / 'provenance-private.jsonl')}
    parents = []
    for p in packet:
        if p['status'] != 'generated':
            continue  # Objective failures are withheld without semantic admission.
        r = private[p['id']]
        source = load(cohort / 'source-review' / f'{r["index"]:04d}.json')['generation_input']
        parents.append(dict(source, id=p['id'], messages=p['messages']))
    audit = cohort / 'audit'
    immutable_rows(audit / 'parents.jsonl', parents)
    for kind, builder in [('base', checks), ('precision', supplemental_checks)]:
        requests = [c for parent in parents for c in builder(parent)]
        immutable_rows(audit / f'{kind}-checks.jsonl', requests)
        for judge in ('flash', 'qwen27b'):
            stage = audit / kind / judge
            prepare_stage(stage, requests, f'validation_{kind}')
            actual = [r for job in load(stage / 'manifest.json')['chunks']
                      for r in rows(stage / job['input'])]
            if actual != requests:
                raise ValueError('prepared audit inputs differ from frozen checks')
    immutable(audit / 'receipt.json', dict(pins={str(p): file_hash(p) for p in [
        cohort / 'label-receipt.json', cohort / 'packet-receipt.json',
        cohort / 'manual-labels.jsonl', cohort / 'blind-packet.jsonl',
        audit / 'parents.jsonl', audit / 'base-checks.jsonl', audit / 'precision-checks.jsonl',
        Path(__file__) ]}, generator='odin', judges=['flash', 'qwen27b'], policy='both'))


def whole_vote(values):
    values = list(values)
    if not values or any(v not in ('accept', 'reject') for v in values):
        return 'unresolved'
    return 'reject' if 'reject' in values else 'accept'


async def execute(root):
    prepare(root)
    audit = root / 'en/validation/audit'
    for path, digest in load(audit / 'receipt.json')['pins'].items():
        if file_hash(Path(path)) != digest:
            raise ValueError('audit evidence changed')

    async def judge(name):
        model, endpoint = MODELS[name]
        # Sequential stages keep each server at its aggregate concurrency of 128.
        for kind, cls in [('base', StagedAudit), ('precision', PrecisionAudit)]:
            stage = audit / kind / name
            adapter = cls(stage, stage / 'audit', endpoint)
            adapter.model = model
            started = time.monotonic()
            write_json(stage / 'audit/pipeline/state.json', dict(phase='running'))
            async with httpx.AsyncClient(timeout=900, trust_env=False,
                    limits=httpx.Limits(max_connections=128)) as client:
                await run(adapter, endpoint, 128, client=client, prefetch=1)
            for job in load(stage / 'manifest.json')['chunks']:
                adapter.verify_receipt(job, stage / 'audit' / job['job_id'])
            write_json(stage / 'audit/pipeline/state.json', dict(phase='complete'))
            immutable(stage / 'completed.json', dict(verified=True))
            write_json(stage / 'latest-run-timing.json', dict(seconds=time.monotonic() - started))
    await asyncio.gather(judge('flash'), judge('qwen27b'))
    requests = [r for kind in ('base', 'precision') for r in rows(audit / f'{kind}-checks.jsonl')]
    votes = {}
    for name in ('flash', 'qwen27b'):
        votes[name] = {r['id']: result.get('review', {}).get('decision', 'unresolved')
            for kind in ('base', 'precision') for r, result in audited_records(audit / kind / name)}
    scored = []
    for p in rows(root / 'en/validation/blind-packet.jsonl'):
        relevant = [r['id'] for r in requests if r['parent_id'] == p['id']]
        whole = {name: whole_vote(votes[name].get(i, 'unresolved') for i in relevant) for name in votes}
        decision = whole_vote(whole.values()) if p['status'] == 'generated' else 'reject'
        scored.append(dict(id=p['id'], votes=whole, decision=decision,
                           deterministic_pass=p['status'] == 'generated'))
    immutable_rows(root / 'en/validation/votes.jsonl', scored)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    with lock(args.root / '.controller.lock'):
        if args.action == 'prepare':
            prepare(args.root)
        else:
            asyncio.run(execute(args.root))
