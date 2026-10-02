"""One bounded retry of two pilot failures; CPU-only oversize planning."""
import argparse
import asyncio
from copy import deepcopy
import fcntl
import json
from pathlib import Path
import sqlite3
from collections import Counter

from scripts import dfm13_search_budgeted_pilot as pilot

base = pilot.base
read = pilot.previous.read
ROOT = Path('data/dfm13/search-budgeted-retry2-20261001')
PLAN = Path('data/dfm13/search-budgeted-remaining-plan-20261001')
HINTS = {
    '31dbdb34': 'Provide one short proposed coding example, at most 100 words, covering both self-management and self-evaluation. Label the application as an illustrative proposal, not a proven intervention. Finish completely and include one exact supporting URL.',
    'bfd8c382': 'Answer who won in one or two sentences and include an exact supporting source URL from the observations. Do not add unnecessary certification dates or claims not established in the supplied passages.',
}


def request_for_retry(request, prefix):
    result = deepcopy(request)
    result['messages'][0]['content'] += '\nGeneration-only retry instruction: ' + HINTS[prefix]
    result['max_tokens'] = 512
    result['tool_choice'] = 'none'
    return result


class RetrySession:
    def __init__(self, session, folder):
        self.session, self.folder = session, folder

    def post(self, *args, **kwargs):
        kwargs['json'] = request_for_retry(kwargs['json'], self.folder.parent.name[:8])
        base.atomic(self.folder / 'actual-request.json', kwargs['json'])
        return self.session.post(*args, **kwargs)


def prepare():
    if ROOT.exists():
        raise ValueError('new retry root required')
    manifest = deepcopy(pilot.previous.verify(pilot.ROOT))
    jobs = [j for j in read(pilot.ROOT / 'jobs.json') if j['id'][:8] in HINTS]
    if len(jobs) != 2:
        raise ValueError('exactly two original jobs required')
    diagnoses = []
    for job in jobs:
        folder = pilot.ROOT / 'records' / job['id']
        response = read(folder / 'generation' / 'answer-response.json')
        actual = json.loads(response['body'])
        diagnoses.append(dict(id=job['id'], finish_reason=actual['choices'][0]['finish_reason'],
            completion_tokens=actual['usage']['completion_tokens'], previous_outcome=read(folder / 'outcome.json'),
            messages_sha256=base.digest(job['messages']), evidence_sha256=base.file_hash(Path(job['evidence'])),
            instruction=HINTS[job['id'][:8]], max_new_attempts=1))
    base.atomic(ROOT / 'jobs.json', jobs)
    base.atomic(ROOT / 'diagnoses.json', diagnoses)
    for path in (Path(__file__), ROOT / 'jobs.json', ROOT / 'diagnoses.json'):
        manifest['pins'][str(path.resolve())] = base.file_hash(path)
    manifest.update(total=2, parent=str(pilot.ROOT), max_attempts=1, paid_calls_allowed=0)
    base.atomic(ROOT / 'manifest.json', manifest)


def plan():
    if PLAN.exists():
        raise ValueError('new plan root required')
    inventory_path = pilot.contract.ROOT / 'inventory.json'
    inventory = read(inventory_path)
    db = sqlite3.connect('file:' + str(base.CAMPAIGN / 'cache.sqlite') + '?mode=ro', uri=True)
    rows = []
    for row in inventory['rows']:
        if not any(t['target_kind'] == 'final_answer' and not t['fits_student_context']
                   for t in row.get('targets', [])):
            continue
        candidate = read(Path(row['candidate']))
        matches = []
        for query, raw in db.execute('SELECT query,raw FROM searches WHERE owner=? AND status=?', (row['id'], 'done')):
            try:
                index = pilot.previous.native_search(candidate, query)
            except ValueError:
                continue
            payload = json.loads(raw)
            urls = [p['url'] for p in payload.get('data', []) if isinstance(p.get('url'), str)]
            chunks = pilot.paragraphs(payload, urls)
            matches.append(dict(query=query, call_index=index, paragraphs=len(chunks), urls=urls,
                raw_sha256=pilot.hashlib.sha256(raw).hexdigest()))
        state = ('already_in_pilot' if row['id'][:8] in pilot.PLANS else
                 'cpu_evidence_available_pending_manual_selection' if any(m['paragraphs'] for m in matches)
                 else 'blocked_no_matched_usable_cached_evidence')
        rows.append(dict(id=row['id'], candidate=row['candidate'], candidate_sha256=base.file_hash(Path(row['candidate'])),
            state=state, caches=matches, prior_quality_disposition=row.get('quality_disposition'),
            exact_hash_hold=row.get('exact_hash_hold'), generation_authorized=False,
            required_gates=['manual pilot quality decision', 'task-specific source relevance and historical-date review',
                            'preserve full pre-call history', 'exact student prompt plus answer budget <=4096',
                            'independent answer review; original hard holds remain']))
    paid = sum(n for _, n in db.execute('SELECT status,count(*) FROM searches GROUP BY status'))
    db.close()
    base.atomic(PLAN / 'plan.json', dict(rows=rows, counts=dict(Counter(r['state'] for r in rows)),
        original_oversize_count=len(rows), paid_reservations=paid, paid_calls=0,
        inventory_sha256=base.file_hash(inventory_path), generation_authorized=False,
        note='Mechanical availability is not semantic eligibility. Four later CPU drafts may already replace oversized originals; deduplicate before launch. No launch command or automatic watcher.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run', 'plan'])
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    elif args.command == 'plan':
        plan()
    else:
        with (ROOT / 'run.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            pilot.GenerationSession = RetrySession
            asyncio.run(pilot.run(argparse.Namespace(root=ROOT, concurrency_per_server=1, timeout=600)))
            finished = read(ROOT / 'finished.json')
            base.atomic(ROOT / 'progress.json', dict(terminal=finished['total'], total=2,
                counts=finished['counts'], paid_calls=0))
