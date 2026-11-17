"""Warm only file pages referenced by a sampled epoch, in physical file order."""
import argparse
import json
import threading
import time
from pathlib import Path

import numpy as np

PAGE = 4096


def mark_ranges(delta, starts, lengths, *, token_count, itemsize, offset):
    if np.any(starts < 0) or np.any(lengths < 0) or np.any(starts > token_count - lengths):
        raise ValueError('Sampled token range outside token array')
    valid = lengths > 0
    starts, lengths = starts[valid], lengths[valid]
    first = (offset + starts * itemsize) // PAGE
    end = (offset + (starts + lengths) * itemsize + PAGE - 1) // PAGE
    np.add.at(delta, first, 1)
    np.add.at(delta, end, -1)


def selected_ranges(delta, file_size):
    # In-place prefix sum avoids another multi-GB array on the real dataset.
    np.cumsum(delta, dtype=delta.dtype, out=delta)
    used = delta[:-1] > 0
    edges = np.diff(used.view(np.int8), prepend=0, append=0)
    starts = np.flatnonzero(edges == 1).astype(np.int64) * PAGE
    ends = np.minimum(np.flatnonzero(edges == -1).astype(np.int64) * PAGE, file_size)
    return np.column_stack((starts, ends))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--epoch', type=int, default=0)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--previous-reader', type=Path)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    state = dict(started=time.time(), status='planning', planned_rows=0, read_bytes=0)
    lock = threading.Lock()

    def update(**values):
        with lock:
            state.update(values)

    def work():
        try:
            token_path = args.dataset / 'tokens.npy'
            tokens = np.load(token_path, mmap_mode='r')
            if tokens.ndim != 1 or tokens.dtype.kind not in 'iu':
                raise ValueError('Expected a one-dimensional integer token array')
            arrays = {k: np.load(args.dataset / f'epoch_{args.epoch}' / f'{k}.npy', mmap_mode='r')
                      for k in ('inst_start', 'inst_len', 'resp_start', 'resp_len')}
            rows = len(arrays['inst_start'])
            if any(a.ndim != 1 or a.dtype.kind not in 'iu' or len(a) != rows for a in arrays.values()):
                raise ValueError('Invalid epoch index arrays')
            size = token_path.stat().st_size
            delta = np.zeros((size + PAGE - 1) // PAGE + 1, dtype=np.int32)
            if rows * 2 >= np.iinfo(np.int32).max:
                raise ValueError('Too many intervals for int32 page counts')
            for start in range(0, rows, 1_000_000):
                if (args.output / 'stop.request').exists():
                    update(status='stopped'); return
                end = min(rows, start + 1_000_000)
                for kind in ('inst', 'resp'):
                    mark_ranges(delta, arrays[kind + '_start'][start:end].astype(np.int64),
                                arrays[kind + '_len'][start:end].astype(np.int64),
                                token_count=len(tokens), itemsize=tokens.dtype.itemsize,
                                offset=tokens.offset)
                update(planned_rows=end, total_rows=rows)
            ranges = selected_ranges(delta, size)
            del delta
            np.save(args.output / 'ranges.npy', ranges)
            selected = int(np.sum(ranges[:, 1] - ranges[:, 0]))
            # A stopped predecessor's completed prefix is already read; do not
            # mistake its still-in-flight read for warmed bytes.
            prefix = 0
            if args.previous_reader:
                while True:
                    prior = json.loads((args.previous_reader / 'status.json').read_text())
                    if prior['status'] != 'reading':
                        break
                    update(status='waiting_for_previous_reader')
                    time.sleep(2)
                if Path(prior.get('current_file', '')).resolve() == token_path.resolve():
                    prefix = int(prior.get('current_file_read_bytes', 0))
            remaining = ranges.copy()
            remaining[:, 0] = np.maximum(remaining[:, 0], prefix)
            remaining = remaining[remaining[:, 1] > remaining[:, 0]]
            todo = int(np.sum(remaining[:, 1] - remaining[:, 0]))
            update(status='reading', token_file_bytes=size, selected_page_bytes=selected,
                   ranges=len(ranges), previous_prefix_bytes=prefix, remaining_bytes=todo,
                   selected_already_read_bytes=selected-todo, read_started=time.time())
            buffer = bytearray(16 * 1024 * 1024)
            view = memoryview(buffer)
            read = 0
            with token_path.open('rb', buffering=0) as f:
                for lo, hi in remaining:
                    f.seek(int(lo))
                    position = int(lo)
                    while position < hi:
                        if (args.output / 'stop.request').exists():
                            update(status='stopped'); return
                        n = f.readinto(view[:min(len(buffer), int(hi)-position)])
                        if not n:
                            raise EOFError('Unexpected end of tokens.npy')
                        position += n
                        read += n
                        update(read_bytes=read, current_file_offset=position)
            update(status='complete')
        except Exception as exc:
            update(status='failed', error=repr(exc))

    worker = threading.Thread(target=work)
    worker.start()
    while True:
        with lock:
            snapshot = dict(state)
        snapshot['time'] = time.time()
        tmp = args.output / 'status.tmp'
        tmp.write_text(json.dumps(snapshot, indent=2) + '\n')
        tmp.replace(args.output / 'status.json')
        print(json.dumps(snapshot), flush=True)
        if snapshot['status'] in ('complete', 'stopped', 'failed'):
            break
        time.sleep(5)
    worker.join()
    if state['status'] == 'failed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
