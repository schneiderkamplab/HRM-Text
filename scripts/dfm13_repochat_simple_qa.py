"""Bounded quarantined QA experiment, gated by scoped reviewer controls."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
from pathlib import Path
from types import SimpleNamespace
from scripts import dfm13_repochat_calibration as b
from scripts import dfm13_repochat_calibration_v3 as generation
from scripts import dfm13_repochat_review_saved as audit

ROOT = Path('data/dfm13/repochat-simple-qa-68-20261001-v1')
INVENTORY = Path('data/dfm13/repochat-simple-qa-inventory-20261001/inventory.json')
CONTROLS = Path('data/dfm13/repochat-simple-qa-controls-20261001')
# Manual whole-prompt scope review; original prompts are never shortened to fit.
EXCLUSIONS = {2, 3, 8, 15, 16, 18, 25, 27, 31, 33, 37, 38, 39, 40, 41, 42, 49, 50, 51, 55, 67}


def controls_ready():
    manifest = b.load(CONTROLS / 'control-manifest.json')
    for path, digest in manifest['source_pins'].items():
        if b.file_sha(path) != digest:
            raise ValueError('control source drift')
    positives = b.load(CONTROLS / 'results' / 'positive-controls.json')
    if not positives['passed']:
        raise ValueError('positive controls failed')
    for key, expected in manifest['expected'].items():
        result = b.load(CONTROLS / 'results' / 'reviews' / key / 'outcome.json')
        if result['status'] != 'reviewed' or result['quality_pass'] != expected:
            raise ValueError('scoped reviewer control failed: ' + key)
    return {'manifest_sha256': b.file_sha(CONTROLS / 'control-manifest.json'),
            'summary_sha256': b.file_sha(CONTROLS / 'results' / 'summary.json'),
            'manual_sample': 'docs/reports/dfm13_repochat_trajectory_assessment_20261001.md',
            'manual_sample_sha256': b.file_sha('docs/reports/dfm13_repochat_trajectory_assessment_20261001.md'),
            'scope': 'non-exhaustive navigation and overview experiment only', 'admission': False}


def prepare():
    inventory = b.load(INVENTORY)
    if inventory['count'] != 68:
        raise ValueError('manual scope review requires original 68-item inventory')
    tasks = [t for i, t in enumerate(inventory['candidates']) if i not in EXCLUSIONS]
    plan = {'inventory_sha256': b.file_sha(INVENTORY), 'tasks': tasks,
            'held_out': [{'id': t['id'], 'reason': 'mixed implementation/API, external comparison/advice, or exhaustive scope'} for i, t in enumerate(inventory['candidates']) if i in EXCLUSIONS], 'admission': False}
    if (ROOT / 'scope-plan.json').exists() and b.load(ROOT / 'scope-plan.json') != plan:
        raise ValueError('scope plan drift')
    b.save(ROOT / 'scope-plan.json', plan)
    failures, snapshots = {}, {}
    repos = list(dict.fromkeys(t['repository'] for t in tasks))
    with ThreadPoolExecutor(max_workers=8) as executor:
        jobs = {executor.submit(b.snapshot, repo, ROOT / 'repositories'): repo for repo in repos}
        for future in as_completed(jobs):
            repo = jobs[future]
            try:
                future.result()
                snapshots[repo] = b.file_sha(ROOT / 'repositories' / repo.replace('/', '--') / 'snapshot.json')
                print('prepared ' + repo, flush=True)
            except Exception as exc:
                failures[repo] = f'{type(exc).__name__}: {exc}'
                print('unavailable ' + repo + ': ' + failures[repo], flush=True)
            b.save(ROOT / 'preparation.json', {'snapshots': snapshots, 'failures': failures, 'admission': False})
    selected = [t for t in tasks if t['repository'] in snapshots]
    b.save(ROOT / 'selection.json', {'tasks': selected, 'candidate_count': 68, 'scope_eligible': len(tasks), 'shortfall_not_resampled': True})
    pins = {str(Path(p).resolve()): b.file_sha(p) for p in [__file__, b.__file__, generation.__file__, audit.__file__, audit.probe.__file__, audit.probe.r.__file__, INVENTORY]}
    for repo, digest in snapshots.items():
        pins[str((ROOT / 'repositories' / repo.replace('/', '--') / 'snapshot.json').resolve())] = digest
    b.save(ROOT / 'ready.json', {'baseline': str(ROOT.resolve()), 'pins': pins, 'selection_sha256': b.file_sha(ROOT / 'selection.json'), 'admission': False})


async def run():
    gate = controls_ready()
    b.save(ROOT / 'scope-readiness.json', gate)
    # Reuse frozen native rollout mechanics; its legacy screen is NOT admission.
    generation.CONTROLS = ()
    args = SimpleNamespace(root=ROOT, authorized=True, endpoints=','.join(f'http://localhost:{p}/v1' for p in range(8800, 8808)), model='dfm13-gemma4', per_endpoint=8, max_turns=16, max_tokens=8192)
    await generation.run(args)
    b.save(ROOT / 'generation-stage.json', {'legacy_screen_ignored_for_admission': True, 'summary_sha256': b.file_sha(ROOT / 'summary.json'), 'admission': False})
    await audit.run(SimpleNamespace(source=ROOT, root=ROOT / 'independent-review', ids=None, thinking=True))
    b.save(ROOT / 'completion.json', {'generated_summary_sha256': b.file_sha(ROOT / 'summary.json'), 'independent_review_summary_sha256': b.file_sha(ROOT / 'independent-review' / 'summary.json'), 'manual_sample_required_before_any_admission': True, 'admission': False})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['prepare', 'run'])
    a = p.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prepare() if a.mode == 'prepare' else asyncio.run(run())
