"""Blind stratified packets and conservative distinct-candidate accounting."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import sqlite3

from scripts import dfm13_search_budgeted_remaining as campaign
from scripts import dfm13_search_manual_packet as packets

base = campaign.base
read = campaign.read
ROOT = Path('data/dfm13/search-postbatch-accounting-20261001')
SEED = 2026100148
STRATA = {
    'high_stakes': ['3812a931', '3e6744b7', 'ceffc54d', 'd331c427', 'a9f75ccd'],
    'temporal_comparison': ['42c1b060', '454d90e0', '70d1096d', 'd8174c0d', 'ee694ce0'],
    'technical': ['42c53538', '56c21202', 'deb701de', 'e5913568', 'f9669093'],
    'cultural_other': ['461d422e', '4f8af9d1', '5b8040e4', 'c95778af', 'd64649f4'],
}
REPORTS = [Path('docs/reports') / name for name in (
    'dfm13_search_cpu_corrections_v3_assessment_20261001.json',
    'dfm13_search_budgeted_pilot8_manual_assessment_20261001.json',
    'dfm13_search_budgeted_batch1_v2_manual_assessment_20261001.json',
    'dfm13_search_remaining48_keeps8_manual_assessment_20261001.json',
    'dfm13_search_asof_repair3_hold_20261001.json',
    'dfm13_search_asof_and_blind8_manual_assessment_20261001.json',
    'dfm13_search_fresh_nonheld_blind8_manual_assessment_20261001.json',
    'dfm13_search_targeted16_completion_20261001.json',
    'dfm13_search_targeted16_keeps_review_20261001.json')]
SUPPORTED_ASSESSMENTS = {
    'broadly_supported', 'useful_no_material_issue_identified',
    'prior_localized_attribution_issue_resolved', 'useful_supported_core',
    'useful_honest_evidence_limitation',
    'prior_scope_issue_resolved_useful_bounded_answer',
    'prior_date_leakage_issue_resolved_useful_answer',
    'useful_supported_identification',
}


def receipt_rows(receipt):
    return [row for key in ('cases', 'pilot', 'v4', 'rows', 'blind_packet', 'repairs')
            for row in receipt.get(key, [])]


def collect_holds():
    holds = list(read(campaign.pilot.contract.ROOT / 'holds.json')['holds'])
    supported = []
    for path in REPORTS:
        receipt = read(path)
        for row in receipt_rows(receipt):
            candidate = row.get('candidate', {})
            sha = candidate.get('sha256') if isinstance(candidate, dict) else None
            sha = sha or row.get('candidate_sha256')
            if not sha:
                pin = next((p for p in row.get('pins', []) if p['path'].endswith('/candidate.json')), None)
                sha = pin['sha256'] if pin else None
            if not sha:
                continue
            result = dict(id=row['id'], candidate_sha256=sha, assessment=row.get('assessment'),
                          receipt=str(path), receipt_sha256=base.file_hash(path))
            if row.get('assessment') in SUPPORTED_ASSESSMENTS:
                supported.append(result)
            else:
                holds.append(result)
    return holds, supported


def held(key, sha, content_sha, holds):
    if key[:8] in campaign.pilot.previous.inventory.HOLDS:
        return True
    return any(h.get('candidate_sha256') == sha or h.get('candidate_content_sha256') == content_sha for h in holds)


def stratified(rows):
    by_prefix = {row['id'][:8]: row for row in rows}
    rng = random.Random(SEED)
    chosen = []
    for group, prefixes in STRATA.items():
        available = sorted(p for p in prefixes if p in by_prefix)
        if len(available) < 2:
            raise ValueError('insufficient nonheld candidates in stratum')
        chosen.extend((group, by_prefix[p]) for p in rng.sample(available, 2))
    return chosen


def main(inventory_only=False):
    if (ROOT / 'inventory.json').exists():
        raise ValueError('new immutable accounting root required')
    holds, supported = collect_holds()
    supported_hashes = {x['candidate_sha256'] for x in supported}
    jobs = {j['id']: j for j in read(campaign.ROOT / 'jobs.json')}
    eligible = []
    diagnostics = []
    for path in sorted((campaign.ROOT / 'records').glob('*/outcome.json')):
        outcome = read(path)
        if outcome.get('verdict') == 'keep':
            candidate_path = path.parent / 'candidate.json'
            candidate = read(candidate_path)
            if not held(path.parent.name, base.file_hash(candidate_path), base.digest(candidate), holds):
                eligible.append(dict(id=path.parent.name, candidate=candidate_path))
        if outcome['status'] == 'error':
            entry = dict(id=path.parent.name, outcome=outcome, stages=[])
            for response in sorted(path.parent.glob('*/*response.json')):
                raw = read(response)
                value = json.loads(raw['body'])
                choice = value['choices'][0]
                content = choice['message'].get('content')
                entry['stages'].append(dict(path=str(response), sha256=base.file_hash(response),
                    finish_reason=choice['finish_reason'], stop_reason=choice.get('stop_reason'),
                    usage=value.get('usage'), content_null=content is None,
                    trailing_whitespace=len(content)-len(content.rstrip()) if isinstance(content, str) else 0))
            diagnostics.append(entry)
    cases = []; private_selection = []
    for group, row in ([] if inventory_only else stratified(eligible)):
        candidate_path = row['candidate']
        candidate = read(candidate_path)
        value = packets.packet(candidate, jobs[row['id']]['sample'])
        value.update(source_sha256=base.file_hash(candidate_path), source_candidate=str(candidate_path))
        folder = ROOT / 'blind8' / row['id']
        base.atomic(folder / 'packet.json', value)
        cases.append(dict(id=row['id'], packet=str(folder / 'packet.json'),
            packet_sha256=base.file_hash(folder / 'packet.json'), candidate_sha256=base.file_hash(candidate_path)))
        private_selection.append(dict(id=row['id'], stratum=group))
    if not inventory_only:
        base.atomic(ROOT / 'blind8/queue.json', dict(cases=cases, admission_authorized=False,
            instructions='Review task fulfillment, exact delivered evidence, historical dates, variants, citations and completeness. No model labels supplied.'))
        base.atomic(ROOT / 'selection-private.json', dict(seed=SEED, population=len(eligible),
            rule='Two uniformly sampled without replacement from each of four prespecified topic strata of automated keeps.',
            strata=STRATA, selected=private_selection, not_a_random_sample_of_all_100=True))
    base.atomic(ROOT / 'error-diagnostics.json', diagnostics)
    samples = read(Path('data/dfm13/search-calibration-100-20261001-v9-cited/samples.json'))
    rows = {s['id']: dict(id=s['id'], versions=[]) for s in samples}
    paths = list(Path('data/dfm13').glob('search*/records/*/candidate.json'))
    paths += list(Path('data/dfm13').glob('search*/generation/records/*/candidate.json'))
    paths += list(Path('data/dfm13').glob('search-heldout-cpu-corrections*/*/candidate.json'))
    latest_source = defaultdict(list)
    held_training = set()
    for path in sorted(set(paths)):
        candidate = read(path)
        key = candidate.get('id')
        if key not in rows:
            continue
        sha = base.file_hash(path)
        content_sha = base.digest(candidate)
        training_sha = base.digest(dict(messages=candidate['messages'], tools=candidate['tools']))
        if held(key, sha, content_sha, holds):
            held_training.add(training_sha)
        outcome_path = path.parent / 'outcome.json'
        outcome = read(outcome_path) if outcome_path.exists() else {}
        rendering_path = path.parent / 'student-render.json'
        if not rendering_path.exists():
            rendering_path = path.parent / 'render.json'
        rendering = read(rendering_path) if rendering_path.exists() else []
        fits = isinstance(rendering, list) and bool(rendering) and all(
            isinstance(x, dict) and x.get('fits_student_context') is True for x in rendering)
        entry = dict(candidate=str(path), candidate_sha256=sha, content_sha256=content_sha,
            training_sha256=training_sha,
            exact_hold=held(key, sha, content_sha, holds), student_fit_verified=fits,
            automated_verdict=outcome.get('verdict'), manual_supported=sha in supported_hashes,
            complete_final=bool(candidate.get('messages')) and candidate['messages'][-1].get('role') == 'assistant')
        rows[key]['versions'].append(entry)
        if outcome.get('verdict') in ('reject','needs_verification'):
            latest_source[content_sha].append(dict(outcome=str(outcome_path), sha256=base.file_hash(outcome_path)))
    for row in rows.values():
        for version in row['versions']:
            if version['training_sha256'] in held_training:
                version['exact_hold'] = True
            version['negative_same_content_reviews'] = latest_source[version['content_sha256']]
        usable = [v for v in row['versions'] if v['student_fit_verified'] and not v['exact_hold']
                  and not v['negative_same_content_reviews'] and v['complete_final']]
        row['manual_useful_candidate'] = any(v['manual_supported'] for v in usable)
        row['automated_keep_candidate'] = any(v['automated_verdict']=='keep' for v in usable)
        row['admitted'] = False
    db = sqlite3.connect('file:' + str(base.CAMPAIGN / 'cache.sqlite') + '?mode=ro', uri=True)
    paid = dict(db.execute('SELECT status,count(*) FROM searches GROUP BY status'))
    cache_owners = db.execute('SELECT count(DISTINCT owner) FROM searches WHERE status="done"').fetchone()[0]
    db.close()
    summary = dict(original_tasks=len(rows), distinct_with_saved_candidates=sum(bool(r['versions']) for r in rows.values()),
        distinct_manual_useful_context_fit_nonheld=sum(r['manual_useful_candidate'] for r in rows.values()),
        distinct_automated_keep_context_fit_nonheld=sum(r['automated_keep_candidate'] for r in rows.values()),
        union_candidate_pool=sum(r['manual_useful_candidate'] or r['automated_keep_candidate'] for r in rows.values()),
        admitted=0, cached_successful_owners=cache_owners, paid_reservations=sum(paid.values()),
        paid_calls=0, note='Distinct IDs, not sum of overlapping versions. Automated keeps are not verified useful trajectories. Manual agent support is not human gold. Final answer only is supervised; cached native tool history is retained.')
    base.atomic(ROOT / 'inventory.json', dict(summary=summary, rows=list(rows.values()),
        holds=holds, supported_receipts=supported, admission_authorized=False))
    print(json.dumps(dict(summary=summary, blind_queue=None if inventory_only else str(ROOT / 'blind8/queue.json'))))


if __name__ == '__main__':
    main()
