"""Train-only source-specific wave-four instruction conversion and audit enqueue."""
from collections import Counter
import json
from pathlib import Path

from .baltic_sources_cpu import renderer
from .io import atomic, digest, file_hash, load, lock, rows, write_json
from .records import validate_messages
from .wave4_cpu import enqueue

ROOT = Path('data/dfm13/wave4')


def convert(repo, language, patterns, mapper, selection=''):
    directory = ROOT/'downloads'/repo.replace('/', '--')
    pin = load(directory/'wave4-download.json')
    if pin['status'] != 'downloaded':
        raise ValueError('Source download incomplete')
    output = ROOT/'instructions'/(repo.replace('/', '--')+'-'+language+selection)
    with lock(output/'.lock'):
        receipt = output/'receipt.json'
        path = output/'candidates.jsonl'
        if not receipt.exists():
            render = renderer()
            seen, counts = set(), Counter()
            files = sorted({p for pattern in patterns for p in directory.glob(pattern)})
            if not files:
                raise ValueError('No canonical source files: '+repo)
            with atomic(path) as out:
                for source in files:
                    for index, row in enumerate(rows(source)):
                        counts['scanned'] += 1
                        try:
                            messages = mapper(row)
                            if messages is None:
                                counts['other_language'] += 1
                                continue
                            validate_messages(messages)
                            tokens = render.count(messages)
                        except (ValueError, KeyError, TypeError) as exc:
                            counts['rejected:'+str(exc)[:100]] += 1
                            continue
                        key = digest([language, messages])
                        if key in seen:
                            counts['duplicate'] += 1
                            continue
                        seen.add(key)
                        record = dict(id=key, language=language, task='instruction',
                            messages=messages, rendered_tokens=tokens, admission_authorized=False,
                            provenance=dict(repo=repo, revision=pin['revision'],
                                file=str(source.relative_to(directory)), row=index,
                                license=pin['license']))
                        for field in ('dataset','template'):
                            if isinstance(row.get(field),str):
                                record['provenance']['source_'+field]=row[field]
                        out.write(json.dumps(record, ensure_ascii=False)+'\n')
                        counts['ready'] += 1
            write_json(receipt, dict(repo=repo, revision=pin['revision'], counts=counts,
                inputs={str(p):file_hash(p) for p in files}, sha256=file_hash(path)))
            print(repo, language, counts, flush=True)
        elif load(receipt)['sha256'] != file_hash(path):
            raise ValueError('Converted output changed')
    enqueue(ROOT, output.name, path)


def main():
    convert('administraktor/hrvatski-dataset-v2', 'hr', ['data/train-*.parquet'],
        lambda r: [dict(role={'human':'user','gpt':'assistant'}[m['from']], content=m['value'])
                   for m in r['conversations']])
    convert('jvalline/LuxIT_wiki_subset', 'lb', ['LuxIT_wiki.jsonl'], lambda r:r['messages'])
    for language, code in [('sq','sqi'), ('hu','hun'), ('sr','srp'), ('fa','pes')]:
        convert('CohereLabs/aya_dataset', language, ['data/train-*.parquet'],
            lambda r, code=code: [dict(role='user', content=r['inputs']),
                dict(role='assistant', content=r['targets'])] if r['language_code']==code else None)
    convert('CohereLabs/aya_dataset','sq',['data/train-*.parquet'],
        lambda r: [dict(role='user',content=r['inputs']),dict(role='assistant',content=r['targets'])]
        if r['language_code']=='als' else None, selection='-tosk')
    convert('alban-labs/Kapibara','sq',['cleaned_entries.jsonl'],
        lambda r: [dict(role=role, content=turn[field]) for turn in r['conversation']
                   for role,field in [('user','input'),('assistant','output')]])
    for language,name in [('bg','Bulgarian'),('hr','Croatian'),('hu','Hungarian'),
                          ('sk','Slovak'),('sl','Slovenian')]:
        convert('utter-project/EuroBlocks-SFT-2512',language,['data/train-*.parquet'],
            lambda r,name=name: r['conversations'] if r['language']==name else None)


if __name__ == '__main__':
    main()
