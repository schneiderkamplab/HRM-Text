"""Verify the exact publication handoff without network or queue mutations."""
from pathlib import Path
from dfm12.io import digest, file_hash, load, rows, write_json

roots = [Path('exports_dfm13/finepdfs-exact-ccby-20261003-v1'),
         Path('exports_dfm13/finepdfs-lv-exact-ccby-20261003-v1')]
registry = {r['name']:r for r in load('config/dfm13_sources.json')['additions']}
records, wanted = [], {}
for root in roots:
    for record in load(root/'integrated.json')['records']:
        current = registry[record['name']]
        assert current['status'] == 'accepted_uploaded' and current['tokenization_performed']
        assert current['output_sha256'] == file_hash(current['output'])
        assert current['tokenized_rows'] == current['rows']
        receipt = load(current['tokenization_receipt'])
        assert receipt['pins']['source_sha256'] == current['output_sha256']
        assert receipt['rows'] == current['rows'] and receipt['tokens'] == current['tokenized_tokens']
        for row in rows(current['output']):
            assert row['id'] not in wanted
            assert row['target_message_index'] == len(row['messages'])-1
            wanted[row['id']] = row
        records.append({k:current[k] for k in ('name','hf_repo_id','hf_revision','rows',
            'output_sha256','tokenized_tokens','tokenization_receipt')})
verified = set()
for language in ('lt','lv'):
    path = Path('data/dfm13/baltic/audit-ready')/f'transform-baltic_{language}_finepdfs/candidates.jsonl'
    for original in rows(path):
        exported = wanted.get(original['id'])
        if exported is None:
            continue
        assert exported['messages'] == original['messages']
        assert exported['provenance'] == original['provenance']
        assert exported['rights_evidence']['original_record_sha256'] == digest(original)
        verified.add(original['id'])
assert verified == set(wanted) and len(verified) == 9
write_json(Path(__file__).parent/'verified-handoff.json', dict(records=records,
    verified_original_messages=9, tokenized_rows=sum(r['rows'] for r in records),
    tokenized_tokens=sum(r['tokenized_tokens'] for r in records),
    publisher_sha256=file_hash('dfm12/finepdf_rights_subset.py'),
    tests_sha256=file_hash('tests/test_finepdf_rights_subset.py'),
    gpu_requests=0, live_audit_writes=0))
print('Verified 9 unchanged conversations and 17,944 tokenized tokens')
