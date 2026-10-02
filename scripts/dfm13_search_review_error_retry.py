"""One bounded retry of seven failed reviews, preserving saved answers."""
import argparse
import asyncio
import fcntl
import json
from pathlib import Path
from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_reviewer_v3 as review
from scripts import dfm13_search_links_v4 as links

ORIGINAL_VALIDATE=review.validate


def validate(value,pages,answer):
    # Validate schema and typed findings before accessing optional model fields.
    if not isinstance(value,dict) or set(value)!=set(review.SCHEMA['required']):
        raise ValueError('review schema invalid')
    normalized={links.equivalent(u):p for u,p in pages.items()}
    transformed=json.loads(json.dumps(value))
    if not isinstance(value['supporting_urls'],list): raise ValueError('support list invalid')
    transformed['supporting_urls']=[links.equivalent(u) for u in value['supporting_urls']]
    candidate_keep=not value['findings'] and not value['unsupported_claims']
    if candidate_keep:
        links.check(answer,pages,value['supporting_urls'])
    canonical='\n'.join('<'+u+'>' for u in transformed['supporting_urls'])
    return ORIGINAL_VALIDATE(transformed,normalized,canonical)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','run'])
    parser.add_argument('--source',type=Path,default=Path('data/dfm13/search-reviewer-v3-20261001'))
    parser.add_argument('--root',type=Path,default=Path('data/dfm13/search-review-error-retry-20261001'))
    parser.add_argument('--concurrency-per-server',type=int,default=8)
    parser.add_argument('--timeout',type=int,default=600)
    args=parser.parse_args()
    if args.command=='prepare':
        if args.root.exists(): raise ValueError('new root required')
        manifest=json.loads((args.source/'manifest.json').read_text())
        jobs=[]
        for job in json.loads((args.source/'jobs.json').read_text()):
            path=args.source/'records'/job['id']/'outcome.json'
            if json.loads(path.read_text())['status']!='error': continue
            # Identical body text, sent once rather than duplicated in excerpts.
            job['pages']={u:{k:p[k] for k in ('url','title','body') if k in p} for u,p in job['pages'].items()}
            jobs.append(job)
            manifest['pins'][str(path.resolve())]=base.file_hash(path)
        base.atomic(args.root/'jobs.json',jobs)
        for path in (Path(__file__),Path(links.__file__),args.root/'jobs.json'):
            manifest['pins'][str(path.resolve())]=base.file_hash(path)
        manifest.update(total=len(jobs),source=str(args.source.resolve()),max_attempts=1,
                        evidence_change='none; omit duplicate excerpt representation',created_at=base.now())
        base.atomic(args.root/'manifest.json',manifest)
        print(json.dumps(dict(queued=len(jobs),generation_calls=0,paid_calls=0)))
    else:
        review.validate=validate
        with (args.root/'run.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            asyncio.run(review.run(args))


if __name__=='__main__':main()
