"""Bind manually read Croatian candidates to census, exports and source replay."""
import json
from pathlib import Path

import pyarrow.parquet as pq

from dfm12.io import digest, file_hash, load, write_json
from dfm12.transform import window
from dfm12.wave4_transforms import transform

ROOT = Path(__file__).resolve().parent


def main():
    report = load(ROOT / 'report.json')
    assert report['classifier_sha256'] == file_hash('scripts/diagnose_hr_transform_structure.py')
    for relative, sha in report['files'].items():
        assert file_hash(ROOT / relative) == sha
    flags = {}
    with (ROOT / 'flags.jsonl').open() as handle:
        for line in handle:
            f = json.loads(line)
            if f['task'] == 'paragraph-reordering' and f['flags']['below_two_furniture_only_remainder']:
                assert f['id'] not in flags
                flags[f['id']] = f
    notes = load(ROOT / 'manual44.json')
    assert len(flags) == len(notes) == 44
    path = report['results']['paragraph-reordering']['published_path']
    selected = []
    with open(path) as handle:
        for line in handle:
            row = json.loads(line)
            if row['id'] in flags:
                assert digest(row) == flags[row['id']]['record_sha256']
                assert row['provenance']['title'] in notes
                selected.append(row)
    assert {r['provenance']['title'] for r in selected} == set(notes)
    source_root = Path('data/dfm13/wave4/downloads/wikipedia-hr')
    source_pins = load('data/dfm13/wave4/transforms/wikipedia-hr/receipt.json')['inputs']
    requests = {}
    for row in selected:
        p = row['provenance']
        requests.setdefault(str(source_root / p['file']), {})[p['row']] = row
    replayed = set()
    for filename, indices in requests.items():
        assert file_hash(filename) == source_pins[filename]
        offset = 0
        for batch in pq.ParquetFile(filename).iter_batches(batch_size=256):
            if any(offset <= i < offset + len(batch) for i in indices):
                values = batch.to_pylist()
                for i, row in indices.items():
                    if not offset <= i < offset + len(batch):
                        continue
                    source = values[i-offset]
                    p = row['provenance']
                    assert all(source[k] == p[k] for k in ('id', 'title', 'url'))
                    text = window(source['text'], p['window_seed'], max_chars=4500)
                    regenerated = transform(text, 'hr', row['task'], p, 20261003)
                    assert text == row['audit_context']['original']
                    assert regenerated['id'] == row['id'] and regenerated['messages'] == row['messages']
                    replayed.add(row['id'])
            offset += len(batch)
    assert replayed == set(flags)
    with (ROOT / 'reviewed44.jsonl').open('w') as out:
        for row in selected:
            out.write(json.dumps(dict(id=row['id'], record_sha256=digest(row),
                window_sha256=digest(row['audit_context']['original']),
                structure=flags[row['id']], note=notes[row['provenance']['title']],
                manual_verdict='one_substantive_shuffled_unit_plus_furniture',
                source_replay_exact=True, record=row), ensure_ascii=False)+'\n')
    examples = load(ROOT / 'examples.json')
    lookup = {x['id']:x for group in examples.values() for x in group}
    manual = load(ROOT / 'representative-review.json')
    bound = []
    for note in manual:
        case = lookup[note['id']]
        assert case['provenance']['title'] == note['title']
        bound.append(dict(note, record_sha256=case['record_sha256'],
            window_sha256=digest(case['window']), provenance=case['provenance'],
            classification=case['structure']['classification']))
    write_json(ROOT / 'representative-review-bound.json', bound)
    write_json(ROOT / 'proposed-reordering-ids.json', dict(status='proposal_only_not_applied',
        task='paragraph-reordering', rows=44, ids=[row['id'] for row in selected],
        source_sha256=report['results']['paragraph-reordering']['published_sha256'],
        reviewed44_sha256=file_hash(ROOT / 'reviewed44.jsonl'),
        would_retain_reordering_rows=30942, other_tasks_unchanged=True))
    assert all(file_hash(p) == sha for p,sha in report['input_pins'].items())
    assert all(file_hash(p) == sha for p,sha in source_pins.items())
    write_json(ROOT / 'receipt.json', dict(status='diagnostic_and_manual_review_complete_no_filter',
        census_rows=sum(r['counts']['rows'] for r in report['results'].values()),
        reordering_rows=30986, manually_reviewed_narrow_candidates=44, other_manual_cases=len(bound),
        narrow_candidate_source_replays=44, tests_passed=10, filtering_applied=False,
        population_semantic_certification=False, all_input_hashes_unchanged=True,
        input_pins=dict(report['input_pins'], **source_pins),
        code_sha256=report['classifier_sha256'],
        files={p.name:file_hash(p) for p in sorted(ROOT.iterdir()) if p.is_file() and p.name != 'receipt.json'}))
    print('receipt', file_hash(ROOT / 'receipt.json'))


if __name__ == '__main__':
    main()
