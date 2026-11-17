"""Prepare/run a gated Qwen story pilot using audit_pipeline and externally owned servers."""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import subprocess
import sys
import time

import httpx

from dfm12.io import atomic, digest, file_hash, load, lock, rows, write_json
from scripts.prepare_dfm16_stories_v2 import chunks
from scripts.dfm16_story_v3 import POLICY, GENERATOR, AUDITOR, spec_for

DEFAULT = Path('data/dfm16/expansion-v1/stories/quality-v3-qwen')


def prepare_stage(path, records, task):
    if (path/'readiness.json').exists():
        return
    chunks(path, records, task)
    write_json(path/'quality-policy.json', dict(policy=POLICY, training_ready=False))


def prepare(base, concurrency=128, port_base=8800):
    stories = base.parent
    with lock(base/'.prepare.lock'):
        manual = Path('docs/reports/simplestories-v2-review-20261028.md')
        labels = {}
        for line in manual.read_text().splitlines():
            parts = [x.strip() for x in line.split('|')]
            if len(parts) == 5 and parts[2] in ('hold', 'clear', 'caveat'):
                labels[parts[1]] = parts[2]
        annotations, calibration, counts = {}, [], Counter()
        sample = stories/'quality-v2/pilot/manual-review-100.jsonl'
        for entry in rows(sample):
            candidate = dict(entry['candidate'])
            group = f'{candidate["language"]}/{candidate["task"]}'
            counts[group] += 1
            annotations[candidate['id']] = labels[f'{group} {counts[group]}']
            candidate['audit_id'] = candidate['id']
            calibration.append(candidate)
        if len(calibration) != 100 or len(annotations) != 100:
            raise ValueError('Expected exactly 100 unique reviewed examples')
        prepare_stage(base/'calibration', calibration, 'blind_judge_calibration')
        write_json(base/'calibration-labels.json', dict(labels=annotations,
            report_sha256=file_hash(manual), input_sha256=file_hash(sample)))
        def seeds():
            for language in ('en', 'da', 'hi', 'ja'):
                pool = list(rows(stories/f'seeds-{language}.jsonl'))
                random.Random(f'{POLICY}:{language}').shuffle(pool)
                for seed in pool[:2000]:
                    key = digest([POLICY, language, seed['provenance']])
                    yield dict(id=key, audit_id=key, language=language,
                        source_language='English' if language in ('en', 'da') else
                                        'Hindi' if language == 'hi' else 'Japanese',
                        seed=seed['text'], provenance=seed['provenance'], task='seed_quality')
        prepare_stage(base/'seeds', seeds(), 'seed_quality')
        write_json(base/'roadmap.json', dict(generator=GENERATOR, auditor=AUDITOR,
            generation_ports=list(range(port_base, port_base+5)), auditor_ports=list(range(port_base+5, port_base+8)),
            concurrency_per_server=concurrency, stages=['blind_100_review', 'seed_screen_8000',
                'generate_2000', 'independent_review', 'manual_review_gate',
                'approved_production_with_replenishment'],
            accepted_target=300000, initial_candidate_budget=450000, maximum_candidate_budget=600000,
            preserve_old_rows=True, production_authorized=False, server_ownership='external',
            public_release_authorized=False))


def audited_records(stage):
    if load(stage/'audit/pipeline/state.json')['phase'] != 'complete':
        raise ValueError(f'Incomplete stage: {stage}')
    for job in load(stage/'manifest.json')['chunks']:
        folder = stage/'audit'/job['job_id']
        receipt = load(folder/'receipt.json')
        if receipt['input_sha256'] != job['sha256'] or receipt['results_sha256'] != file_hash(folder/'results.jsonl'):
            raise ValueError('Audit receipt mismatch')
        source = {r['audit_id']: r for r in rows(stage/job['input'])}
        seen = set()
        for result in rows(folder/'results.jsonl'):
            key = result['audit_id']
            if key in seen or key not in source:
                raise ValueError('Duplicate/unknown result')
            seen.add(key)
            yield source[key], result
        if seen != set(source):
            raise ValueError('Missing rows')


def calibration_report(base):
    labels = load(base/'calibration-labels.json')['labels']
    counts = Counter()
    for source, result in audited_records(base/'calibration'):
        decision = result.get('review', {}).get('decision', 'unresolved')
        counts[f'{labels[source["id"]]}/{decision}'] += 1
    write_json(base/'calibration-report.json', dict(counts=dict(counts),
        interpretation='clear/accept and hold/reject are desired; caveats are not binary ground truth',
        production_authorized=False))


def make_pilot(base):
    pools = {lang: [] for lang in ('en', 'da', 'hi', 'ja')}
    for source, result in audited_records(base/'seeds'):
        if result.get('review', {}).get('decision') == 'accept':
            pools[source['language']].append(source)
    if any(len(pool) < 100 for pool in pools.values()):
        raise ValueError(f'Insufficient clean seeds: { {k: len(v) for k,v in pools.items()} }')
    def candidates():
        for language, pool in pools.items():
            for i in range(100):
                for j, task in enumerate(('creative', 'revision', 'summary', 'rewrite', 'qa')):
                    source = pool[(i*5+j) % len(pool)]
                    spec = spec_for(task, i, language)
                    key = digest([POLICY, source['id'], task, i, spec])
                    yield dict(id=key, audit_id=key, language=language, task=task,
                        variant=i, seed=source['seed'], specification=spec,
                        revisions=len(spec.get('revision_operations', [])),
                        provenance=dict(source['provenance'], seed_audit_id=source['id'],
                            policy=POLICY, generator=GENERATOR, auditor=AUDITOR))
    prepare_stage(base/'generation', candidates(), 'story_generation')


def make_reviews(base):
    def records():
        for source, result in audited_records(base/'generation'):
            if result['status'] == 'generated':
                yield dict(result['candidate'], audit_id=source['audit_id'])
    prepare_stage(base/'review', records(), 'whole_conversation_quality')


def pilot_report(base):
    rng = random.Random(20261028)
    counts, samples, accepted = Counter(), {}, Counter()
    for source, result in audited_records(base/'review'):
        group = f'{source["language"]}/{source["task"]}'
        decision = result.get('review', {}).get('decision', 'unresolved')
        counts[f'{group}/{decision}'] += 1
        if decision != 'accept':
            continue
        accepted[group] += 1
        sample = samples.setdefault(group, [])
        if len(sample) < 5:
            sample.append(source)
        else:
            index = rng.randrange(accepted[group])
            if index < 5:
                sample[index] = source
    with atomic(base/'manual-review.jsonl') as f, atomic(base/'manual-review.md') as md:
        md.write('# Qwen v3 pilot: manual review pending\n\n')
        for group, sample in sorted(samples.items()):
            for i, row in enumerate(sample, 1):
                f.write(json.dumps(row, ensure_ascii=False)+'\n')
                md.write(f'## {group} sample {i}\n\nID: {row["id"]}\n\n')
                for message in row['messages']:
                    md.write(f'**{message["role"]}**\n\n{message["content"]}\n\n')
    generation_counts = Counter(r['status'] for _, r in audited_records(base/'generation'))
    write_json(base/'pilot-report.json', dict(counts=dict(counts), generation_counts=dict(generation_counts),
        manual_review_complete=False, production_authorized=False,
        selected=sum(map(len, samples.values()))))


def wait_servers(ports, model, base):
    while True:
        missing = []
        for port in ports:
            try:
                response = httpx.get(f'http://127.0.0.1:{port}/v1/models', timeout=3, trust_env=False)
                response.raise_for_status()
                if not any(m['id'] == model and m.get('max_model_len', 0) >= 32768
                           for m in response.json()['data']):
                    missing.append(port)
            except (httpx.HTTPError, ValueError, KeyError):
                missing.append(port)
        if not missing:
            return
        write_json(base/'status.json', dict(phase='waiting_for_external_servers', model=model,
            missing_ports=missing, time=time.time(), no_servers_started_or_stopped=True))
        time.sleep(30)


def run_stage(base, name, kind, ports, model, concurrency=128):
    stage = base/name
    state = stage/'audit/pipeline/state.json'
    if state.exists() and load(state)['phase'] == 'complete':
        # Validate completed artifacts before downstream use, not silent acceptance.
        for _ in audited_records(stage):
            pass
        return
    wait_servers(ports, model, base)
    write_json(base/'status.json', dict(phase=name, time=time.time(), model=model,
        ports=ports, concurrency_per_server=concurrency))
    subprocess.run([sys.executable, '-u', '-m', 'audit_pipeline', kind,
        '--root', str(stage), '--output', str(stage/'audit'), '--model', model,
        '--ports', ','.join(map(str, ports)), '--concurrency', str(concurrency)], check=True)
    if load(state)['phase'] != 'complete':
        raise RuntimeError(f'Stage did not complete: {name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--concurrency', type=int, default=128)
    parser.add_argument('--port-base', type=int, default=8800)
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 1024:
        parser.error('--concurrency must be between 1 and 1024')
    if not 1 <= args.port_base <= 65528:
        parser.error('--port-base must leave room for eight ports')
    generation_ports = list(range(args.port_base, args.port_base+5))
    auditor_ports = list(range(args.port_base+5, args.port_base+8))
    base = args.root.resolve()
    with lock(base/'.roadmap.lock'):
        prepare(base, args.concurrency, args.port_base)
        if args.prepare_only:
            return
        try:
            run_stage(base, 'calibration', 'story-review', auditor_ports, AUDITOR, args.concurrency)
            calibration_report(base)
            run_stage(base, 'seeds', 'story-seeds', auditor_ports, AUDITOR, args.concurrency)
            make_pilot(base)
            run_stage(base, 'generation', 'story-generate', generation_ports, GENERATOR, args.concurrency)
            make_reviews(base)
            run_stage(base, 'review', 'story-review', auditor_ports, AUDITOR, args.concurrency)
            pilot_report(base)
            write_json(base/'status.json', dict(phase='awaiting_manual_review', production_authorized=False,
                report=str(base/'pilot-report.json'), time=time.time()))
        except BaseException as exc:
            write_json(base/'status.json', dict(phase='failed', error=repr(exc), time=time.time()))
            raise


if __name__ == '__main__':
    main()
