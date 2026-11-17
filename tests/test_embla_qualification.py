import hashlib
import json

from scripts.collect_embla_qualification import VARIANTS, collect


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def test_receipts_require_every_rank_and_exact_config(tmp_path):
    configs = tmp_path / 'configs'
    configs.mkdir()
    hashes = {}
    for key, name in VARIANTS.items():
        config = configs / (name + '.yaml')
        config.write_text(name)
        hashes[key] = hashlib.sha256(config.read_bytes()).hexdigest()
        for rank in range(8):
            write(tmp_path / 'full-size-v5' / name / f'fsdp-full-rank{rank}.json', {
                'passed': True, 'rank': rank, 'world_size': 8,
                'global_batch_size': 262144, 'config_sha256': hashes[key],
                'step_seconds': [1, 1, 1],
            })
    for key,name in VARIANTS.items():
        for rank in range(8):
            value=json.loads((tmp_path / 'full-size-v5' / name / f'fsdp-full-rank{rank}.json').read_text())
            write(tmp_path / 'native-full-size' / name / f'rank{rank}.json',value)
    write(tmp_path / 'compute-match.json', {'matrix_match_passed': True, 'config_sha256': hashes})
    write(tmp_path / 'http-smoke-v5/result.json', {'passed': True, 'responses': ['ok'], 'native': ['ok']})
    write(tmp_path / 'cuda-suspend-v5-final/result.json', {
        'parity': 'exact model, optimizer/EMA and per-step metrics match',
        'suspended': {'phases': [{}, {}]},
    })
    assert collect(tmp_path, configs)['passed']
    removed = tmp_path / 'full-size-v5/embla-prefix-target/fsdp-full-rank7.json'
    original = removed.read_bytes()
    removed.unlink()
    result = collect(tmp_path, configs)
    assert not result['passed'] and str(removed) in result['missing_receipts']
    removed.write_bytes(original)
    (configs / 'embla-loop-prefix-target.yaml').write_text('changed')
    result = collect(tmp_path, configs)
    assert not result['passed'] and not result['full_size_8gpu'] and not result['compute_match']
