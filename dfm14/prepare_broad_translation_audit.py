"""Prepare both-direction translation pairs for the shared compact audit runner."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path

from dfm12.io import atomic, file_hash, load, lock, rows, write_json

BASE = Path('data/dfm14')
PRIOR = ('persian-bridge-audit-v1', 'slovak-bridge-audit-v1',
         'institutional-parallel-v1/audit', 'sparse-parallel-v1/audit')


def prepare_pair(args):
    pair, output, excluded = args
    seen = set(excluded)
    chunks, buffer = [], []
    counts = Counter()
    inputs = []
    def flush():
        if not buffer:
            return
        job_id = f'translation-{pair}-{len(chunks):05d}'
        path = output/'chunks'/(job_id+'.jsonl')
        with atomic(path) as handle:
            for row in buffer:
                handle.write(json.dumps(row,ensure_ascii=False)+'\n')
        chunks.append(dict(job_id=job_id,input=str(path.relative_to(output)),
                           sha256=file_hash(path),rows=len(buffer),task='translation'))
        buffer.clear()
    for source in (BASE/'parallel-v1/candidates'/('opus-'+pair)/'candidates.jsonl',
                   BASE/'parallel-expansion-v4/novel'/(pair+'.jsonl')):
        if not source.exists():
            continue
        inputs.append(dict(path=str(source.resolve()),sha256=file_hash(source)))
        for row in rows(source):
            counts['input_rows'] += 1
            if row['id'] in seen:
                counts['previously_audited' if row['id'] in excluded else 'duplicate'] += 1
                continue
            seen.add(row['id'])
            if not row.get('messages') or not row.get('reverse_messages'):
                raise ValueError('Missing translation direction: '+row['id'])
            context=dict(row['audit_context'])
            context.update(reverse_conversation=row['reverse_messages'],
                           provenance=row.get('provenance'),
                           instruction='Accept only if BOTH translation directions preserve meaning, '
                           'names, numbers, negation and intended languages/variants. If an English '
                           'pivot anchor is provided, check equivalence and reject sense mismatches. '
                           'Direct pairs do not require an English anchor.')
            buffer.append(dict(row,audit_id=row['id'],
                language=' / '.join(context['languages'].values()),audit_context=context,
                training_ready=False,admission_authorized=False))
            counts['prepared_rows'] += 1
            if len(buffer)==500:
                flush()
    flush()
    return dict(pair=pair,chunks=chunks,counts=dict(counts),inputs=inputs)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=BASE/'broad-translation-gpu-v1')
    p.add_argument('--workers',type=int,default=16)
    args=p.parse_args()
    with lock(args.output/'.prepare.lock'):
        if (args.output/'manifest.json').exists():
            raise ValueError('Already prepared; do not overwrite audit inputs')
        excluded=set();prior=[]
        for name in PRIOR:
            for receipt in (BASE/name).glob('*/receipt.json'):
                r=load(receipt);journal=receipt.parent/'results.jsonl'
                if file_hash(journal)!=r['sha256']:
                    raise ValueError('Changed prior audit journal')
                prior.append(dict(path=str(journal.resolve()),sha256=r['sha256']))
                for record in rows(journal):
                    if record['status'] in ('accept','reject'):
                        excluded.add(record['audit_id'])
        coverage=load(BASE/'parallel-expansion-v4/coverage.json')
        jobs=[(row['pair'],args.output,excluded) for row in coverage['per_pair']]
        result=[];counts=Counter()
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for part in pool.map(prepare_pair,jobs):
                result.append(part);counts.update(part['counts'])
                write_json(args.output/'progress.json',dict(pairs=len(result),total_pairs=len(jobs),counts=dict(counts)))
        manifest=dict(status='ready_for_gpu_audit',chunks=[c for part in result for c in part['chunks']],
            counts=dict(counts),prior_audits=prior,inputs=[i for part in result for i in part['inputs']],
            preparation_sha256=file_hash(Path(__file__)),training_ready=False)
        write_json(args.output/'manifest.json',manifest)
        write_json(args.output/'readiness.json',dict(status='cpu_complete_ready_for_gpu',
            manifest_sha256=file_hash(args.output/'manifest.json'),training_ready=False))
        print(json.dumps(dict(counts=counts,chunks=len(manifest['chunks']),prior_audit_ids=len(excluded))),flush=True)


if __name__=='__main__':main()
