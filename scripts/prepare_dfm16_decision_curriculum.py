"""Convert executable curriculum training decisions to native chat messages."""
from collections import Counter
import hashlib
import json
from pathlib import Path


def convert(row):
    d = row['decision']
    if d['dataset'] != 'generated-curriculum' or d['split'] != 'train':
        return None
    if d['soft'] or d['target'].count(1.0) != 1 or any(x not in (0, 1) for x in d['target']):
        raise ValueError('Expected verified hard label')
    assert len(d['options']) == len(d['target'])
    gold = d['target'].index(1.0)
    choices = '\n'.join(f'{i+1}. {text}' for i, text in enumerate(d['options']))
    prompt = (d['state'] + '\n\n' + d['question'] + '\n\n' + choices
              + '\n\nAnswer with the option number and its text.')
    return dict(messages=[dict(role='user', content=prompt),
                          dict(role='assistant', content=f'{gold+1}. {d["options"][gold]}')],
                source_id=d['id'], group_id=d['group_id'], skill=row['skill'],
                provenance=row['provenance'])


def main():
    registry = json.loads(Path('config/dfm16_decision_sources.json').read_text())
    source = Path(registry['local_sources'][0]['path'])
    out = Path('data/dfm16/decision_curriculum/input')
    out.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    target = out / 'train.jsonl'
    temp = target.with_suffix('.partial')
    with source.open() as stream, temp.open('w') as dest:
        for line in stream:
            row = convert(json.loads(line))
            if row is not None:
                counts[row['skill']] += 1
                dest.write(json.dumps(row, ensure_ascii=False) + '\n')
    assert sum(counts.values()) == 90120, counts
    temp.replace(target)
    receipt = dict(rows=sum(counts.values()), families=dict(counts),
                   source=str(source), source_sha256=hashlib.file_digest(source.open('rb'), 'sha256').hexdigest(),
                   output=str(target), tokenized=False)
    (out.parent / 'conversion.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
