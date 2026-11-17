"""Collect qualification evidence; missing or inconsistent receipts never pass.

Run after each candidate's eight-rank capacity smoke, with its receipts under
<root>/full-size-v5/<candidate>/fsdp-full-rank{0..7}.json. This does not launch jobs.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = {'embla-causal': 'embla-causal-all',
            'embla-prefix': 'embla-prefix-target',
            'embla-loop': 'embla-loop-prefix-target'}


def collect(root, configs):
    missing = []
    evidence = {}

    def read(path):
        if not path.is_file():
            missing.append(str(path))
            return {}
        evidence[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        return json.loads(path.read_text())

    hashes = {key: hashlib.sha256((configs / (name + '.yaml')).read_bytes()).hexdigest()
              for key, name in VARIANTS.items()}
    compute = read(root / 'compute-match.json')
    mapping_path = root / 'capacity-attempts.json'
    attempts = read(mapping_path) if mapping_path.exists() else {}
    full_size = True
    native_training = True
    for key, name in VARIANTS.items():
        chosen = attempts.get(name,{})
        capacity_dir = Path(chosen.get('capacity',root / 'full-size-v5' / name))
        native_dir = Path(chosen.get('native',root / 'native-full-size' / name))
        for rank in range(8):
            native = read(native_dir / f'rank{rank}.json')
            native_training &= (native.get('passed') is True and native.get('rank') == rank and native.get('world_size') == 8 and native.get('global_batch_size') == 262144 and native.get('config_sha256') == hashes[key] and len(native.get('step_seconds',[])) >= 3)
            receipt = read(capacity_dir / f'fsdp-full-rank{rank}.json')
            full_size &= (receipt.get('passed') is True and
                          receipt.get('rank') == rank and
                          receipt.get('world_size') == 8 and
                          receipt.get('global_batch_size') == 262144 and
                          receipt.get('config_sha256') == hashes[key] and
                          len(receipt.get('step_seconds', [])) >= 3)
    serving = read(root / 'http-smoke-v5/result.json')
    suspension = read(root / 'cuda-suspend-v5-final/result.json')
    result = {
        'config_sha256': hashes,
        'full_size_8gpu': bool(full_size),
        'native_training': bool(native_training),
        'compute_match': compute.get('matrix_match_passed') is True and compute.get('config_sha256') == hashes,
        'serving': serving.get('passed') is True and bool(serving.get('responses')) and serving.get('responses') == serving.get('native'),
        'suspension': suspension.get('parity') == 'exact model, optimizer/EMA and per-step metrics match' and len(suspension.get('suspended', {}).get('phases', [])) >= 2,
        'missing_receipts': missing,
        'evidence_sha256': evidence,
        'limitations': ['Serving and suspension evidence uses the small model; capacity evidence must cover all full-size candidates.',
                       'Compute matching includes an estimated scalar allowance; see compute-match.json.',
                       'This receipt does not verify that the live scheduler has loaded the native backend.'],
    }
    result['passed'] = all(result[k] for k in ('full_size_8gpu', 'native_training', 'compute_match', 'serving', 'suspension')) and not missing
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT/'logs/diagnostics/embla')
    parser.add_argument('--configs', type=Path, default=ROOT/'logs/diagnostics/embla/candidate-configs-v5')
    args = parser.parse_args()
    result = collect(args.root, args.configs)
    output = args.root/'qualification.json'
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, indent=2) + '\n')
    temporary.replace(output)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
