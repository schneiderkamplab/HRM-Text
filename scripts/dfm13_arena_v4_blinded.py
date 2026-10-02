"""Freeze unchanged v4 predictions on supplied samples; never open references."""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path

PATH=Path(__file__).with_name('dfm13_arena_reviewer_v4_schema.py')
spec=importlib.util.spec_from_file_location('_arena_v4_blind_adapter',PATH)
adapter=importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
engine=adapter.engine
base=engine.base


def check_samples(rows):
    if len(rows)!=40 or len({r['id'] for r in rows})!=40:
        raise ValueError('Exactly forty unique samples required')
    for row in rows:
        if base.digest(row['example'])!=row['row_sha256']:
            raise ValueError('Sample row hash drift')
        base.visible(row['example'])


def prepare(root,samples,template):
    root,samples,template=map(lambda p:Path(p).resolve(),(root,samples,template))
    with base.lock(root/'controller.lock'):
        if any(p.name!='controller.lock' for p in root.iterdir()):raise ValueError('Fresh root required')
        manifest,development=engine.verify(template)
        rows=[base.strict_json(l) for l in samples.read_text().splitlines()]
        check_samples(rows)
        baseline=[base.strict_json(l) for l in (Path(manifest['source'])/'samples.jsonl').read_text().splitlines()]
        ids={r['source_id'] for r in rows}
        overlap=dict(baseline1000=sorted(ids & {r['source_id'] for r in baseline}),
                     development129=sorted(ids & {r['source_id'] for r in development}))
        tok=engine.tokenizer(manifest['tokenizer_dir']);jobs=[]
        for i,row in enumerate(rows):
            document=engine.evidence(row['example'])
            requests={r:engine.request(document,r,False) for r in ('neutral','critic')}
            jobs.append(dict(id=row['id']+'-off',source_id=row['source_id'],thinking=False,document=document,
                requests=requests,budgets={r:engine.measure(tok,p,manifest['context_limit']) for r,p in requests.items()},
                endpoint_index=i%8,exposed_control=False,row_sha256=row['row_sha256']))
        with base.atomic(root/'jobs.jsonl') as stream:
            for job in jobs:stream.write(json.dumps(job,ensure_ascii=False)+'\n')
        pins=dict(manifest['pins'])
        for path in (samples,Path(__file__),Path(__file__).parents[1]/'tests/test_dfm13_arena_v4_blinded.py',
                     template/'manifest.json',template/'seal.json',template/'jobs.jsonl'):
            pins[str(path.resolve())]=base.file_hash(path)
        result=dict(manifest,pins=pins,total=40,mode='off',subset='reference-blinded40',
            reference_accessed=False,input_exposure=overlap,samples_path=str(samples),
            jobs_sha256=base.file_hash(root/'jobs.jsonl'))
        base.write_json(root/'manifest.json',result)
        base.write_json(root/'seal.json',dict(manifest_sha256=base.file_hash(root/'manifest.json')))
        engine.verify(root)
        return dict(total=40,overlap_counts={k:len(v) for k,v in overlap.items()},references_read=False)


def freeze(root):
    root=Path(root)
    with base.lock(root/'controller.lock'):
        _,jobs=engine.verify(root)
        if (root/'predictions-frozen.json').exists():raise ValueError('Predictions already frozen')
        outcomes={}
        for job in jobs:
            path=root/'outcomes'/f"{job['id']}.json"
            result=base.load(path)
            if result['status'] not in ('complete','review_error','invalid_response','abort_status_unknown','http_error'):
                raise ValueError('Predictions not terminal')
            outcomes[str(path.resolve())]=base.file_hash(path)
        paths=[root/'manifest.json',root/'seal.json',root/'jobs.jsonl',root/'assessment.json']
        paths+=list((root/'stages').glob('*.json'))+list((root/'raw').glob('*.json'))
        receipt=dict(version='v4-blind-freeze-v1',reference_accessed=False,total=40,
                     outcomes=outcomes,artifacts={str(p.resolve()):base.file_hash(p) for p in paths})
        base.write_json(root/'predictions-frozen.json',receipt)
        return dict(total=40,freeze_sha256=base.file_hash(root/'predictions-frozen.json'),references_read=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','run','freeze'])
    p.add_argument('--root',type=Path,required=True);p.add_argument('--samples',type=Path);p.add_argument('--template',type=Path)
    p.add_argument('--servers-ready',action='store_true');a=p.parse_args()
    if a.command=='prepare':
        if not a.samples or not a.template:p.error('--samples and --template required')
        result=prepare(a.root,a.samples,a.template)
    elif a.command=='run':
        asyncio.run(engine.run(a.root,a.servers_ready));result=freeze(a.root)
    else:result=freeze(a.root)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
