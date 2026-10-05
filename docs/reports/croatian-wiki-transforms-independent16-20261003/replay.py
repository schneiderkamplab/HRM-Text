"""Read-only deterministic Croatian transform evidence extraction/replay."""
import json
from pathlib import Path
import re

import pyarrow.parquet as pq

from dfm12.io import digest, file_hash, load, write_json
from dfm12.transform import window
from dfm12.wave4_transforms import transform

ROOT = Path(__file__).resolve().parent
SOURCE = Path('data/dfm13/wave4/downloads/wikipedia-hr')


def main():
    require_new = ROOT / 'evidence.json'
    if require_new.exists():
        raise ValueError('Evidence already frozen')
    registry = load('config/dfm13_sources.json')
    entries = sorted((e for e in registry['additions'] if
        e['name'].startswith('dfm13_wave4_wikipedia_hr_')), key=lambda e:e['task'])
    assert len(entries) == 4
    pins = dict(load('data/dfm13/wave4/transforms/wikipedia-hr/receipt.json')['inputs'])
    evidence = []
    for entry in entries:
        source = Path(entry['output'])
        assert file_hash(source) == entry['output_sha256']
        pins[str(source)] = entry['output_sha256']
        pins[entry['manifest']] = file_hash(entry['manifest'])
        ordinals = {(entry['rows'] - 1) * i // 3 for i in range(4)}
        count = 0
        with source.open() as handle:
            for ordinal, line in enumerate(handle):
                count += 1
                if ordinal in ordinals:
                    row = json.loads(line)
                    evidence.append(dict(case=len(evidence), ordinal=ordinal,
                        publication=entry, record=row, record_sha256=digest(row)))
        assert count == entry['rows']
    wanted = {}
    for item in evidence:
        p = item['record']['provenance']
        wanted.setdefault(str(SOURCE / p['file']), set()).add(p['row'])
    documents = {}
    for filename, indices in wanted.items():
        assert file_hash(filename) == pins[filename]
        offset = 0
        for batch in pq.ParquetFile(filename).iter_batches(batch_size=256):
            if any(offset <= i < offset + len(batch) for i in indices):
                values = batch.to_pylist()
                for i in indices:
                    if offset <= i < offset + len(batch):
                        documents[(filename, i)] = values[i-offset]
            offset += len(batch)
    checks = []
    for item in evidence:
        row = item['record']; p = row['provenance']
        source = documents[(str(SOURCE / p['file']), p['row'])]
        assert all(source[k] == p[k] for k in ('id', 'url', 'title'))
        selected = window(source['text'], p['window_seed'], max_chars=4500)
        replayed = transform(selected, 'hr', row['task'], p, 20261003)
        check = dict(case=item['case'], id=row['id'], task=row['task'],
            source_identity_matches=True, window_matches=selected == row['audit_context']['original'],
            candidate_id_matches=replayed['id'] == row['id'],
            messages_match=replayed['messages'] == row['messages'],
            source_chars=len(source['text']), window_chars=len(selected),
            window_blocks=len(selected.split('\n\n')), quality_status=row['quality_status'])
        body = row['messages'][0]['content'].split('\n\n', 1)[1]
        target = row['messages'][-1]['content']
        if row['task'] == 'denoising':
            check.update(target_equals_window=target == selected,
                         deleted_chars=len(selected)-len(body), corruption_changed=body != selected)
        elif row['task'] == 'paragraph-reordering':
            parts = selected.split('\n\n')
            shuffled = re.split(r'\n\n\[\d+\] ', body)
            shuffled[0] = re.sub(r'^\[1\] ', '', shuffled[0])
            check.update(target_equals_window=target == selected,
                permutation=[parts.index(s)+1 for s in shuffled],
                all_blocks_preserved=sorted(parts) == sorted(shuffled), nonidentity=parts != shuffled)
        elif row['task'] == 'prefix-continuation':
            check.update(prefix_matches=selected.startswith(body),
                exact_stripped_suffix=selected[len(body):].strip() == target)
        else:
            left, right = body.split(' <GAP> ')
            check.update(exact_source_span=(left + ' ' + target + ' ' + right).split() == selected.split(),
                         gap_count=body.count('<GAP>'))
        item.update(source_document=source, source_text_sha256=digest(source['text']),
                    window=selected, window_sha256=digest(selected), replay=check)
        checks.append(check)
    assert all(file_hash(p) == sha for p,sha in pins.items())
    write_json(ROOT / 'evidence.json', evidence)
    write_json(ROOT / 'mechanical-checks.json', checks)
    write_json(ROOT / 'input-pins.json', pins)
    with (ROOT / 'overview.md').open('w') as out:
        for item in evidence:
            row = item['record']
            out.write(f'\n## {item["case"]}: {row["task"]} - {row["provenance"]["title"]}\n')
            out.write(f'ID: `{row["id"]}`; ordinal {item["ordinal"]}\n\n')
            for message in row['messages']:
                out.write(f'### {message["role"]}\n\n{message["content"]}\n\n')
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
