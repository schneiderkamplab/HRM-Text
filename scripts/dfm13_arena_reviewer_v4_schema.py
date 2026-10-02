"""V4 transport correction: show the enforced schema to the model explicitly."""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path

PATH=Path(__file__).with_name('dfm13_arena_reviewer_v4.py')
spec=importlib.util.spec_from_file_location('_arena_v4_explicit_schema',PATH)
engine=importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
engine.VERSION='arena-reviewer-v4-explicit-schema'
original_request=engine.request


def request(document,role,thinking,reviews=None):
    payload=original_request(document,role,thinking,reviews)
    data=json.loads(payload['messages'][1]['content'])
    data['output_schema']=engine.schema()
    payload['messages'][1]['content']=json.dumps(data,ensure_ascii=False)
    return payload


engine.request=request


def prepare(root,source,subset='controls',mode='both'):
    result=engine.prepare(root,source,subset,mode)
    root=Path(root)
    # Add adapter pins before any launch; base prepare pins its own implementation.
    with engine.base.lock(root/'controller.lock'):
        manifest=engine.base.load(root/'manifest.json')
        for path in [Path(__file__),Path(__file__).parents[1]/'tests/test_dfm13_arena_reviewer_v4_schema.py']:
            manifest['pins'][str(path.resolve())]=engine.base.file_hash(path)
        manifest['transport_correction']='Exact server schema also included in prompt; original v4 untouched'
        engine.base.write_json(root/'manifest.json',manifest)
        engine.base.write_json(root/'seal.json',dict(manifest_sha256=engine.base.file_hash(root/'manifest.json')))
        engine.verify(root)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','verify','run']);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--source',type=Path);p.add_argument('--subset',choices=['controls','diagnostic'],default='controls')
    p.add_argument('--mode',choices=['off','on','both'],default='both');p.add_argument('--servers-ready',action='store_true')
    a=p.parse_args()
    if a.command=='prepare':
        if a.source is None:p.error('--source required')
        result=prepare(a.root,a.source,a.subset,a.mode)
    elif a.command=='verify':result={'jobs':len(engine.verify(a.root)[1])}
    else:result=asyncio.run(engine.run(a.root,a.servers_ready))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
