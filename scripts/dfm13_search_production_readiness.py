"""Read-only CPU production inventory; does not authorize search or admission."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import pyarrow.parquet as pq
from scripts import dfm13_search_calibration as base

ROOTS=[
 'search-calibration-100-20261001-followup2',
 'search-reviewer-v3-20261001',
 'search-review-error-retry-20261001',
 'search-review-loop-retry-20261001',
 'search-targeted-repair-v4-20261001',
]


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if args.output.exists():raise ValueError('new snapshot output required')
    source=Path('data/downloads/arena_review/search-arena-24k/data/search-arena-chat-24k.parquet')
    db=sqlite3.connect('file:'+str(base.CAMPAIGN/'cache.sqlite')+'?mode=ro',uri=True)
    cache=[dict(status=s,count=n,owners=o) for s,n,o in db.execute('SELECT status,count(*),count(DISTINCT owner) FROM searches GROUP BY status')]
    db.close();stages=[];pins={}
    for name in ROOTS:
        root=Path('data/dfm13')/name
        paths=sorted((root/'records').glob('*/outcome.json'))
        outcomes=[json.loads(p.read_text()) for p in paths]
        stages.append(dict(root=str(root),terminal=len(outcomes),finished=(root/'finished.json').exists(),
            counts=dict(Counter(o.get('verdict',o['status']) for o in outcomes))))
        for path in paths:pins[str(path.resolve())]=base.file_hash(path)
    report=dict(created_at=base.now(),stages=stages,cache=cache,paid_call_ceiling=100,
        new_paid_calls_allowed_this_phase=0,source_parquet_rows=pq.ParquetFile(source).metadata.num_rows,
        source_rows_are_not_eligible_or_verified_count=True,source_path=str(source),
        production_ready=False,admission_authorized=False,upload_authorized=False,
        readiness_blockers=[
            'Automatic keeps include known historical-date false accepts; require final independent dispositions.',
            'Missing citations and source-claim support are distinct; parser clearance is not factual clearance.',
            'Current cache supports only 75 distinct successful queried owners, not 100 fresh searches.',
            '12 unresolved paid reservations remain charged; do not retry/refund or spend remaining slots in this phase.',
            'Targeted repair carries a calibration-specific CPU-verified Miller-Rabin teacher hint globally; scope to its case before production.',
            'Whitelist only validated examples; preserve errors, uncertainty, temporal scope and source-license review.',
        ],teacher_hint=dict(kind='CPU-verified correction',case_prefix='032d2d0c',
            fact='3215031751 = 151*751*28351 passes strong tests for bases 2,3,5,7 yet is composite and below 2^32',
            current_scope='global targeted-calibration repair system prompt',independent_generalization_claim=False),pins=pins)
    base.atomic(args.output/'manifest.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('pins','readiness_blockers','teacher_hint')}))


if __name__=='__main__':main()
