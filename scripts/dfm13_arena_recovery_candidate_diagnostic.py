"""Explicitly authorized diagnostic after failed controls; never production acceptance."""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
import random
import sqlite3
import time

PATH = Path(__file__).with_name('dfm13_arena_frozen_review_recovery.py')
spec = importlib.util.spec_from_file_location('private_frozen_diagnostic', PATH)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
base = runner.base


def authorized(manifest, jobs, outcomes, controls):
    return (manifest.get('diagnostic_only') is True
        and manifest.get('controls_pass') is False
        and manifest.get('export_prohibited') is True
        and manifest.get('no_admission') is True
        and manifest.get('user_authorized_failed_control_diagnostic') is True
        and manifest.get('total') == 100
        and len([j for j in jobs if j['kind'] == 'recovery']) == 100
        and len(controls) == 6
        and all(outcomes.get(r['id']) == r for r in controls))


def prepare(root, source):
    if any(root.iterdir()):
        raise ValueError('Fresh diagnostic root required')
    manifest = runner.pilot.verify(source)
    controls = base.load(source/'controls-results.json')
    jobs = base.load(source/'jobs.json')
    if runner.controls_pass(jobs, {r['id']: r for r in controls}):
        raise ValueError('This exception is specifically for the preserved failed smoke')
    base.write_json(root/'jobs.json', jobs)
    base.write_json(root/'controls-results.json', controls)
    ids = sorted(j['id'] for j in jobs if j['kind'] == 'recovery')
    base.write_json(root/'manual-sample.json', dict(seed=20261001100,
        method='uniform random without replacement, frozen before outcomes',
        ids=random.Random(20261001100).sample(ids, 10)))
    with sqlite3.connect(root/'ledger.sqlite') as db:
        db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,status TEXT,request_sha256 TEXT,record TEXT)')
        for r in controls:
            db.execute('INSERT INTO jobs VALUES(?,?,?,?)',
                (r['id'], r['status'], r['request_sha256'], json.dumps(r)))
    manifest.update(version='recovery-candidate-diagnostic-v1', diagnostic_only=True,
        controls_pass=False, export_prohibited=True,
        user_authorized_failed_control_diagnostic=True,
        authorization='User authorized bounded100 recovery-candidate diagnostic despite5/6 controls; no production acceptance or admission.',
        source_root=str(source), created=time.time())
    for path in [source/'manifest.json', source/'seal.json', source/'controls-results.json',
                 root/'jobs.json', root/'controls-results.json', root/'manual-sample.json',
                 Path(__file__).resolve(), PATH.parent.parent/'tests/test_dfm13_arena_recovery_candidate_diagnostic.py']:
        manifest['pins'][str(path.resolve())] = base.file_hash(path)
    base.write_json(root/'manifest.json', manifest)
    base.write_json(root/'seal.json', dict(sha256=base.file_hash(root/'manifest.json')))


def run(root):
    with base.lock(root/'controller.lock'):
        manifest = runner.pilot.verify(root)
        controls = base.load(root/'controls-results.json')
        # Private module-local dispatch authorization, not a changed semantic verdict.
        runner.controls_pass = lambda jobs, outcomes: authorized(manifest, jobs, outcomes, controls)
        asyncio.run(runner.run(root, 'recovery', reviewed=True))
        summary = base.load(root/'recovery-complete.json')
        summary.update(diagnostic_only=True, controls_pass=False, export_prohibited=True,
                       no_admission=True, semantic_quality_unestablished=True)
        base.write_json(root/'recovery-complete.json', summary)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare', 'run'])
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--source', type=Path)
    args = p.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if args.command == 'prepare':
        prepare(root, args.source.resolve())
    else:
        run(root)
