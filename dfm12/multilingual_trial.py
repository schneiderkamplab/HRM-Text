"""Fail-closed calibration gate and diagnostic reporting for the 700-slot trial."""
import asyncio
import json
from collections import Counter
from pathlib import Path

from .io import atomic, file_hash, load, write_json
from .multilingual_calibration import calibration_cases, score_reviews
from .multilingual_review import review_request
from .multilingual_tasks import MODEL

POLICY = 'all-controls-pass-v1'


def verify_inputs(root, require_receipt=True):
    root = Path(root)
    config = load(root / 'pilot-config.json')
    if (config.get('calibration_policy') != POLICY or not config.get('second_review')
            or config.get('generator_model') != MODEL or config.get('reviewer_model') != MODEL
            or config.get('bulk_authorized') is not False):
        raise ValueError('Invalid calibrated trial policy/model')
    for name, expected in load(root / 'seeds-ready.json').items():
        if file_hash(root / name) != expected:
            raise ValueError('Trial input changed: ' + name)
    for name, expected in load(root / 'implementation-pins.json').items():
        if file_hash(Path(__file__).parent / name) != expected:
            raise ValueError('Trial implementation changed: ' + name)
    if load(root / 'calibration/controls.json') != calibration_cases():
        raise ValueError('Calibration controls changed')
    inspection = load(root / 'calibration/render-inspection/inspection.json')
    for name, expected in inspection['pins'].items():
        if file_hash(Path(inspection['tokenizer_dir']) / name) != expected:
            raise ValueError('Reviewer tokenizer changed: ' + name)
    if require_receipt:
        receipt = load(root / 'cpu-preflight-passed.json')
        if receipt.get('passed') is not True or receipt.get('seeds_ready_sha256') != file_hash(root / 'seeds-ready.json'):
            raise ValueError('Missing/stale CPU preflight receipt')
    return config


async def gate(root, session, endpoints, query):
    config = verify_inputs(root) or {}
    from .multilingual_diagnose import configured_review_request, configured_review_keeps
    cases = load(root / 'calibration/controls.json')
    concurrency = config.get('calibration_concurrency', 2 if config.get('diagnostic_followup') else 16)
    if type(concurrency) is not int or not 1 <= concurrency <= 16:
        raise ValueError('Calibration concurrency must be an integer in 1..16')
    semaphore = asyncio.Semaphore(concurrency)
    reviews, errors = {}, {}
    async def one(index, case):
        async with semaphore:
            try:
                reviews[case['name']] = await query(session, endpoints[index % len(endpoints)], configured_review_request(case['record'], config))
                configured_review_keeps(reviews[case['name']], case['record'], config)
            except Exception as exc:
                errors[case['name']] = repr(exc)
    await asyncio.gather(*(one(i, case) for i, case in enumerate(cases)))
    structured = config.get('review_options', {}).get('variant') in ('structured4096', 'tools4096', 'routed4096')
    report = score_reviews(cases, reviews, validator=(lambda review, record:
                          configured_review_keeps(review, record, config)) if structured else None)
    failures = [d for d in report['details'] if d['status'] != 'valid' or d['actual_keep'] != d['expected_keep']]
    # Labeled dimension disagreement also blocks, even if the final keep matches.
    dimension_failures = [c['name'] for c in cases if isinstance(reviews.get(c['name']), dict) and any(
        expected is not None and reviews[c['name']].get(key) != expected
        for key, expected in c['expected_dimensions'].items())]
    passed = not failures and not dimension_failures and not errors
    report.update(passed=passed, policy=POLICY, reviews=reviews, errors=errors,
                  dimension_failures=dimension_failures,
                  generation_authorized=passed and not config.get('calibration_measurement_only', False),
                  pause_recommendations=[] if passed else ['Pause the entire trial; inspect failed controls. Do not drop language/family combinations.'],
                  bulk_authorized=False)
    report['by_family'] = {}
    for case, detail in zip(cases, report['details']):
        bucket = report['by_family'].setdefault(case['group'], {'total': 0, 'agreement': 0, 'failed': 0})
        bucket['total'] += 1
        agreed = (detail['status'] == 'valid' and detail['actual_keep'] == detail['expected_keep']
                  and case['name'] not in dimension_failures and case['name'] not in errors)
        bucket['agreement'] += agreed
        bucket['failed'] += not agreed
    write_json(root / 'review-calibration.json', report)
    if not passed:
        raise RuntimeError('All-control calibration gate failed; zero generation authorized')


def outcomes(store):
    groups = []
    with atomic(store.root / 'trial-inspection.jsonl') as handle:
        for language in store.config['languages']:
            for family in store.quotas:
                rows = store.db.execute('SELECT status,attempts,candidate,audit,error FROM slots WHERE language=? AND family=? ORDER BY slot', (language, family)).fetchall()
                events = store.db.execute('SELECT state,detail FROM events WHERE language=? AND family=? ORDER BY time', (language, family)).fetchall()
                dimensions = {key: Counter() for key in ('language_quality', 'coherence', 'usefulness',
                              'language_correct', 'meaning_correct', 'constraints_met')}
                for _, detail in events:
                    audit = json.loads(detail).get('audit', {})
                    for key, counts in dimensions.items():
                        value = audit.get(key, audit.get('second_review', {}).get(key))
                        counts['unreviewed' if value is None else str(value).lower()] += 1
                groups.append(dict(language=language, family=family, statuses=dict(Counter(r[0] for r in rows)),
                                   attempts=sum(r[1] for r in rows), events=dict(Counter(e[0] for e in events)),
                                   dimensions=dimensions))
                for status, _, candidate, audit, _ in [r for r in rows if r[0] == 'accepted'][:3]:
                    handle.write(json.dumps(dict(language=language, family=family, state=status,
                        candidate=json.loads(candidate), audit=json.loads(audit)), ensure_ascii=False) + '\n')
                for status in ('rejected', 'failed_attempt'):
                    for state, detail in [e for e in events if e[0] == status][:3]:
                        handle.write(json.dumps(dict(language=language, family=family, state=state, detail=json.loads(detail)), ensure_ascii=False) + '\n')
    write_json(store.root / 'trial-outcomes.json', dict(groups=groups, native_review='pending', bulk_authorized=False,
        pause_recommendations=['Inspect every language/family and rejected/error samples before any expansion; no automatic bulk continuation.']))
