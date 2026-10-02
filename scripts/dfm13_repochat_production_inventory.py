"""CPU-only source triage and public Git metadata inventory; never admission."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import re
import urllib.error
import urllib.request

from scripts import dfm13_repochat_calibration as b

SOURCE = Path('data/downloads/arena_review/repochat-arena-preference-4k/repochat_battles.json')
BASE = Path('data/dfm13')
PRIOR = (
    ('repochat-calibration-100-20261001-v3/selection.json', 'tasks'),
    ('repochat-simple-qa-inventory-20261001/inventory.json', 'candidates'),
    ('repochat-qa-next-20261001-v1/scope-plan.json', 'tasks'),
)
ATTEMPTS = (
    'repochat-calibration-100-20261001-v3/selection.json',
    'repochat-simple-qa-68-20261001-v1/selection.json',
    'repochat-qa-extension-20261001-v1/selection.json',
    'repochat-qa-next-20261001-v1/first/selection.json',
    'repochat-qa-next-20261001-v1/eligible-74/selection.json',
)


def scope(task):
    q = task['query']
    if b.task_exclusion(task):
        return 'safety_or_nonrepository_hold'
    if re.search(r'\b(implement|write|create|convert|refactor|fix|patch|modify|add|migrate|port|generate)\b|\b(change|replace|remove)\s+(?:the|this|a|all)\b', q, re.I):
        return 'construction_or_change_hold'
    if re.search(r'\b(all|every|exhaustive|entire|complete list|vulnerabilit\w*|exploit\w*)\b', q, re.I):
        return 'exhaustiveness_or_security_hold'
    if re.search(r'\b(where|which file|what file|which director\w*|locate|find the file)\b', q, re.I):
        return 'qa_navigation_candidate'
    if re.search(r'\b(explain|describe|summari[sz]e|overview|purpose|what is|what does|what are|how does|how is|why does|which|architecture|difference between)\b', q, re.I):
        return 'qa_source_explanation_candidate'
    if re.search(r'\b(how (?:can|do|to|would|should)|can (?:i|this)|usage|install|configure|run)\b', q, re.I):
        return 'usage_requires_scope_review'
    return 'unclassified_requires_manual_review'


def probe(repo):
    # Data-only public Git advertisement: no clone, hooks, credentials, or archives.
    b.repository('https://github.com/' + repo)
    url = f'https://github.com/{repo}.git/info/refs?service=git-upload-pack'
    result = {'repository': repo, 'url': url, 'checked_at': datetime.now(timezone.utc).isoformat()}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), b.NoRedirect())
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'DFM13-RepoChat-inventory'})
        with opener.open(req, timeout=20) as response:
            data = response.read(8_000_001)
            result['http_status'] = response.status
        if len(data) > 8_000_000:
            raise ValueError('advertisement_size_limit')
        head = re.search(rb'([a-f0-9]{40}) HEAD\x00', data)
        result.update(status='public_head_available' if head else 'head_unresolved',
                      commit=head[1].decode() if head else None, refs_sha256=b.sha(data))
    except urllib.error.HTTPError as exc:
        result.update(status='unavailable_at_probe' if exc.code in (401, 404) else 'probe_infrastructure_unknown', http_status=exc.code, error=str(exc))
    except Exception as exc:
        result.update(status='probe_infrastructure_unknown', error=f'{type(exc).__name__}: {exc}')
    return result


def prepare(root):
    rows = b.load(SOURCE)
    _, selection = b.select(rows, 1)
    tasks, _ = b.select(rows, selection['eligible'])
    prior, pins = set(), {}
    for relative, key in PRIOR:
        path = BASE / relative
        prior.update(t['id'] for t in b.load(path)[key])
        pins[str(path)] = b.file_sha(path)
    attempted = set()
    for relative in ATTEMPTS:
        path = BASE / relative
        if path.exists():
            attempted.update(t['id'] for t in b.load(path)['tasks'])
            pins[str(path)] = b.file_sha(path)
    queries = Counter(' '.join(t['query'].split()).casefold() for t in tasks)
    inventory = []
    for t in tasks:
        inventory.append(dict(t, scope=scope(t), previously_inventoried=t['id'] in prior,
                              previously_selected_for_attempt=t['id'] in attempted,
                              cross_repository_query_multiplicity=queries[' '.join(t['query'].split()).casefold()]))
    result = {'source': str(SOURCE), 'source_sha256': b.file_sha(SOURCE), 'implementation_sha256': b.file_sha(__file__),
              'pins': pins, 'raw_rows': len(rows), 'source_selection': selection,
              'source_eligible_duplicate_rows': len(rows) - sum(selection['excluded'].values()) - len(tasks),
              'prior_inventory_unique': len(prior), 'prior_selected_unique': len(attempted),
              'remaining': sum(not t['previously_inventoried'] for t in inventory),
              'remaining_scope_counts': dict(Counter(t['scope'] for t in inventory if not t['previously_inventoried'])),
              'tasks': inventory, 'admission': False, 'gpu_launch_authorized': False,
              'qualification': 'Lexical triage, not semantic eligibility. Unclassified/non-English prompts retained for manual review. Availability is not a license or quality clearance.'}
    b.save(root / 'inventory.json', result)
    return result


def run(root, workers=8):
    if not 1 <= workers <= 8:
        raise ValueError('workers must be 1..8')
    root.mkdir(parents=True, exist_ok=True)
    if (root / 'inventory.json').exists():
        inventory = b.load(root / 'inventory.json')
        if inventory['source_sha256'] != b.file_sha(SOURCE) or inventory['implementation_sha256'] != b.file_sha(__file__):
            raise ValueError('inventory pin drift')
        for path, digest in inventory['pins'].items():
            if b.file_sha(path) != digest:
                raise ValueError('prior selection pin drift')
    else:
        inventory = prepare(root)
    remaining = [t for t in inventory['tasks'] if not t['previously_inventoried']]
    repos = sorted({t['repository'] for t in remaining})
    availability = {}
    for repo in repos:
        path = root / 'availability' / (b.sha(repo.lower().encode()) + '.json')
        if path.exists():
            availability[repo] = b.load(path)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(probe, repo): repo for repo in repos if repo not in availability}
        for future in as_completed(futures):
            repo = futures[future]
            availability[repo] = future.result()
            b.save(root / 'availability' / (b.sha(repo.lower().encode()) + '.json'), availability[repo])
            b.save(root / 'progress.json', {'completed_repositories': len(availability), 'total_repositories': len(repos), 'admission': False})
    candidates = [t for t in remaining if t['scope'].startswith('qa_')]
    ready = [t for t in candidates if availability[t['repository']]['status'] == 'public_head_available']
    summary = {k: inventory[k] for k in ('raw_rows', 'source_selection', 'source_eligible_duplicate_rows', 'prior_inventory_unique', 'prior_selected_unique', 'remaining', 'remaining_scope_counts')}
    summary.update(unique_remaining_repositories=len(repos), repository_availability=dict(Counter(v['status'] for v in availability.values())),
                   qa_candidates=len(candidates), qa_public_head_candidates=len(ready), qa_public_repositories=len({t['repository'].lower() for t in ready}),
                   qa_query_only_unique=len({' '.join(t['query'].split()).casefold() for t in ready}),
                   scope_availability=dict(Counter(t['scope'] + '/' + availability[t['repository']]['status'] for t in remaining)),
                   inventory_sha256=b.file_sha(root / 'inventory.json'), admission=False,
                   accepted_estimate=None, qualification='Candidate capacity only; no defensible accepted-yield estimate from exposed calibration controls or biased manual samples.')
    b.save(root / 'availability.json', availability)
    summary['availability_sha256'] = b.file_sha(root / 'availability.json')
    b.save(root / 'summary.json', summary)
    print(summary, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    run(args.root, args.workers)
