"""Read-only accounting of retained Jina usage; never estimates an invoice."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import sqlite3
from scripts import dfm13_search_calibration as base

ROOT=Path('data/dfm13/search-billing-snapshot-20261001')


def numeric(value):
    return value if type(value) in (int,float) else None


def main():
    if ROOT.exists():raise ValueError('immutable root already exists')
    db=sqlite3.connect('file:'+str(base.CAMPAIGN/'cache.sqlite')+'?mode=ro',uri=True)
    counts=dict(db.execute('SELECT status,count(*) FROM searches GROUP BY status'))
    rows=[]
    for key,owner,query,raw,provenance in db.execute('SELECT key,owner,query,raw,provenance FROM searches WHERE status="done" ORDER BY key'):
        payload=json.loads(raw)
        pages=payload.get('data',[])
        rows.append(dict(cache_key=key,owner=owner,query=query,raw_sha256=hashlib.sha256(raw).hexdigest(),
            raw_bytes=len(raw),retrieved_at=json.loads(provenance).get('retrieved_at'),
            response_meta_usage=payload.get('meta',{}).get('usage'),response_top_usage=payload.get('usage'),
            result_count=len(pages),full_content_characters=sum(len(p.get('content','')) for p in pages if isinstance(p.get('content'),str)),
            result_usage=[dict(url=p.get('url'),usage=p.get('usage')) for p in pages]))
    db.close()
    meta=[numeric((r['response_meta_usage'] or {}).get('tokens')) for r in rows]
    result_fields=Counter()
    for row in rows:
        for page in row['result_usage']:
            for key,value in (page['usage'] or {}).items():
                if numeric(value) is not None:result_fields[key]+=value
    report=dict(schema='dfm13-jina-retained-billing-evidence-v1',provider_calls=0,
        campaign_reservations=sum(counts.values()),status_counts=counts,
        retained_successful_responses=len(rows),retained_meta_usage_tokens=sum(x for x in meta if x is not None),
        responses_missing_meta_usage=sum(x is None for x in meta),
        result_usage_fields_separate_do_not_add_to_meta=dict(result_fields),
        full_response_bytes=sum(r['raw_bytes'] for r in rows),full_content_characters=sum(r['full_content_characters'] for r in rows),
        returned_documents=sum(r['result_count'] for r in rows),
        request_configuration=dict(endpoint='https://s.jina.ai/?q=<query>',accept='application/json',
            authorization='Bearer credential, never retained here',user_agent='DFM13SearchCalibration/1.0 (research; public documents)',
            x_engine_sent=False,token_budget_headers_sent=False,explicit_no_content_header_sent=False,
            observation='Search responses include bundled full document content and result-level usage. Local excerpting occurs after provider response and cannot reduce that completed request usage.'),
        limitations=['Usage is response-reported, not a billing ledger.',
            'Unretained oversized/error responses may have consumed provider resources; no token totals are available for them.',
            'HTTP 402 bodies were not captured in the historical client; do not infer exact credit/account cause.',
            'User-reported 19.7M tokens /145 requests cannot be exactly reconciled from 113 retained successful responses and 200 conservative local reservations.',
            'Result outputTokens/measuredTokens/scaledTokens/tokens are alternative fields, not additive charges; do not add them to response meta usage.',
            'No evidence that an X-Engine override was sent. Provider default engine and pricing cannot be inferred from absence of a header.'],
        pins={str(p.resolve()):base.file_hash(p) for p in (Path(__file__),Path(base.__file__),Path('scripts/dfm13_search_parallel86.py'))},rows=rows)
    base.atomic(ROOT/'report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows','pins','limitations')}))


if __name__=='__main__':main()
