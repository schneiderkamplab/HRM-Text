"""Compare fresh HF file identities with historical receipts (no local payload reads)."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scripts.queue_dfm_hf_rebuild import ROOT, load, write_json


def check(queue):
    work = queue / 'dfm1'
    plan = load(queue / 'plan.json')
    manifest = load(Path(plan['acquisition']) / 'dfm1-hf-inputs.json')
    sources = {s['name']: s for s in manifest['hf_sources']}
    files = {(s['name'], f['path']): f for s in sources.values() for f in s['files']}

    def one(path):
        rel = path.relative_to(work / 'filtered')
        name, *parts = rel.parts
        if name in ('dbc', 'lexdk'):
            return dict(path=str(rel), status='agreement')
        if name == 'opus':
            return dict(path=str(rel), status='published_derivative_requires_token_parity')
        upstream = '/'.join(parts)
        f = files[name, upstream]
        receipt = ROOT / 'data/downloads/datasets' / name / '.cache/huggingface/download' / (upstream + '.metadata')
        if not receipt.exists():
            return dict(path=str(rel), status='missing_historical_receipt')
        revision, etag, *_ = receipt.read_text().splitlines()
        return dict(path=str(rel), status='matched' if etag in
                    (f['blob_id'], f['lfs_sha256']) else 'mismatched',
                    historical_revision=revision, historical_etag=etag,
                    fresh_revision=sources[name]['resolved_revision'])

    paths = [p for p in (work / 'filtered').rglob('*') if p.is_file()
             and (p.suffix in ('.parquet', '.jsonl') or p.name.endswith('.jsonl.gz'))]
    with ThreadPoolExecutor(max_workers=32) as pool:
        rows = list(pool.map(one, paths))
    from collections import Counter
    counts = dict(Counter(r['status'] for r in rows))
    write_json(work / 'historical-hf-receipt-comparison.json', dict(counts=counts, files=rows))
    print(counts, flush=True)
    if counts.get('mismatched') or counts.get('missing_historical_receipt'):
        raise ValueError('Historical HF receipt mismatch; inspect report')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue', type=Path, required=True)
    check(parser.parse_args().queue.resolve())
