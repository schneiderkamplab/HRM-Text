"""Bounded report-directed cache-only repairs and a blind manual-review packet."""
import argparse
import asyncio
from collections import Counter
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3

import aiohttp

from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_followup as old
from scripts import dfm13_search_followup_v2 as replay
from scripts import dfm13_search_critic_free_control as criticfree
from scripts import dfm13_search_json_mode_probe as probe
from scripts import dfm13_search_adjudication_retry as bounded
from scripts import dfm13_search_campaign_ledger as inventory

SOURCE = Path('data/dfm13/search-reviewer-v3-20261001')
REPORT = Path('docs/reports/dfm13_search_trajectory_assessment_20261001.md')
LEDGER = Path('data/dfm13/search-campaign-ledger-20261001-post-supplement/ledger.json')
ROOT = Path('data/dfm13/search-cached-defect-repairs-20261001')
HINTS = {
    '0cfb74ac': 'Original date March 27, 2025: remove completed-season title, final placement and final scoring totals presented as already known. Use only clearly dated pre-question evidence for contemporary claims.',
    '12490c96': 'LinkedIn navigation/related-content text does not establish AI spending or automation as the cause. Remove that unsupported bullet; distinguish documented layoffs from speculation about motives.',
    '25bdd9ac': 'The task asks to SHOW logos beside URLs, not just link to logo pages. Use only image URLs literally supplied in cached body text with identifiable company context. Unsupported entries must be removed. Later image URL dates alone do not prove fabrication; do not assert historical availability without support.',
    '42c1b060': 'Original date April 15, 2025: do not present November 2025 or July 2026 tariff events as already current. A later source may document earlier history, but each as-of claim requires explicit date support.',
    '4f8af9d1': 'User asks for ALL new mythics. Product listings and repeated image alt text do not prove rarity; require explicit rarity attached to the named card. Do not mention a previous answer absent from the conversation. A partial list is not a verified complete answer.',
    'b528d937': 'Each recommended restaurant must have explicit evidence of a price below TWD200, prior inclusion years, and absence from the 2024 list. Bib Gourmand status alone does not prove price under TWD200. Do not retain uncertain qualifying entries.',
    'ceffc54d': 'Research question is anchored April 1, 2025. Remove compounds, mechanisms and numerical efficacy assertions absent from reliable delivered research evidence. Commercial claims are not verified clinical studies. Do not infer absence of research from a different approved indication.',
    'e19e0b36': 'Do not cite an unseen rctest page or claim exhaustive absence of Bluetooth-specific regulations from commercial summaries. Distinguish federal legal instruments from certification commentary, and exact scope from extrapolation. Only cite observed source pages.',
}
HELDOUT = ('118fd78c', '918bee08', 'bcb18033', 'e5913568',
           '81484873', '889a9213', 'd4fc6d00', 'ea1b1cdd')


def read(path):
    return json.loads(path.read_text())


def native_search(candidate, query):
    for index, message in enumerate(candidate['messages']):
        calls = message.get('tool_calls') or []
        if len(calls) != 1 or calls[0]['function']['name'] != 'search':
            continue
        args = calls[0]['function']['arguments']
        if isinstance(args, str):
            args = base.strict_json(args)
        if args == {'query': query}:
            return index
    raise ValueError('cached query has no matching native search call')


def repaired_candidate(job, answer):
    candidate = deepcopy(job['candidate'])
    index = native_search(candidate, job['query'])
    history = candidate['messages'][:index + 1]
    history.append(dict(role='tool', name='search',
        tool_call_id=history[-1]['tool_calls'][0]['id'], content=json.dumps(dict(
            provider='jina_full_cache_replay', query=job['query'],
            raw_cache_sha256=job['cache_sha256'], paid_calls=0,
            results=list(job['pages'].values()),
            note='New excerpts of a saved real response, not new retrieval.'), ensure_ascii=False)))
    history.append(dict(role='assistant', content=answer))
    candidate.update(messages=history, target_message_indices=[len(history) - 1],
        admission_authorized=False, repair_mode='report_directed_cached_repair',
        evidence_replay=dict(raw_cache_sha256=job['cache_sha256'], query=job['query']),
        student_window_validation='pending; not admitted',
        correction_provenance=dict(report=str(REPORT), report_sha256=base.file_hash(REPORT),
                                   generation_only_hint=job['hint']))
    candidate.pop('teacher_rendered_tokens', None)
    candidate['citation_validation_errors'] = []
    return candidate


def validate_repair(value):
    if (not isinstance(value, dict) or set(value) != set(old.REPAIR['required'])
            or type(value['evidence_sufficient']) is not bool
            or not all(isinstance(value[k], str) and value[k].strip() for k in ('answer', 'reason'))):
        raise ValueError('invalid repair contract')
    return value


def gated_outcome(key, reviewer_verdict, evidence_sufficient):
    hold = inventory.HOLDS.get(key[:8])
    return dict(verdict='needs_verification' if hold or not evidence_sufficient else reviewer_verdict,
                reviewer_verdict=reviewer_verdict, independent_hold=hold,
                essential_evidence_sufficient=evidence_sufficient, admission_authorized=False)


def prepare(root):
    if root.exists():
        raise ValueError('new root required')
    jobs = read(SOURCE / 'jobs.json')
    manifest = read(SOURCE / 'manifest.json')
    pins = {str(p.resolve()): base.file_hash(p) for p in
            (SOURCE / 'jobs.json', SOURCE / 'manifest.json', REPORT, LEDGER)}
    db = sqlite3.connect('file:' + str(base.CAMPAIGN / 'cache.sqlite') + '?mode=ro', uri=True)
    selected = []
    for job in jobs:
        if job['id'][:8] not in HINTS:
            continue
        cached = db.execute('SELECT query,raw FROM searches WHERE owner=? AND status=? ORDER BY key',
                            (job['id'], 'done')).fetchall()
        match = None
        for query, raw in cached:
            try:
                native_search(job['candidate'], query)
                match = query, raw
                break
            except ValueError:
                pass
        if match is None:
            raise ValueError('missing matching cached search: ' + job['id'])
        query, raw = match
        payload = json.loads(raw)
        hint = HINTS[job['id'][:8]]
        pages = replay.excerpts(payload, query + '\n' + job['sample']['prompt'] + '\n' + hint, max_chunks=8)
        if not pages:
            raise ValueError('empty cached evidence: ' + job['id'])
        path = root / 'cache-snapshots' / (job['id'] + '.json')
        base.atomic(path, payload)
        pins[str(path.resolve())] = base.file_hash(path)
        selected.append(dict(job, query=query, hint=hint, pages=pages,
                             cache_sha256=hashlib.sha256(raw).hexdigest(), cache_snapshot=str(path)))
    paid = dict(db.execute('SELECT status,count(*) FROM searches GROUP BY status'))
    db.close()
    if len(selected) != 8:
        raise ValueError('expected exactly eight repair jobs')
    excluded = set()
    for name in ('search-critique-adjudication-20261001', 'search-targeted-repair-v4-20261001', 'search-supplement9-20261001'):
        path = Path('data/dfm13') / name / 'jobs.json'
        excluded.update(j['id'] for j in read(path))
        pins[str(path.resolve())] = base.file_hash(path)
    manual = []
    for job in jobs:
        if job['id'][:8] not in HELDOUT:
            continue
        if job['id'] in excluded or job['id'][:8] in HINTS:
            raise ValueError('manual heldout overlaps recent controls/repairs')
        folder = root / 'manual-heldout' / job['id']
        # Reviewer dispositions are deliberately absent from this blind packet.
        packet = dict(id=job['id'], sample=job['sample'], answer=job['answer'],
                      candidate=job['candidate'], pages=job['pages'],
                      origin=str(SOURCE / 'jobs.json'), admission_authorized=False)
        base.atomic(folder / 'packet.json', packet)
        pins[str((folder / 'packet.json').resolve())] = base.file_hash(folder / 'packet.json')
        manual.append(dict(id=job['id'], packet=str(folder / 'packet.json'),
                           review_status='pending_independent_manual_assessment'))
    if len(manual) != 8:
        raise ValueError('expected eight heldout cases')
    base.atomic(root / 'manual-heldout' / 'queue.json', dict(cases=manual,
        scope='Fresh to recent repair/control experiments, NOT unseen by all earlier reviewers.',
        instructions='Assess original task/date, all substantive claims and task completion against delivered evidence. Navigation is not claim support. Record exact defects and unresolved evidence; no model verdict provided.',
        admission_authorized=False))
    base.atomic(root / 'jobs.json', selected)
    paths = [Path(__file__), Path(base.__file__), Path(old.__file__), Path(replay.__file__),
             Path(criticfree.__file__), Path(probe.__file__), Path(bounded.__file__), Path(inventory.__file__),
             root / 'jobs.json', root / 'manual-heldout' / 'queue.json']
    pins.update({str(p.resolve()): base.file_hash(p) for p in paths})
    base.atomic(root / 'manifest.json', dict(
        **{k: manifest[k] for k in ('tokenizer_dir', 'context_tokens', 'model', 'endpoints')},
        pins=pins, total=8, heldout=8, paid_calls_allowed=0, paid_snapshot=paid,
        max_attempts=1, admission_authorized=False, independent_hold_policy=inventory.HOLDS))
    print(json.dumps(dict(repair_jobs=8, manual_heldout=8, paid_reservations=sum(paid.values()))))


def verify(root):
    manifest = read(root / 'manifest.json')
    for path, expected in manifest['pins'].items():
        if base.file_hash(Path(path)) != expected:
            raise ValueError('pin mismatch: ' + path)
    return manifest


async def execute(job, model, folder):
    request = [dict(role='system', content=replay.RUBRIC +
        'Repair the supplied answer once using only delivered cached pages. Address the agent-identified defect;'
        ' that hint is not independent evidence. Use the original language. Do not repeat unsupported navigation,'
        ' image-alt or related-link text as article claims. Later sources are not automatically false; do not'
        ' use their later facts as current at the original timestamp. Use exact observed URLs and cite supporting'
        ' passages. Do not invent missing claims or fill an exhaustive list from memory. If essential requested'
        ' facts cannot be established, provide a useful honest partial answer but set evidence_sufficient=false.'
        ' No new search is available. Return exactly a compact JSON object with answer (string),'
        ' evidence_sufficient (boolean), reason (string). Under 600 words; no extra keys.'),
        dict(role='user', content=json.dumps(dict(sample=job['sample'], previous_answer=job['answer'],
             pages=job['pages'], generation_only_repair_hint=job['hint'], retrieval_date='2026-10-01'), ensure_ascii=False))]
    model.session.folder = folder / 'generation'
    repair = validate_repair(await model.ask(request, old.REPAIR, None, folder / 'generation', 'repair'))
    base.atomic(folder / 'repair.json', repair)
    candidate = repaired_candidate(job, repair['answer'])
    tokens = model.tokenizer.apply_chat_template(candidate['messages'], tools=candidate['tools'],
                    tokenize=True, add_generation_prompt=False, enable_thinking=False)
    if len(tokens) > model.manifest['context_tokens']:
        raise ValueError('full repaired trajectory exceeds context; no truncation')
    candidate['teacher_rendered_tokens'] = len(tokens)
    base.atomic(folder / 'candidate.json', candidate)
    payload = dict(requirements=dict(original_user_prompt=job['sample']['prompt'],
        original_timestamp=job['sample']['original_timestamp'], retrieval_date='2026-10-01',
        historical_policy=job['sample'].get('date_policy', 'Preserve original date')),
        answer=repair['answer'], pages=job['pages'], verified_checks=[])
    model.session.folder = folder / 'audit'
    raw = await model.ask(criticfree.messages(payload), bounded.SCHEMA, None, folder / 'audit', 'review')
    base.atomic(folder / 'raw-review.json', raw)
    try:
        review = bounded.derive(raw, job['pages'], repair['answer'])
    except ValueError as error:
        review = dict(verdict='needs_verification', reason=str(error))
    base.atomic(folder / 'review.json', review)
    return dict(status='reviewed', candidate_sha256=base.file_hash(folder / 'candidate.json'),
                **gated_outcome(job['id'], review['verdict'], repair['evidence_sufficient']))


def finalize(root):
    ledger = read(LEDGER)
    for row in ledger['rows']:
        hold = inventory.HOLDS.get(row['id'][:8])
        if hold:
            row.update(independent_hold=hold, selected=None, disposition='independent_hold')
        path = root / 'records' / row['id'] / 'outcome.json'
        if not path.exists():
            continue
        outcome = read(path)
        row['history'].append(dict(stage=root.name, outcome=str(path), outcome_sha256=base.file_hash(path),
                                   status=outcome['status'], verdict=outcome.get('verdict')))
        # Prior candidates with report-identified defects cannot survive as a fallback keep.
        row['selected'] = None
        row['disposition'] = 'repaired_candidate_pending_manual_review' if outcome.get('verdict') == 'keep' and not hold else 'no_verified_candidate_selected'
        row['repair_outcome'] = str(path)
        if hold:
            row['disposition'] = 'independent_hold'
    ledger.update(at=base.now(), counts=dict(Counter(r['disposition'] for r in ledger['rows'])),
                  admission_authorized=False, production_ready=False, predecessor=str(LEDGER),
                  predecessor_sha256=base.file_hash(LEDGER))
    base.atomic(root / 'campaign-ledger.json', ledger)


async def run(args):
    root = args.root
    manifest = verify(root)
    replay.worker_slots(manifest['endpoints'], args.concurrency_per_server)
    os.environ.pop('JINA_API_KEY', None)
    queue = asyncio.Queue()
    for job in read(root / 'jobs.json'):
        folder = root / 'records' / job['id']
        if (folder / 'outcome.json').exists():
            continue
        if (folder / 'started.json').exists():
            base.atomic(folder / 'outcome.json', dict(status='interrupted', admission_authorized=False))
            continue
        queue.put_nowait(job)
    base.atomic(root / 'runtime.json', dict(pid=os.getpid(), queued=queue.qsize(),
        concurrency_per_endpoint=args.concurrency_per_server, paid_calls=0, max_attempts=1))
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(manifest['tokenizer_dir'], local_files_only=True)
    async with aiohttp.ClientSession(trust_env=False) as session:
        async def worker(endpoint):
            while not queue.empty():
                job = queue.get_nowait()
                folder = root / 'records' / job['id']
                base.atomic(folder / 'started.json', dict(at=base.now(), endpoint=endpoint))
                model = base.Model(probe.ModeSession(session, 'json_object'), tokenizer, manifest, endpoint, args.timeout)
                try:
                    outcome = await execute(job, model, folder)
                except Exception as error:
                    outcome = dict(status='error', error=str(error), admission_authorized=False)
                base.atomic(folder / 'outcome.json', outcome)
                rows = [read(p) for p in (root / 'records').glob('*/outcome.json')]
                base.atomic(root / 'progress.json', dict(terminal=len(rows), total=8,
                    counts=dict(Counter(r.get('verdict', r['status']) for r in rows)), paid_calls=0))
        await asyncio.gather(*(worker(e) for e in replay.worker_slots(manifest['endpoints'], args.concurrency_per_server)))
    finalize(root)
    rows = [read(p) for p in (root / 'records').glob('*/outcome.json')]
    base.atomic(root / 'finished.json', dict(terminal=len(rows), total=8,
        counts=dict(Counter(r.get('verdict', r['status']) for r in rows)),
        paid_calls=0, admission_authorized=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run', 'verify'])
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--concurrency-per-server', type=int, default=8)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.root)
    elif args.command == 'verify':
        verify(args.root)
    else:
        with (args.root / 'run.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            asyncio.run(run(args))


if __name__ == '__main__':
    main()
