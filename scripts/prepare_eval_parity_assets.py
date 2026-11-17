"""Materialize pinned remote evaluation inputs without changing tracked configs."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/work/dfm/HRM-Text'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def prepare(snapshot, output, host, port):
    output.mkdir(parents=True, exist_ok=True)
    records = json.loads(snapshot.read_text())
    jobs = [json.loads(r['definition']) for r in records
            if r['job_id'].startswith('dfm14-xl-step_3450000-') and r['status'] != 'skipped']
    mappings, pins = {}, {}

    def fetch(remote, expected=None):
        target = output / 'inputs' / remote.lstrip('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['rsync', '-a', '--checksum', '-e', f'ssh -o BatchMode=yes -p {port}',
                        f'{host}:{remote}', str(target)], check=True)
        digest = sha(target)
        if expected and digest != expected:
            raise ValueError('Remote pinned file changed: ' + remote)
        pins[remote] = {'path': str(target), 'sha256': digest}
        return target

    manifest_remote = REMOTE + '/config/dfm_dala_heldout_20260930.json'
    manifest = json.loads(fetch(manifest_remote).read_text())
    for language, entry in manifest['languages'].items():
        for field in ('producer_manifest', 'test_file'):
            item = entry[field]
            item['path'] = str(fetch(item['path'], item['sha256']))
        print('Verified historical heldout', language, flush=True)
    manifest_path = output / 'historical-dala.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    config_remote = REMOTE + '/config/dfm_evals_multilingual_dala_heldout.yaml'
    config = yaml.safe_load(fetch(config_remote).read_text())
    for group in config['sets'].values():
        for task in group['tasks']:
            task['name'] = task['name'].replace(REMOTE, str(ROOT))
            task['args'] = ['manifest=' + str(manifest_path) if s.startswith('manifest=')
                            else s for s in task['args']]
    config_path = output / 'historical-dala.yaml'
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    mappings[config_remote] = str(config_path)
    # Keep population contents byte-identical: artifact paths are relative to log roots.
    for job in jobs:
        meta = json.loads(job['metadata_json'])
        if job['action'] == 'average' and meta.get('multilingual_manifest'):
            remote = meta['multilingual_manifest']
            if remote not in mappings:
                target = fetch(remote, meta.get('population_manifest_sha256'))
                mappings[remote] = str(target)
    # Verify the shared scoring implementations, rather than copying over a dirty tree.
    scripts = ['scripts/headline_population_registry.py',
               'scripts/log_dfm5_headline_averages.py',
               'scripts/log_expanded_dala_v2_averages.py',
               'scripts/log_multilingual_headline_averages.py',
               'scripts/backfill_external_eval_to_wandb.py',
               'scripts/todo5_future_average',
               'scripts/euroeval_api_no_flash_attn_guard.py',
               'scripts/euroeval_json_output_compat.py',
               'dfm-evals/dfm_evals/tasks/dala_multilingual_heldout.py']
    for relative in scripts:
        remote = REMOTE + '/' + relative
        result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-p', str(port), host,
                                 'sha256sum ' + shlex.quote(remote)],
                                check=True, capture_output=True, text=True)
        if sha(ROOT / relative) != result.stdout.split()[0]:
            raise ValueError('Scoring code differs across machines: ' + relative)
    receipt = {'remote_host': host, 'remote_port': port, 'snapshot_sha256': sha(snapshot),
               'mappings': mappings, 'pins': pins, 'verified_code': scripts,
               'historical_manifest': str(manifest_path),
               'euroeval_bin': '/home/ucloud/miniforge3/envs/hrm/bin/uv run --no-project '
                   '--with euroeval==18.1.0 ' + str(ROOT / 'scripts/euroeval_api_no_flash_attn_guard.py')}
    (output / 'ready.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('Assets ready:', output / 'ready.json', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--host', default='ssh.cloud.sdu.dk')
    p.add_argument('--port', type=int, default=2546)
    args = p.parse_args()
    prepare(args.snapshot, args.output.resolve(), args.host, args.port)
