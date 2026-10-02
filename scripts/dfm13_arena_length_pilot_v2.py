"""Six-case correction contract fix; v1 raw results remain immutable."""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path

P=Path(__file__).with_name('dfm13_arena_length_pilot.py')
spec=importlib.util.spec_from_file_location('_length_contract_base',P)
pilot=importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
base=pilot.base
original_compact=pilot.compact


def compact(payload, **kwargs):
    result=original_compact(payload,**kwargs)
    schema=payload['response_format']['json_schema']['schema']
    result['messages'][0]['content']+='\nExact output contract (all fields required, no additional fields): '+json.dumps(schema)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','run'])
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--previous',type=Path)
    args=parser.parse_args()
    root=args.root.resolve()
    with base.lock(root/'controller.lock'):
        if args.command=='prepare':
            if (root/'manifest.json').exists():
                raise ValueError('Fresh root required')
            previous=args.previous.resolve()
            old=pilot.verify(previous)
            jobs=[j for j in base.load(previous/'jobs.json') if j['kind']=='suspected_reasoning_loop']
            assert len(jobs)==6
            base.write_json(root/'jobs.json',jobs)
            pins=dict(old['pins'])
            for path in (Path(__file__).resolve(),base.ROOT/'tests/test_dfm13_arena_length_pilot_v2.py',previous/'manifest.json',previous/'seal.json',root/'jobs.json'):
                pins[str(path)]=base.file_hash(path)
            manifest=dict(old,version='arena-length-diagnostic-contract-v2',total=6,
                groups={'suspected_reasoning_loop':6},previous=str(previous),pins=pins,
                max_initial_calls=6,contract_fix_only=True)
            base.write_json(root/'manifest.json',manifest)
            base.write_json(root/'seal.json',dict(sha256=base.file_hash(root/'manifest.json')))
        else:
            pilot.compact=compact
            asyncio.run(pilot.run(root,pilot.verify(root)))


if __name__=='__main__':
    main()
