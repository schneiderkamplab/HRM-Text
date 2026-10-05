"""Attach verified local publication readiness without claiming remote upload."""
from pathlib import Path
from dfm12.io import load, lock, write_json, file_hash


def main():
    package = Path('exports_dfm13/dfm13-hendrycks-math-worked')
    receipt = package.with_suffix('.ready.json')
    proof = load(receipt)
    assert proof['valid'] and proof['upload_ready'] and not proof['uploaded']
    assert (proof['rows'], proof['repeat']) == (7496, 5)
    # The private receipt pins the public package manifest.
    candidates = list(package.rglob('manifest.json'))
    assert any(file_hash(p) == proof['manifest_sha256'] for p in candidates)
    with lock(Path('config/dfm13_sources.lock')):
        path = Path('config/dfm13_sources.json'); registry = load(path)
        entry = next(e for e in registry['additions'] if e['name'] == 'hendrycks_math_worked')
        assert entry['rows'] == 7496 and entry['repeat'] == 5
        entry.update(local_hf_package=str(package.resolve()), local_upload_ready=True,
            local_upload_readiness_receipt=str(receipt.resolve()),
            local_upload_readiness_sha256=file_hash(receipt),
            intended_hf_repo_id=proof['hf_repo_id'])
        write_json(path, registry)


if __name__ == '__main__':
    main()
