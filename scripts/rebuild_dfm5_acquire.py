"""Acquire immutable June DFM5 publications into an isolated HF-only root.

Publication dates select candidates, not historical equivalence. Downstream
row and token comparisons are mandatory even when every checksum passes.
"""
import argparse
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import statistics
import subprocess
import sys
import time

from huggingface_hub import HfApi, hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.replay_dfm_serial import write_json


def load(path):
    return json.loads(path.read_text())


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def candidates():
    config = load(ROOT / 'config/data/dfm5_hf_rebuild.json')
    rows = [dict(repo_id='schneiderkamplab/' + name, kind='export', name=name)
            for name in config['exports']]
    # This manifest supplies only historical source identities, never payloads.
    sources = config['synthetic_sources']
    counts = {g: sum(x['group'] == g for x in sources)
              for g in ('high40', 'repeat30')}
    if counts != dict(high40=40, repeat30=30):
        raise ValueError('Historical synthetic identity manifest is incomplete')
    rows.extend(sources)
    if len({r['repo_id'] for r in rows}) != 82:
        raise ValueError('DFM5 requires 82 distinct export/synthetic repositories')
    return rows


def validate_config_resume(manifest, config):
    if manifest['config'] == config:
        return
    # Initial acquisition used identical identities from the June local
    # metadata manifest. Moving those identities into tracked config must not
    # discard or resolve any already-pinned revision again.
    old = {k: v for k, v in manifest['config'].items() if k != 'download_workers'}
    new = {k: v for k, v in config.items()
           if k not in ('synthetic_sources', 'synthetic_identity_provenance')}
    identities = candidates()
    if old != new or len(manifest['entries']) != len(identities) or any(
            any(saved.get(k) != v for k, v in identity.items())
            for saved, identity in zip(manifest['entries'], identities)):
        raise ValueError('Acquisition settings/identities changed; preserve the input lock')
    manifest['config'] = config


def acquire(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config = load(ROOT / 'config/data/dfm5_hf_rebuild.json')
        manifest_path = root / 'manifest.json'
        manifest = load(manifest_path) if manifest_path.exists() else dict(
            status='acquiring', config=config, entries=candidates())
        validate_config_resume(manifest, config)
        api = HfApi()
        cutoff = datetime.fromisoformat(config['publication_cutoff'])
        for entry in manifest['entries']:
            repo = entry['repo_id']
            if not entry.get('revision'):
                commits = api.list_repo_commits(repo, repo_type='dataset')
                eligible = [c for c in commits if c.created_at < cutoff]
                if not eligible:
                    raise ValueError(f'No historical publication before cutoff: {repo}')
                commit = max(eligible, key=lambda c: c.created_at)
                entry.update(revision=commit.commit_id, commit_date=commit.created_at.isoformat(),
                             revision_basis='latest_pre_cutoff_publication_requires_exact_comparison')
                write_json(manifest_path, manifest)
            revision = entry['revision']
            if not re.fullmatch('[0-9a-f]{40}', revision):
                raise ValueError('Unpinned HF revision')
            folder = root / 'downloads' / (repo.replace('/', '--') + '--' + revision)
            folder.mkdir(parents=True, exist_ok=True)
            entry['download_path'] = str(folder.resolve())
            if not entry.get('files'):
                info = api.dataset_info(repo, revision=revision, files_metadata=True)
                entry['files'] = [dict(path=s.rfilename, size=s.size,
                                      sha256=s.lfs.sha256 if s.lfs else None)
                                  for s in info.siblings if s.rfilename.startswith('data/')
                                  and s.rfilename.endswith('.jsonl.gz')]
                if not entry['files'] or any('dfm8-extra' in f['path'] for f in entry['files']):
                    raise ValueError(f'Invalid June payload inventory: {repo}')
                write_json(manifest_path, manifest)
            for item in entry['files']:
                rel = Path(item['path'])
                if rel.is_absolute() or '..' in rel.parts:
                    raise ValueError('Unsafe HF payload path')
                path = folder / rel
                if not path.exists() or not item.get('verified_sha256'):
                    hf_hub_download(repo, item['path'], repo_type='dataset', revision=revision,
                                    local_dir=folder)
                if not path.resolve().is_relative_to(folder.resolve()):
                    raise ValueError('Download escapes isolated acquisition')
                actual = digest(path)
                if path.stat().st_size != item['size'] or (
                        item['sha256'] and actual != item['sha256']):
                    raise ValueError(f'HF checksum mismatch: {repo}/{rel}')
                if item.get('verified_sha256') not in (None, actual):
                    raise ValueError('Previously downloaded payload changed')
                item['verified_sha256'] = actual
                write_json(manifest_path, manifest)
            entry['status'] = 'downloaded_sha256_verified'
            write_json(manifest_path, manifest)
            print(f"Acquired {repo}@{revision}: {len(entry['files'])} files", flush=True)
        manifest['status'] = 'downloaded_sha256_verified'
        write_json(manifest_path, manifest)


def watch(root, logs):
    """Same latency guard as the serial rebuild, restricted to our own group."""
    logs.mkdir(parents=True, exist_ok=True)
    probe = logs / f'.latency-{os.getpid()}'
    def measure():
        try:
            p = subprocess.run([sys.executable, str(ROOT / 'scripts/watch_dfm_rebuild_io.py'),
                                '--probe', str(probe)], check=True, capture_output=True,
                               text=True, timeout=5)
            return float(p.stdout)
        except (subprocess.SubprocessError, ValueError):
            return 5.0
    baseline = statistics.median(measure() for _ in range(5))
    if baseline >= .5:
        raise ValueError('Filesystem latency unsafe for acquisition launch')
    with (logs / 'acquire.log').open('a') as out:
        child = subprocess.Popen([sys.executable, __file__, '--root', str(root)],
            stdout=out, stderr=subprocess.STDOUT, start_new_session=True,
            env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'OMP_NUM_THREADS': '1'})
        write_json(logs / 'acquisition-launch.json', dict(watchdog_pid=os.getpid(), pid=child.pid,
                   baseline=baseline, threshold=max(.5, 10 * baseline)))
        slow = 0
        while child.poll() is None:
            time.sleep(30)
            latency = measure()
            slow = slow + 1 if latency > max(.5, 10 * baseline) else 0
            print(json.dumps(dict(pid=child.pid, latency=latency, slow_checks=slow)), flush=True)
            if slow >= 3 and child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                break
        raise SystemExit(child.wait())


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--watch', type=Path)
    args = p.parse_args()
    if args.watch:
        watch(args.root.resolve(), args.watch.resolve())
    else:
        acquire(args.root.resolve())
