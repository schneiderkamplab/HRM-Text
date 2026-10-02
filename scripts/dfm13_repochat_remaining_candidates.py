"""Account for and attempt the remaining original 68 candidates in quarantine."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
from scripts import dfm13_repochat_simple_qa as prior

b, generation, audit = prior.b, prior.generation, prior.audit
ROOT = Path('data/dfm13/repochat-remaining-68-20261001-v1')


def remaining_tasks(candidates, generated_ids, blocked_repos):
    ids = [t['id'] for t in candidates]
    if len(ids) != len(set(ids)) or not set(generated_ids).issubset(ids):
        raise ValueError('candidate identity mismatch')
    return [t for t in candidates if t['id'] not in generated_ids and t['repository'] not in blocked_repos]


def prepare():
    inventory = b.load(prior.INVENTORY)
    original = b.load(prior.ROOT / 'selection.json')['tasks']
    old_prep = b.load(prior.ROOT / 'preparation.json')
    candidates = inventory['candidates']
    tasks = remaining_tasks(candidates, {t['id'] for t in original}, old_prep['failures'])
    if len(candidates) != 68 or len(tasks) != 21:
        raise ValueError('expected frozen 68 candidates and 21 previously held tasks')
    plan = {'inventory_sha256': b.file_sha(prior.INVENTORY), 'original_selection_sha256': b.file_sha(prior.ROOT / 'selection.json'),
            'tasks': tasks, 'original_generated': len(original), 'prior_source_failures': old_prep['failures'],
            'authorization': 'Latest user explicitly requested all eligible 68 attempted.',
            'scope': 'remaining mixed-scope diagnostic attempts; complex outputs remain barred from admission and scale', 'admission': False}
    if (ROOT / 'plan.json').exists() and b.load(ROOT / 'plan.json') != plan:
        raise ValueError('plan drift')
    b.save(ROOT / 'plan.json', plan)
    state = b.load(ROOT / 'preparation.json') if (ROOT / 'preparation.json').exists() else {'failures': {}, 'snapshots': {}}
    failures, snapshots = state['failures'], state['snapshots']
    repository_root = ROOT / 'repositories'
    repository_root.mkdir(parents=True, exist_ok=True)

    def snapshot(repo):
        name = repo.replace('/', '--')
        cached, target = prior.ROOT / 'repositories' / name, repository_root / name
        if (cached / 'snapshot.json').exists() and not target.exists():
            # Atomic copies preserve the original pinned commit without sharing writes.
            with tempfile.TemporaryDirectory(dir=repository_root) as temporary:
                staged = Path(temporary) / name
                shutil.copytree(cached, staged)
                os.replace(staged, target)
        b.snapshot(repo, repository_root)
        return b.file_sha(target / 'snapshot.json')

    repos = list(dict.fromkeys(t['repository'] for t in tasks))
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = {pool.submit(snapshot, repo): repo for repo in repos if repo not in failures}
        for future in as_completed(jobs):
            repo = jobs[future]
            try:
                snapshots[repo] = future.result()
                print('prepared ' + repo, flush=True)
            except Exception as exc:
                failures[repo] = f'{type(exc).__name__}: {exc}'
                print('blocked ' + repo + ': ' + failures[repo], flush=True)
            b.save(ROOT / 'preparation.json', {'snapshots': snapshots, 'failures': failures, 'admission': False})
    selected = [t for t in tasks if t['repository'] in snapshots and t['repository'] not in failures]
    b.save(ROOT / 'selection.json', {'tasks': selected, 'candidate_origin': str(prior.INVENTORY), 'admission': False})
    files = [__file__, prior.__file__, b.__file__, generation.__file__, audit.__file__, audit.probe.__file__, audit.probe.r.__file__, prior.INVENTORY, prior.ROOT / 'selection.json']
    pins = {str(Path(p).resolve()): b.file_sha(p) for p in files}
    pins.update({str((repository_root / repo.replace('/', '--') / 'snapshot.json').resolve()): digest for repo, digest in snapshots.items()})
    b.save(ROOT / 'ready.json', {'baseline': str(ROOT.resolve()), 'pins': pins, 'selection_sha256': b.file_sha(ROOT / 'selection.json'), 'admission': False})


async def run():
    if not b.load(ROOT / 'selection.json')['tasks']:
        raise ValueError('no available tasks')
    generation.CONTROLS = ()
    await generation.run(SimpleNamespace(root=ROOT, authorized=True, endpoints=','.join(f'http://localhost:{p}/v1' for p in range(8800, 8808)), model='dfm13-gemma4', per_endpoint=8, max_turns=16, max_tokens=8192))
    b.save(ROOT / 'generation-stage.json', {'legacy_screen_ignored_for_admission': True, 'summary_sha256': b.file_sha(ROOT / 'summary.json'), 'admission': False})
    await audit.run(SimpleNamespace(source=ROOT, root=ROOT / 'independent-review', ids=None, thinking=True))
    b.save(ROOT / 'completion.json', {'generation_summary_sha256': b.file_sha(ROOT / 'summary.json'), 'review_summary_sha256': b.file_sha(ROOT / 'independent-review' / 'summary.json'), 'complex_scope_not_approved': True, 'admission': False})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['prepare', 'run'])
    p.add_argument('--authorized', action='store_true')
    args = p.parse_args()
    if args.mode == 'run' and not args.authorized:
        p.error('--authorized is required')
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prepare() if args.mode == 'prepare' else asyncio.run(run())
