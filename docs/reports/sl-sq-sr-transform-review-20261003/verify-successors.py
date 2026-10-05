"""Read-only proof of exact successor promotion and historical preservation."""
import json
from pathlib import Path
import sqlite3

from dfm12 import reviewed_transform_subset as s
from dfm12.io import digest, file_hash, load, write_json


def main():
    base = Path('exports_dfm13/sl-sq-exact4-subsets-20261003-v1')
    target = base / 'verified-handoff.json'
    assert not target.exists(), 'Preserve frozen handoff'
    registry = load(s.shared.REGISTRY)
    entries = []
    for (language, task), (count, revision, sha, case) in s.PARENTS.items():
        root = base / (language+'-'+task)
        folder = root / task
        package = s.verify_package(folder)
        completion = load(root/'completion.json')
        entry = next(e for e in registry['additions'] if e['name'] == package['name'])
        assert entry == completion['entries'][0]
        assert not entry.get('quality_hold') and entry['status'] == 'accepted_uploaded'
        assert entry['rows'] == count-1 and entry['tokenized_rows'] == count-1
        assert len(entry['remote_verified_files']) == len(s.ATTACHMENTS)+1
        parent = load(folder/'parent-entry.json')
        assert parent['output_sha256'] == sha == file_hash(parent['output'])
        old_publication = load(parent['manifest'])
        assert old_publication['hf_revision'] == revision and old_publication['output_sha256'] == sha
        preserved_arrays = 0
        legacy_array_files_present = 0
        if parent.get('tokenization_receipt'):
            receipt = load(parent['tokenization_receipt'])
            assert receipt['pins']['source_sha256'] == sha
            assert Path(receipt['output']) != Path(entry['tokenized_path'])
            legacy_array_files_present = len(list(Path(receipt['output']).rglob('*.npy')))
            assert legacy_array_files_present > 0
            for relative, pin in receipt.get('array_hashes', {}).items():
                assert file_hash(Path(receipt['output'])/relative) == pin
                preserved_arrays += 1
        decision = next(d for d in s.manual.reviewed_decisions() if d['id'] == s.manual.AUTHORIZED[case])
        ledger = Path('data/dfm13/wave4/release') / decision['component'] / 'ledger.sqlite'
        with sqlite3.connect(ledger.resolve().as_uri()+'?mode=ro',uri=True) as db:
            raw, status, review = db.execute('SELECT record,status,review FROM rows WHERE id=?',(decision['id'],)).fetchone()
            assert status == 'accepted' and digest(json.loads(raw)) == decision['record_sha256']
            assert digest(json.loads(review)) == decision['review_sha256']
        entries.append(dict(name=entry['name'], rows=entry['rows'], tokens=entry['tokenized_tokens'],
            hf_repo_id=entry['hf_repo_id'], hf_revision=entry['hf_revision'], output_sha256=entry['output_sha256'],
            tokenized_path=entry['tokenized_path'], excluded_id=decision['id'],
            remote_verified_attachment_count=len(entry['remote_verified_files']),
            historical_arrays_verified=preserved_arrays, historical_ledger_and_export_unchanged=True,
            historical_array_files_present=legacy_array_files_present,
            completion_sha256=file_hash(root/'completion.json'),
            assembly_verification_sha256=file_hash(root/'assembly-verification.json')))
    write_json(target, dict(status='accepted_uploaded', policy=s.POLICY, excluded_rows=4,
        retained_rows=sum(e['rows'] for e in entries), tokens=sum(e['tokens'] for e in entries),
        entries=entries, source_review_receipt_sha256=s.manual.RECEIPT_SHA,
        prepublication_mutations_applied=0, gpu_actions=0))
    print(json.dumps(load(target),indent=2))


if __name__ == '__main__':
    main()
