"""Broad, pinned seed reservoirs for owner-authorized DFM14 synthesis."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter
import json
from pathlib import Path

from dfm12.io import file_hash, load, lock, rows, write_json, digest
from dfm12.records import validate_messages
from dfm14.catalog import LANGUAGES
from dfm14.generation_prepare import reservoir
from dfm14.synthetic_quality import source_issues

ROOT = Path('data/dfm14/production-v1')


def prepare_pool(name):
    from tokenizers import Tokenizer
    from dfm14.transforms import window
    folder = ROOT / 'seeds'
    output = folder / (name + '.json')
    with lock(folder / (name + '.lock')):
        receipt = folder / (name + '-receipt.json')
        if receipt.exists():
            result = load(receipt)
            if file_hash(output) != result['sha256']:
                raise ValueError('Changed production seeds')
            return result
        inputs, counts = {}, Counter()
        tokenizer = Tokenizer.from_file(load('data/sampled_dfm13/metadata.json')['tokenizer_info']['tokenizer_path'])

        def read(path):
            path = Path(path)
            inputs[str(path.resolve())] = file_hash(path)
            yield from rows(path)

        def candidates():
            if name in LANGUAGES:
                base = Path('data/dfm14/gpu-ready')
                manifest = load(base/'manifest.json')
                for chunk in manifest['chunks']:
                    if chunk['language'] != name or chunk['task'] != 'denoising':
                        continue
                    if file_hash(base/chunk['input']) != chunk['sha256']:
                        raise ValueError('Changed native source chunk')
                    for row in read(base/chunk['input']):
                        source = dict(id=digest(row['audit_context']['original']),text=row['audit_context']['original'],
                            provenance=row['provenance'],source_audit_id=row['audit_id'])
                        if source_issues(dict(source=source)):
                            counts['source_hold'] += 1
                        else:
                            yield source
            elif name == 'openhermes':
                base = Path('data/dfm14/generation-calibration-v1')
                pin = load(base/'source-lock.json')
                path = base/'downloads/modernized-openhermes-en'/pin['file']
                if file_hash(path) != pin['sha256']:
                    raise ValueError('Changed modernized OpenHermes')
                for i,row in enumerate(read(path)):
                    messages = row.get('messages')
                    if row.get('tools') or not isinstance(messages,list) or not 2 <= len(messages) <= 12:
                        continue
                    if any(set(m) != {'role','content'} or m['role'] not in {'user','assistant'} for m in messages):
                        continue
                    try:
                        validate_messages(messages)
                    except ValueError:
                        continue
                    if 100 < len(json.dumps(messages,ensure_ascii=False)) < 6500:
                        yield dict(id=digest(messages),messages=messages,provenance=dict(repo=pin['repo'],revision=pin['revision'],file=pin['file'],row=i))
            elif name == 'knowledge-commonsense':
                for row in read('data/dfm14/knowledge-pilot-v1/atomic-train-relations.jsonl'):
                    yield row
            elif name == 'knowledge-textbook':
                for row in read('data/mimir_openstax_sft/passages/openstax_cc_by_en.jsonl'):
                    if row.get('license') == 'CC-BY-4.0':
                        yield dict(id=row['passage_id'],text=row['passage'],provenance=row)
            else:
                components = {'knowledge-science':'pes2o-evidence','knowledge-evidence':'pes2o-evidence',
                    'knowledge-explanatory_qa':'stackexchange-explanatory','knowledge-math':'swallow-stage3-qa'}
                component = components[name]
                for receipt_path in sorted(Path('data/dfm14/enrichment-v2/candidates',component).glob('*/receipt.json')):
                    receipt_data = load(receipt_path)
                    path = receipt_path.parent/'candidates.jsonl'
                    if file_hash(path) != receipt_data['sha256']:
                        raise ValueError('Changed knowledge candidates')
                    for row in read(path):
                        if row.get('text'):
                            try:
                                text = window(row['text'],tokenizer,row['id'],max_tokens=1800)
                            except ValueError:
                                continue
                            if source_issues(dict(source=dict(text=text))):
                                continue
                            yield dict(id=digest([row['id'],text]),text=text,provenance=row['provenance'],
                                source_document_id=row['id'],window_is_excerpt=True)
                        elif row.get('messages'):
                            yield dict(id=row['id'],messages=row['messages'],provenance=row['provenance'])
        size = 150000 if name == 'openhermes' else (100000 if name.startswith('knowledge-') else 25000)
        selected = reservoir(candidates(),size)
        if not selected:
            raise ValueError('No usable seeds for '+name)
        write_json(output,selected)
        result = dict(pool=name,rows=len(selected),sha256=file_hash(output),inputs=inputs,counts=dict(counts),training_ready=False)
        write_json(receipt,result)
        print(json.dumps(dict(pool=name,rows=len(selected))),flush=True)
        return result


def prepare():
    names = list(LANGUAGES)+['openhermes']+['knowledge-'+k for k in
        ('textbook','science','commonsense','explanatory_qa','evidence','math')]
    with lock(ROOT/'seeds/.prepare.lock'):
        results = []
        with ProcessPoolExecutor(max_workers=16) as pool:
            for future in as_completed([pool.submit(prepare_pool,name) for name in names]):
                results.append(future.result())
                write_json(ROOT/'seed-progress.json',dict(done=len(results),total=len(names),pools=results))
        write_json(ROOT/'seed-manifest.json',dict(pools=results))


if __name__ == '__main__': prepare()
