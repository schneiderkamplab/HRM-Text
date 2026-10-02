"""One bounded technical-only follow-up after the sealed full pass completes."""
import argparse
import asyncio
from collections import Counter
import fcntl
import json
from pathlib import Path
import shutil
import sqlite3
import time

from scripts import dfm13_repochat_full_campaign as campaign

b = campaign.b


def eligible(outcome):
    if outcome.get('status') != 'technical_failure':
        return False
    error = outcome.get('error', '')
    return error == 'ValueError: incomplete_final:stop' or any(
        error.startswith(prefix) for prefix in (
            'TimeoutError:', 'ServerDisconnectedError:', 'ClientConnectionError:',
            'ClientConnectorError:', 'ClientOSError:'))


def prepare(parent, root):
    manifest = b.load(parent / 'manifest.json')
    for path, digest in manifest['pins'].items():
        if b.file_sha(path) != digest:
            raise ValueError('parent pin drift: ' + path)
    completion = b.load(parent / 'completion.json')
    if b.file_sha(parent / 'progress.json') != completion['progress_sha256']:
        raise ValueError('completion hash drift')
    with sqlite3.connect(f'file:{parent}/jobs.sqlite?mode=ro', uri=True) as db:
        rows = db.execute('SELECT id,status,outcome FROM jobs').fetchall()
    if any(status != 'terminal' for _, status, _ in rows):
        raise ValueError('parent not terminal')
    selected = {key for key, _, value in rows if eligible(json.loads(value))}
    buckets = Counter(json.loads(value).get('error', '') for _, _, value in rows
                      if json.loads(value).get('status') == 'technical_failure')
    if (root / 'manifest.json').exists():
        prior = b.load(root / 'manifest.json')
        if {t['id'] for t in prior['tasks']} != selected:
            raise ValueError('retry selection drift')
        return
    root.mkdir(parents=True, exist_ok=True)
    for source in (parent / 'sources').glob('*/outcome.json'):
        target = root / 'sources' / source.parent.name / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for key in selected:
        target = root / 'trajectories' / key
        target.mkdir(parents=True, exist_ok=True)
        for source in (parent / 'trajectories' / key).glob('*.json'):
            if source.name == 'outcome.json':
                continue
            if source.name.startswith('generate-') and source.stem[-2:].isdigit():
                choice = b.load(source)['response']['choices'][0]
                message = choice['message']
                if not message.get('tool_calls') and not (message.get('content') or '').strip():
                    continue
            shutil.copy2(source, target / source.name)
    manifest['tasks'] = [t for t in manifest['tasks'] if t['id'] in selected]
    manifest['followup'] = {'parent': str(parent), 'manifest_sha256': b.file_sha(parent / 'manifest.json'),
                            'completion_sha256': b.file_sha(parent / 'completion.json'),
                            'max_followup_attempts': 1, 'selected': len(selected),
                            'technical_buckets': dict(buckets), 'script_sha256': b.file_sha(__file__),
                            'policy': 'Only empty-stop final or transport failures; never reviewed rows.'}
    b.save(root / 'selection.json', manifest['followup'])
    b.save(root / 'manifest.json', manifest)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--per-endpoint', type=int, default=64)
    args = parser.parse_args()
    if args.parent.resolve() == args.root.resolve():
        raise ValueError('separate root required')
    args.root.mkdir(parents=True, exist_ok=True)
    with (args.root / 'watcher.lock').open('a') as watcher:
        fcntl.flock(watcher, fcntl.LOCK_EX | fcntl.LOCK_NB)
        b.save(args.root / 'watcher-status.json', {'status': 'waiting_parent_completion', 'parent': str(args.parent), 'admission': False})
        while not (args.parent / 'completion.json').exists():
            time.sleep(15)
        with (args.parent / 'controller.lock').open('a') as parent_lock:
            fcntl.flock(parent_lock, fcntl.LOCK_EX)
            prepare(args.parent, args.root)
        with (args.root / 'controller.lock').open('a') as controller:
            fcntl.flock(controller, fcntl.LOCK_EX | fcntl.LOCK_NB)
            b.save(args.root / 'watcher-status.json', {'status': 'retry_running', 'admission': False})
            asyncio.run(campaign.run(args))
        b.save(args.root / 'watcher-status.json', {'status': 'retry_finished', 'admission': False})


if __name__ == '__main__':
    main()
