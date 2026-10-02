"""Manually scoped unused QA cohort with a mandatory human-assessed first wave."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
from pathlib import Path
from types import SimpleNamespace
from scripts import dfm13_repochat_simple_qa as previous

b = previous.b
ROOT = Path('data/dfm13/repochat-qa-next-20261001-v1')
SOURCE = Path('data/downloads/arena_review/repochat-arena-preference-4k/repochat_battles.json')
PRIOR = [Path('data/dfm13/repochat-calibration-100-20261001-v3/selection.json'), previous.INVENTORY]
# Whole original prompts reviewed in deterministic unused-source order.
# Descriptive source reading only; no edits, external rankings or exhaustive audit.
INDICES = (10,19,20,25,26,45,50,60,66,95,116,117,134,135,150,169,175,187,
           189,224,228,258,265,276,285,286,296,297,317,332,355,379,395,
           401,404,405,418,430,450,456,462,464,469,489,493,497,508,517,
           522,525,536,538,539,545,547,553,567,568,579,586,591,600,605,
           617,622,629,633,635,640,645,647,669,673,691,698,712,722,726,
           731,735,747,752,756,770,775,791,803,821,830,836,850,859,873,
           876,882,890,891,898,928,938)


def candidates():
    rows = b.load(SOURCE)
    _, inventory = b.select(rows, 1)
    tasks, _ = b.select(rows, inventory['eligible'])
    used = {t['id'] for path in PRIOR for t in
            (b.load(path).get('tasks') or b.load(path).get('candidates'))}
    unused = [t for t in tasks if t['id'] not in used and not b.task_exclusion(t)]
    selected = [unused[i] for i in INDICES]
    if len(selected) != len({t['id'] for t in selected}) or len(selected) > 100:
        raise ValueError('scope selection contract')
    return selected, len(unused)


def prepare():
    tasks, available = candidates()
    plan = {'tasks': tasks, 'unused_pool': available, 'source_sha256': b.file_sha(SOURCE),
            'prior_pins': {str(p): b.file_sha(p) for p in PRIOR},
            'scope': 'manually reviewed descriptive source QA; original prompts unchanged',
            'first_wave': 8, 'manual_gate_required': True, 'admission': False}
    path = ROOT/'scope-plan.json'
    if path.exists() and b.load(path) != plan:
        raise ValueError('scope drift')
    b.save(path, plan)
    statepath = ROOT/'preparation.json'
    state = b.load(statepath) if statepath.exists() else {'snapshots': {}, 'failures': {}}
    repos = list(dict.fromkeys(t['repository'] for t in tasks))
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = {pool.submit(b.snapshot, repo, ROOT/'repositories'): repo for repo in repos
                if repo not in state['snapshots'] and repo not in state['failures']}
        for future in as_completed(jobs):
            repo = jobs[future]
            try:
                future.result()
                state['snapshots'][repo] = b.file_sha(ROOT/'repositories'/repo.replace('/', '--')/'snapshot.json')
                print('prepared '+repo, flush=True)
            except Exception as exc:
                state['failures'][repo] = str(exc)
                print('blocked '+repo+': '+str(exc), flush=True)
            b.save(statepath, state)
    selected = [t for t in tasks if t['repository'] in state['snapshots']]
    b.save(ROOT/'selection.json', {'tasks': selected, 'admission': False})
    files = [__file__, SOURCE, *PRIOR, previous.__file__, b.__file__,
             previous.generation.__file__, previous.audit.__file__,
             previous.audit.probe.__file__, previous.audit.probe.r.__file__]
    pins = {str(Path(p).resolve()): b.file_sha(p) for p in files}
    pins.update({str((ROOT/'repositories'/repo.replace('/', '--')/'snapshot.json').resolve()): digest
                 for repo, digest in state['snapshots'].items()})
    b.save(ROOT/'ready.json', {'baseline': str(ROOT.resolve()), 'pins': pins,
           'selection_sha256': b.file_sha(ROOT/'selection.json'), 'admission': False})


async def run(wave):
    ready = b.load(ROOT/'ready.json')
    for path, digest in ready['pins'].items():
        if b.file_sha(path) != digest:
            raise ValueError('pin drift: '+path)
    if b.file_sha(ROOT/'selection.json') != ready['selection_sha256']:
        raise ValueError('selection drift')
    tasks = b.load(ROOT/'selection.json')['tasks']
    if wave == 'rest':
        gate = b.load(ROOT/'manual-gate.json')
        if gate.get('release_remaining') is not True or gate.get('ready_sha256') != b.file_sha(ROOT/'ready.json'):
            raise ValueError('manual gate not released')
        for path, digest in gate['evidence_pins'].items():
            if b.file_sha(path) != digest:
                raise ValueError('manual gate evidence drift')
    selected = tasks[:8] if wave == 'first' else tasks[8:]
    root = ROOT/wave
    selection = {'tasks': selected, 'admission': False}
    if (root/'selection.json').exists() and b.load(root/'selection.json') != selection:
        raise ValueError('wave selection drift')
    b.save(root/'selection.json', selection)
    b.save(root/'ready.json', {**ready, 'selection_sha256': b.file_sha(root/'selection.json')})
    b.save(root/'scope-readiness.json', previous.controls_ready())
    previous.generation.CONTROLS = ()
    await previous.generation.run(SimpleNamespace(root=root, authorized=True,
        endpoints=','.join(f'http://localhost:{p}/v1' for p in range(8800,8808)),
        model='dfm13-gemma4', per_endpoint=8, max_turns=16, max_tokens=8192))
    await previous.audit.run(SimpleNamespace(source=root, root=root/'independent-review', ids=None, thinking=True))
    b.save(root/'completion.json', {'admission': False, 'manual_assessment_required': True,
           'review_sha256': b.file_sha(root/'independent-review/summary.json')})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['prepare', 'first', 'rest'])
    args = p.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT/'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prepare() if args.mode == 'prepare' else asyncio.run(run(args.mode))
