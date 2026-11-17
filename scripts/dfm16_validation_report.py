"""Receipt-verified English validation results; never promote production data."""
import argparse
from collections import Counter
from pathlib import Path

from dfm12.io import file_hash, load, lock, rows, write_json
from scripts.dfm16_story_calibration import immutable, immutable_rows, metrics, bound
from scripts.dfm16_staged_audit import StagedAudit
from scripts.dfm16_staged_precision import PrecisionAudit
from scripts.dfm16_staged_experiment import MODELS
from scripts.dfm16_staged_stories import StagedGenerate
from scripts.dfm16_staged_validation import report
from scripts.dfm16_staged_validation_campaign import ROOT
from scripts.dfm16_validation_audit import require_sealed_labels, whole_vote
from scripts.queue_dfm16_stories_qwen import audited_records


def usage(attempts):
    attempts = list(attempts)
    bodies = [a['response'] for a in attempts if 'response' in a]
    return dict(attempts=len(attempts), responses=len(bodies),
                missing_usage=sum(not b.get('usage') for b in bodies),
                prompt_tokens=sum(b.get('usage', {}).get('prompt_tokens', 0) for b in bodies),
                completion_tokens=sum(b.get('usage', {}).get('completion_tokens', 0) for b in bodies))


def generation_attempts_from(result):
    # Code-assembled stages (including selective undo) have no model attempts.
    return [a for stage in result['stages'].values() for a in stage.get('attempts', [])]


def assemble(packet, labels, private, votes):
    """Keep every sampled family, including intake and deterministic failures."""
    packet = list(packet)
    identifiers = {p['id'] for p in packet}
    if len(identifiers) != len(packet):
        raise ValueError('duplicate packet')
    mappings = []
    for values in (labels, private, votes):
        values = list(values)
        mapping = {v['id']: v for v in values}
        if len(mapping) != len(values) or set(mapping) != identifiers:
            raise ValueError('report evidence coverage mismatch')
        mappings.append(mapping)
    labels, private, votes = mappings
    result = []
    for p in packet:
        identifier = p['id']
        label, provenance, vote = labels[identifier], private[identifier], votes[identifier]
        deterministic = p['status'] == 'generated'
        if vote['deterministic_pass'] != deterministic:
            raise ValueError('deterministic admission mismatch')
        result.append(dict(id=identifier, family=provenance['family'], index=provenance['index'],
            language='en', task=p['task'], cohort='validation', status=p['status'],
            label=label['final_label'], first_label=label['first_label'],
            corrected=any(a.get('findings') for s in p['stages'].values()
                          for a in s['attempts'][:-1]),
            deterministic_pass=deterministic, votes=vote['votes'], decision=vote['decision'],
            category=label.get('category', 'deterministic' if p['status']=='deterministic_failure' else 'source_intake'),
            note=label['note']))
    return result


def finish(root):
    cohort = root / 'en/validation'
    packet, labels = require_sealed_labels(cohort)
    audit = cohort / 'audit'
    for path, digest in load(audit / 'receipt.json')['pins'].items():
        if file_hash(Path(path)) != digest:
            raise ValueError('audit evidence changed')
    pins = {}
    requests = [r for kind in ('base', 'precision') for r in rows(audit / f'{kind}-checks.jsonl')]
    required = {}
    for r in requests:
        required.setdefault(r['parent_id'], []).append(r['id'])
    observed, audit_usage, timings = {}, {}, {}
    for name in ('flash', 'qwen27b'):
        observed[name] = {}
        attempts = []
        for kind, cls in [('base', StagedAudit), ('precision', PrecisionAudit)]:
            stage = audit / kind / name
            model, endpoint = MODELS[name]
            adapter = cls(stage, stage / 'audit', endpoint)
            adapter.model = model
            for job in load(stage / 'manifest.json')['chunks']:
                folder = stage / 'audit' / job['job_id']
                adapter.verify_receipt(job, folder)
                pins[str(folder / 'receipt.json')] = file_hash(folder / 'receipt.json')
            for request, value in audited_records(stage):
                if request['id'] in observed[name]:
                    raise ValueError('duplicate review')
                observed[name][request['id']] = value.get('review', {}).get('decision', 'unresolved')
                attempts.extend(value['attempts'])
            timings[f'{name}/{kind}'] = load(stage / 'latest-run-timing.json')['seconds']
        if set(observed[name]) != {r['id'] for r in requests}:
            raise ValueError('incomplete audit evidence')
        audit_usage[name] = usage(attempts)
    votes = list(rows(cohort / 'votes.jsonl'))
    for v in votes:
        expected = {name: whole_vote(observed[name].get(i, 'unresolved')
                    for i in required.get(v['id'], [])) for name in observed}
        if v['votes'] != expected:
            raise ValueError('whole-conversation votes differ from receipts')
    private = list(rows(cohort / 'provenance-private.jsonl'))
    records = assemble(packet, labels, private, votes)
    generation_attempts, generation_ids = [], set()
    generation_wall = 0
    for stage in sorted((cohort / 'generation').iterdir()):
        if not stage.is_dir():
            continue
        model, endpoint = MODELS['odin']
        adapter = StagedGenerate(stage, stage / 'audit', endpoint)
        adapter.model = model
        for job in load(stage / 'manifest.json')['chunks']:
            folder = stage / 'audit' / job['job_id']
            adapter.verify_receipt(job, folder)
            pins[str(folder / 'receipt.json')] = file_hash(folder / 'receipt.json')
        for source, result in audited_records(stage):
            if source['id'] in generation_ids:
                raise ValueError('duplicate generation')
            generation_ids.add(source['id'])
            generation_attempts.extend(generation_attempts_from(result))
        generation_wall += load(stage / 'state.json')['seconds']
    expected_ids = {v['source_id'] for v in private
                    if next(p for p in packet if p['id']==v['id'])['status'] != 'source_rejected'}
    if generation_ids != expected_ids:
        raise ValueError('generation coverage mismatch')
    generation_usage = usage(generation_attempts)
    generation_usage.update(estimated_DKK=(generation_usage['prompt_tokens']*6.25+
        generation_usage['completion_tokens']*25)/1e6,
        pricing_basis='historical experiment estimate, 6.25/25 DKK per million input/output tokens',
        excludes='local GPU, manual assessment and unreported provider usage costs')
    value = report(root, 'en', records)
    corrected = [r for r in records if r['corrected']]
    generated = [r for r in records if r['status']=='generated']
    unresolved = sum(r['label']=='unresolved' or r['decision']=='unresolved' for r in records)
    details = dict(reference='provisional assistant-manual; not independent human certification',
        qualification=value, statuses=dict(Counter(r['status'] for r in records)),
        first_labels=dict(Counter(r['first_label'] for r in records)),
        final_labels=dict(Counter(r['label'] for r in records)),
        first_attempt_clear_yield=sum(r['first_label']=='clear' for r in records)/len(records),
        final_clear_yield=sum(r['label']=='clear' for r in records)/len(records),
        correction=dict(attempted_examples=len(corrected),
            recovered_clear=sum(r['first_label']!='clear' and r['label']=='clear' for r in corrected),
            remaining_bad=sum(r['label']=='bad' for r in corrected)),
        generated_only=metrics(generated),
        unresolved_evidence_or_decision=dict(numerator=unresolved, denominator=len(records),
            rate=unresolved/len(records), upper95=bound(unresolved, len(records))),
        defect_categories=dict(Counter(r['category'] for r in records if r['label']=='bad')),
        generation_usage=generation_usage, audit_usage=audit_usage,
        throughput=dict(generation_batch_wall_seconds_sum=generation_wall,
            generated_per_batch_second=len(generation_ids)/generation_wall,
            audit_stage_seconds=timings,
            caveat='Batch execution times exclude manual review gaps; audit stages overlap between models. Requested 4/4 capacity was not deployed or benchmarked.'),
        production_authorized=False)
    output = root / 'en/reports'
    immutable_rows(output / 'scored-conversations.jsonl', records)
    immutable_rows(output / 'accepted-defects.jsonl', [r for r in records
                   if r['label']=='bad' and r['decision']=='accept'])
    immutable_rows(output / 'borderline-conversations.jsonl', [r for r in records
                   if r['label']=='borderline'])
    immutable(output / 'results.json', details)
    for path in [cohort/'label-receipt.json', cohort/'packet-receipt.json', cohort/'votes.jsonl',
                 cohort/'provenance-private.jsonl', output/'scored-conversations.jsonl',
                 output/'accepted-defects.jsonl', output/'borderline-conversations.jsonl',
                 output/'results.json', output/'qualification.json', Path(__file__)]:
        pins[str(path)] = file_hash(path)
    immutable(output / 'receipt.json', dict(pins=pins, production_authorized=False))
    write_json(root / 'en/status.json', dict(phase='validation_complete', sampled=800,
        qualified=value['qualified'], lifecycle=value['validation_lifecycle'],
        production_authorized=False, reference='provisional assistant-manual'))
    return details


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    with lock(args.root / '.controller.lock'):
        result = finish(args.root)
        print(result['qualification'])
