"""Recover small read-only DFM11 range provenance over SSH, never token payloads."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


FILES = ['data/tokenized_dfm11/union_manifest.json', 'data/tokenized_dfm11/tokenizer_info.json',
         'data/sampled_dfm11/metadata.json', 'logs/dfm11/sample_corrected.log',
         'data_io/prefix_config_dfm11.yaml', 'data_io/prefix_config_dfm10.yaml',
         'data_io/sample_tokenized.py', 'scripts/build_tokenized_dfm11_tree.py']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(root):
    import numpy as np
    union = root / 'data/tokenized_dfm11'
    rows = []; offset = 0
    for directory in sorted(union.iterdir()):
        if not directory.is_dir():
            continue
        arrays = {k: np.load(directory / (k + '.npy'), mmap_mode='r', allow_pickle=False)
                  for k in ('inst_len', 'resp_len', 'tokens')}
        size = int(arrays['inst_len'].sum(dtype=np.uint64)) + int(arrays['resp_len'].sum(dtype=np.uint64))
        assert size == len(arrays['tokens']), directory
        assert len(arrays['inst_len']) == len(arrays['resp_len']), directory
        probes = []
        if size:
            for position in sorted(set([0, max(0, size // 2 - 8), max(0, size - 16)])):
                length = min(16, size - position)
                raw = arrays['tokens'][position:position+length].astype('<u4').tobytes()
                probes.append(dict(relative_position=position, tokens=length, sha256=hashlib.sha256(raw).hexdigest()))
        metadata = directory / 'metadata.json'
        rows.append(dict(task=directory.name, resolved_path=str(directory.resolve()),
            token_start=offset, token_end=offset+size, tokens=size, original_targets=len(arrays['inst_len']),
            metadata=json.loads(metadata.read_text()) if metadata.exists() else None,
            metadata_sha256=sha(metadata) if metadata.exists() else None, token_probes=probes))
        offset += size
        if len(rows) % 1000 == 0:
            print('Remote inventory tasks', len(rows), file=sys.stderr, flush=True)
    sampled = np.load(root / 'data/sampled_dfm11/tokens.npy', mmap_mode='r', allow_pickle=False)
    assert offset == len(sampled), 'Remote token union differs from sampled backing length'
    return dict(schema='dfm11-remote-range-map-v1', remote_root=str(root), tasks=rows,
        stored_tokens=offset, sampled_dtype=str(sampled.dtype),
        order='sorted immediate tokenized union directories, including disabled tasks; pre-filter offsets',
        files={p: {'sha256': sha(root / p), 'bytes': (root / p).stat().st_size} for p in FILES})


def recover(output):
    output.mkdir(parents=True, exist_ok=True)
    inventory_path = output / 'source-map.json'
    if inventory_path.exists():
        raise FileExistsError('Preserve existing recovery: ' + str(inventory_path))
    host = 'ssh.cloud.sdu.dk'; remote = '/work/dfm/HRM-Text'
    command = ['ssh', '-o', 'BatchMode=yes', '-p', '6768', host,
        '/home/ucloud/miniforge3/envs/hrm/bin/python', '-', '--inventory', '--remote-root', remote]
    result = subprocess.run(command, input=Path(__file__).read_bytes(), stdout=subprocess.PIPE, check=True)
    data = json.loads(result.stdout)
    for relative, expected in data['files'].items():
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['rsync', '-aL', '-e', 'ssh -o BatchMode=yes -p 6768',
                        host + ':' + remote + '/' + relative, str(target)], check=True)
        if sha(target) != expected['sha256']:
            raise ValueError('Remote provenance changed during recovery: ' + relative)
    inventory_path.write_text(json.dumps(data, indent=2) + '\n')
    (output / 'transfer-receipt.json').write_text(json.dumps(dict(host=host, port=6768,
        remote_root=remote, source_map_sha256=sha(inventory_path), helper_sha256=sha(__file__),
        transferred_token_payload=False, tasks=len(data['tasks']), stored_tokens=data['stored_tokens'],
        files=data['files']), indent=2) + '\n')
    print('Recovered', len(data['tasks']), 'tasks to', output, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--inventory', action='store_true')
    parser.add_argument('--remote-root', type=Path, default=Path('/work/dfm/HRM-Text'))
    parser.add_argument('--output', type=Path, default=Path('data/provenance/dfm11_remote_20261002'))
    args = parser.parse_args()
    if args.inventory:
        print(json.dumps(inventory(args.remote_root)))
    else:
        recover(args.output)
