import json

from dfm12.baltic_pivots import main
from dfm12.io import file_hash, load, write_json


def test_pivots_use_explicit_root_and_reject_ambiguous_anchors(tmp_path):
    root = tmp_path / 'wave4'
    write_json(root / 'translations/config.json', dict(
        requested_pairs=[['hr', 'lb']], languages={'hr': 'Croatian', 'lb': 'Luxembourgish'},
        pair_budgets={'hr-lb': {'fraction': .0625}}))
    for language, pairs in [('hr', [('stable', 'HR'), ('ambiguous', 'HR1'), ('ambiguous', 'HR2')]),
                            ('lb', [('stable', 'LB'), ('ambiguous', 'LB2')])]:
        folder = root / 'translations/candidates' / ('opus-en-' + language)
        folder.mkdir(parents=True)
        path = folder / 'candidates.jsonl'
        records = [dict(language=language, reverse_language='en',
            messages=[{'role': 'assistant', 'content': native}],
            reverse_messages=[{'role': 'assistant', 'content': english}],
            provenance={'language': language, 'license': 'cc-by-4.0'}) for english, native in pairs]
        path.write_text(''.join(json.dumps(row) + '\n' for row in records))
        write_json(folder / 'receipt.json', {'sha256': file_hash(path)})
    main(root)
    path = root / 'pivots/candidates/opus-hr-lb/candidates.jsonl'
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(records) == 1
    row = records[0]
    assert row['provenance']['english_anchor'] == 'stable'
    assert len(row['provenance']['legs']) == 2
    assert row['messages'][-1]['content'] == 'LB'
    assert row['reverse_messages'][-1]['content'] == 'HR'
    assert not row['admission_authorized']
    manifest = load(root / 'pivots/manifest.json')
    assert len(manifest['inputs']) == 2
    # Existing sealed results are reused, never overwritten on a resume.
    before = file_hash(path)
    main(root)
    assert file_hash(path) == before
