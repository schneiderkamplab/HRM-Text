"""Audit institutional pilot chunks without changing any active audit protocol."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path

from dfm12.io import atomic, file_hash, load, lock, rows, write_json
from dfm14 import parallel_audit
from dfm14.institutional_parallel import ROOT

OUTPUT = ROOT / 'audit'


def worker(endpoint):
    parallel_audit.PROMPT = parallel_audit.PROMPT.replace(
        'and equivalence\nto the English pivot anchor.',
        'and, only when an English pivot anchor is supplied, equivalence\nto that anchor.')
    parallel_audit.worker(OUTPUT, endpoint, 16)


def run():
    with lock(OUTPUT / '.controller.lock'):
        jobs = []
        for entry in load(ROOT/'coverage.json')['per_pair']:
            pair = entry['pair']; source = ROOT/'novel'/(pair+'.jsonl')
            records = list(rows(source))
            for start in range(0,len(records),500):
                name=f'{pair}-{start//500:04d}'
                path=OUTPUT/'inputs'/(name+'.jsonl')
                chunk=records[start:start+500]
                if not path.exists():
                    with atomic(path) as out:
                        for row in chunk: out.write(json.dumps(row,ensure_ascii=False)+'\n')
                elif list(rows(path)) != chunk: raise ValueError('Changed audit input')
                jobs.append(dict(pair=name,original_pair=pair,input=str(path),sha256=file_hash(path),rows=len(chunk)))
        manifest=dict(jobs=jobs,rows=sum(j['rows'] for j in jobs),thinking=False,retries=1,
            code_pins={str(p):file_hash(p) for p in (Path(__file__),Path(parallel_audit.__file__),
                Path('dfm14/generation_contract.py'),Path('dfm14/synthetic_review.py'))})
        if (OUTPUT/'manifest.json').exists() and load(OUTPUT/'manifest.json') != manifest:
            raise ValueError('Changed audit campaign')
        write_json(OUTPUT/'manifest.json',manifest)
        write_json(OUTPUT/'state.json',dict(phase='running',pid=os.getpid(),rows=manifest['rows']))
        with ProcessPoolExecutor(max_workers=8) as pool:
            list(pool.map(worker,[f'http://127.0.0.1:{p}/v1' for p in range(8800,8808)]))
        counts=Counter(); accepted={}
        for job in jobs:
            verdicts={r['audit_id']:r for r in rows(OUTPUT/job['pair']/'results.jsonl')}
            for row in rows(Path(job['input'])):
                verdict=verdicts[row['id']]; counts[verdict['status']]+=1
                if verdict['status']=='accept':
                    row['audit']=dict(result=verdict,evidence=str(OUTPUT/job['pair']/'results.jsonl'))
                    accepted.setdefault(job['original_pair'],[]).append(row)
        for pair,records in accepted.items():
            with atomic(ROOT/'accepted'/(pair+'.jsonl')) as out:
                for row in records: out.write(json.dumps(row,ensure_ascii=False)+'\n')
        write_json(OUTPUT/'state.json',dict(phase='complete',counts=dict(counts),training_ready=False,
            remaining=['inherited/benchmark decontamination','combined source selection and token caps']))


if __name__=='__main__': run()
