"""Bounded-memory chat tokenization using an explicitly frozen historical adapter."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import ExitStack
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

import jinja2
import numpy as np
import pyarrow.parquet as pq
from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.tokenize_hrm_hf import DTYPES


def adapter(path):
    spec = importlib.util.spec_from_file_location('historical_chat_adapter', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# Column pre-selection and the generic row fallback mirror the historical
# adapter (cd88c93), which the DFM7/DFM8 tokenizations actually ran with.
GENERIC_PARQUET_COLUMNS = ('instruction', 'prompt', 'question', 'input', 'text',
                           'source', 'document', 'article', 'response', 'completion',
                           'answer', 'target', 'output', 'summary', 'translation',
                           'label', 'condition', 'task')


def examples(module, path):
    if path.suffix != '.parquet':
        yield from module.read_examples(path)
        return
    # Keep the historical interpretation, but not its oversized Arrow batches.
    names = set(pq.ParquetFile(path).schema_arrow.names)
    if {'condition', 'instruction', 'response'} <= names:
        columns = ['condition', 'instruction', 'response']
    elif 'messages' in names:
        columns = ['messages'] + (['tools'] if 'tools' in names else [])
    else:
        columns = [c for c in GENERIC_PARQUET_COLUMNS if c in names] or None
    for batch in pq.ParquetFile(path).iter_batches(batch_size=128, columns=columns):
        batch_names = set(batch.schema.names)
        for row in batch.to_pylist():
            if {'condition', 'instruction', 'response'} <= batch_names:
                yield module.hrm_row_to_messages(str(row.get('condition') or 'direct'),
                    str(row.get('instruction') or ''), str(row.get('response') or ''))
            elif 'messages' in batch_names:
                if isinstance(row.get('messages'), list):
                    tools = row.get('tools')
                    yield from module.examples_from_messages(row['messages'],
                        tools if isinstance(tools, list) else None)
            else:
                example = module.generic_row_to_messages(row)
                if example is not None:
                    yield example


def initialize(adapter_path, tokenizer_path, template_path):
    global MODULE, TOKENIZER, TEMPLATE
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    MODULE = adapter(adapter_path)
    TOKENIZER = Tokenizer.from_file(tokenizer_path)
    TEMPLATE = jinja2.Environment().from_string(Path(template_path).read_text())


def process(job):
    source, output, fingerprint = job
    source, output = Path(source), Path(output)
    stat = source.stat()
    receipt = dict(driver='bounded-historical-chat-v1', fingerprint=fingerprint,
                   source_size=stat.st_size, source_mtime_ns=stat.st_mtime_ns)
    try:
        if json.loads((output / 'hf_receipt.json').read_text()) == receipt:
            arrays = {k: np.load(output / f'{k}.npy', mmap_mode='r') for k in DTYPES}
            if all(a.ndim == 1 and a.dtype == np.dtype(DTYPES[k]) for k, a in arrays.items()):
                if len({len(a) for k, a in arrays.items() if k != 'tokens'}) == 1:
                    return output.name, 'cached'
    except (OSError, ValueError, EOFError):
        pass
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.chat-', dir=output.parent.parent))
    counts = dict.fromkeys(DTYPES, 0)
    skipped = 0
    try:
        with ExitStack() as stack:
            streams = {k: stack.enter_context((stage / f'{k}.raw').open('wb')) for k in DTYPES}
            for example in examples(MODULE, source):
                pair = MODULE.tokenize_example(TOKENIZER, TEMPLATE, example, False)
                if pair is None:
                    skipped += 1
                    continue
                inst, resp = pair
                values = dict(tokens=inst + resp, inst_start=[counts['tokens']],
                    inst_len=[len(inst)], resp_start=[counts['tokens'] + len(inst)],
                    resp_len=[len(resp)])
                for k, data in values.items():
                    streams[k].write(np.asarray(data, dtype=DTYPES[k]).tobytes())
                    counts[k] += len(data)
        for k, dtype in DTYPES.items():
            with (stage / f'{k}.npy').open('wb') as target:
                np.lib.format.write_array_header_1_0(target,
                    dict(descr=dtype, fortran_order=False, shape=(counts[k],)))
                with (stage / f'{k}.raw').open('rb') as raw:
                    shutil.copyfileobj(raw, target, length=8 * 1024 * 1024)
            (stage / f'{k}.raw').unlink()
        after = source.stat()
        if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError(f'Source changed during tokenization: {source}')
        (stage / 'metadata.json').write_text(json.dumps(dict(source_size=stat.st_size,
                                                          source_mtime=int(stat.st_mtime))))
        (stage / 'hf_receipt.json').write_text(json.dumps(receipt))
        if output.exists():
            shutil.rmtree(output)
        stage.rename(output)
        return output.name, counts['inst_len'], skipped
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--adapter', type=Path, required=True)
    p.add_argument('--tokenizer', type=Path, required=True)
    p.add_argument('--template', type=Path, required=True)
    p.add_argument('--workers', type=int, default=64)
    args = p.parse_args()
    if args.workers < 1:
        p.error('workers must be positive')
    args.output.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(b''.join(x.read_bytes() for x in
        (Path(__file__), args.adapter, args.tokenizer, args.template))).hexdigest()
    paths = sorted((x for x in args.input.iterdir() if x.is_file()),
                   key=lambda x: x.stat().st_size, reverse=True)
    if not paths:
        raise ValueError('Empty input inventory')
    with (args.output / '.driver.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with ProcessPoolExecutor(max_workers=args.workers, initializer=initialize,
                initargs=tuple(str(x) for x in (args.adapter, args.tokenizer, args.template))) as pool:
            futures = [pool.submit(process, (str(x), str(args.output / x.name), fingerprint)) for x in paths]
            for i, future in enumerate(as_completed(futures), 1):
                print(f'{i}/{len(paths)} {future.result()}', flush=True)


if __name__ == '__main__':
    main()
