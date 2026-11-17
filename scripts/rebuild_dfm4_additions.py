"""Reconstruct DFM4 additions from HF-rebuilt predecessors, never local payloads."""
import argparse
import hashlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import zip_longest
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace

import numpy as np
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import generate_dfm4_tasks as g
from scripts.replay_dfm_serial import equal_arrays, FIELDS, write_json


def paragraph_rows(text, kind, rel, row_index):
    if kind == 'dynaword':
        return g.paragraph_reorder_rows(text, 'da', 20260601, 4, kind, rel, row_index)
    # Original Common Pile recipe predates randomized multi-window selection.
    paragraphs = g.split_paragraphs(g.trim_text(text, 1370))[:8]
    row = g.paragraph_reorder_row_from_paragraphs(
        paragraphs, 'en', 20260601, kind, rel, row_index)
    return [row] if row else []


def paragraph_job(job):
    work, source, source_root, kind = job
    rel = source.relative_to(source_root)
    category = f'dfm4_{kind}_paragraph_reorder'
    output = work / 'paragraph'
    receipt = work / 'paragraph_receipts' / category / rel.with_suffix('.json')
    fingerprint = hashlib.sha256(Path(__file__).read_bytes() + Path(g.__file__).read_bytes()).hexdigest()
    stat = source.stat()
    provenance = dict(recipe_sha256=fingerprint, source_size=stat.st_size,
                      source_mtime_ns=stat.st_mtime_ns)
    if receipt.exists():
        saved = json.loads(receipt.read_text())
        if all(saved.get(k) == v for k, v in provenance.items()) and (
                saved['rows'] == 0 or (output / category / rel).exists()):
            return str(rel), saved['rows']
    stage = Path(tempfile.mkdtemp(prefix='.paragraph-', dir=work))
    try:
        writer = g.Writer(stage, category, rel, 4096)
        cap = 200000 if kind == 'dynaword' else 6000
        try:
            for row_index, text in enumerate(g.iter_parquet_column(source, 'response')):
                if row_index >= 250000 or writer.total_count >= cap:
                    break
                for row in paragraph_rows(text, kind, rel, row_index):
                    if writer.total_count >= cap:
                        break
                    writer.write(row)
        finally:
            count = writer.close()
        if count:
            dst = output / category / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage / category / rel, dst)
        receipt.parent.mkdir(parents=True, exist_ok=True)
        write_json(receipt, dict(rows=count, source=str(source), cap=cap, seed=20260601,
                                **provenance))
        return str(rel), count
    finally:
        shutil.rmtree(stage)


def paragraph(work, workers, limit=None):
    queue = work.parent
    jobs = []
    for kind, root, pattern in [
        ('common_pile', queue / 'dfm3/raw_converted', 'common_pile_*/*.parquet'),
        ('dynaword', queue / 'dfm1/converted/danish_dynaword', '**/*.parquet')]:
        paths = sorted(root.glob(pattern))
        if limit:
            paths = paths[:limit]
        jobs.extend((work, path, root, kind) for path in paths)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(paragraph_job, job) for job in jobs]
        for i, future in enumerate(as_completed(futures), 1):
            print(f'{i}/{len(jobs)} {future.result()}', flush=True)


def summarization(work):
    download = work / 'downloads/common_pile_arxiv_papers_filtered'
    if not download.exists():
        download.symlink_to((work.parent / 'dfm3/inputs/common_pile_arxiv_papers_filtered').resolve(),
                            target_is_directory=True)
    args = SimpleNamespace(downloads_root=work / 'downloads',
        summary_output_root=work / 'summary', force=False, batch_size=4096,
        limit_files=None, max_rows_scanned_per_file=250000,
        arxiv_summary_rows_per_file=200000, laion_rows_per_file=3000, laion_workers=8)
    print(g.generate_summarization(args), flush=True)


def verify(work, tokenized=False):
    if tokenized:
        pairs = [(work / 'tokenized_paragraph',
                  [ROOT / 'data/tokenized_dfm4_paragraph_reorder_common_existing',
                   ROOT / 'data/tokenized_dfm4_paragraph_reorder_dynaword_windows']),
                 (work / 'tokenized_summary', [ROOT / 'data/tokenized_dfm4_summarization'])]
        for rebuilt, refs in pairs:
            expected = {p.name: p for ref in refs for p in ref.iterdir() if p.is_dir()}
            actual = {p.name: p for p in rebuilt.iterdir() if p.is_dir()}
            if actual.keys() != expected.keys():
                raise ValueError(f'Task mismatch: missing={sorted(expected.keys()-actual.keys())} '
                                 f'extra={sorted(actual.keys()-expected.keys())}')
            for i, (name, path) in enumerate(sorted(actual.items()), 1):
                for field in ('tokens', *FIELDS):
                    equal_arrays(np.load(path / f'{field}.npy', mmap_mode='r'),
                                 np.load(expected[name] / f'{field}.npy', mmap_mode='r'),
                                 f'{name}/{field}')
                print(f'Compared {i}/{len(actual)} {name}', flush=True)
        write_json(work / 'addition-token-comparison.json', dict(status='matched'))
        return
    # The Common Pile parquet tree was partly overwritten historically; its
    # authoritative comparison is against preserved token arrays after encoding.
    for rebuilt, reference in [
        (work / 'paragraph/dfm4_dynaword_paragraph_reorder',
         ROOT / 'data/converted_sources_dfm4_paragraph_reorder_dynaword_windows/dfm4_dynaword_paragraph_reorder'),
        (work / 'summary', ROOT / 'data/converted_sources_dfm4_summarization')]:
        actual = {p.relative_to(rebuilt) for p in rebuilt.rglob('*.parquet')}
        expected = {p.relative_to(reference) for p in reference.rglob('*.parquet')}
        if actual != expected:
            raise ValueError(f'Generated file inventory mismatch: {rebuilt}: '
                             f'missing={sorted(expected-actual)} extra={sorted(actual-expected)}')
        for i, rel in enumerate(sorted(actual), 1):
            a, b = pq.ParquetFile(rebuilt / rel), pq.ParquetFile(reference / rel)
            for x, y in zip_longest(a.iter_batches(batch_size=4096), b.iter_batches(batch_size=4096)):
                if x is None or y is None or not x.equals(y):
                    raise ValueError(f'Generated row mismatch: {rel}')
            print(f'Compared generated {i}/{len(actual)} {rel}', flush=True)
    write_json(work / 'generated-row-comparison.json', dict(status='matched',
        scope='DynaWord and summaries; Common Pile requires token comparison'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('paragraph', 'summary', 'verify-rows', 'verify-tokens'))
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--limit-files', type=int)
    args = p.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    if args.stage == 'paragraph':
        paragraph(work, args.workers, args.limit_files)
    elif args.stage == 'summary':
        summarization(work)
    else:
        verify(work, tokenized=args.stage == 'verify-tokens')


if __name__ == '__main__':
    main()
