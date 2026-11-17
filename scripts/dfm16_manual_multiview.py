"""Print blind review packets and expand explicitly reviewed parent annotations."""
import argparse
import json
from fnmatch import fnmatchcase
from pathlib import Path

from dfm12.io import rows, write_json, file_hash
from scripts.dfm16_judge_ensemble_study import save_rows
from scripts.prepare_dfm16_multiview_judges import ROOT

ANNOTATIONS = Path('docs/reports/dfm16-multiview-manual-labels.json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int)
    parser.add_argument('--end', type=int)
    args = parser.parse_args()
    checks = list(rows(ROOT/'checks.jsonl'))
    if args.start is not None:
        parents = {r['id']: r for r in rows(ROOT/'parents.jsonl')}
        for number in range(args.start, args.end+1):
            identifier = f'H{number:03}'
            seed = next(r for r in checks if r['study_id']==identifier and r['view']=='seed')
            print(identifier, 'SEED:\n'+seed['text'])
            seen = {p.strip(): f'seed paragraph {i}' for i,p in enumerate(seed['text'].split('\n\n'))}
            for i,m in enumerate(parents[seed['parent_id']]['messages']):
                print(identifier, 'MESSAGE',i,m['role'],'WORDS',len(m['content'].split()))
                for j,paragraph in enumerate(m['content'].split('\n\n')):
                    key = paragraph.strip()
                    if key in seen:
                        print(f'[exactly identical to {seen[key]}]')
                    else:
                        print(f'P{j}: {paragraph}')
                        seen[key] = f'message {i} paragraph {j}'
        return
    annotations = json.loads(ANNOTATIONS.read_text())
    labels = []
    valid = {r['id'] for r in checks}
    checksum = file_hash(ROOT/'checks.jsonl')
    for identifier, annotation in annotations['parents'].items():
        assert all(any(fnmatchcase(v, identifier+'/'+suffix) for v in valid) for suffix in annotation['overrides'])
    for row in checks:
        annotation = annotations['parents'].get(row['study_id'])
        if annotation is None:
            continue  # Never infer labels for an unread parent.
        suffix = row['id'].split('/',1)[1]
        matching = [value for pattern,value in annotation['overrides'].items() if fnmatchcase(suffix,pattern)]
        assert len(matching) <= 1, (row['id'], matching)
        label, note = matching[0] if matching else ['clear', 'No material defect found in manual review.']
        assert label in ('clear','bad','borderline')
        labels.append(dict(id=row['id'], label=label, note=note, reviewer='assistant-manual',
                           source_sha256=checksum))
    save_rows(ROOT/'manual-labels.jsonl', labels)
    write_json(ROOT/'manual-progress.json', dict(reviewed_parents=len(annotations['parents']), total_parents=200,
        labelled_checks=len(labels), total_checks=len(checks), annotations_sha256=file_hash(ANNOTATIONS)))
    print(len(annotations['parents']), 'parents;',len(labels),'checks manually labelled')


if __name__ == '__main__':
    main()
