"""Bounded exact hash statistics on a contiguous sample of actual pilot rows.

Reads mmap arrays only. Does not tokenize, mutate data, log to W&B or use CUDA.
Counts distinct tuples exactly within the bounded sample, not fingerprints.
"""
import argparse
import json
from pathlib import Path

import numpy as np


def measure(sequences, orders=(2, 3), heads=4, buckets=65536, max_tokens=100000):
    if max_tokens < 1 or heads < 1 or buckets < 2 or not orders or min(orders) < 2:
        raise ValueError("Invalid measurement bounds")
    distinct = {order: set() for order in orders}
    observations = {order: 0 for order in orders}
    consumed = rows = 0
    for sequence in sequences:
        ids = np.asarray(sequence)[:max_tokens - consumed]
        if not len(ids):
            continue
        rows += 1
        consumed += len(ids)
        for order in orders:
            observations[order] += max(0, len(ids) - order + 1)
            distinct[order].update(tuple(map(int, ids[i - order + 1:i + 1]))
                                   for i in range(order - 1, len(ids)))
        if consumed >= max_tokens:
            break
    results = []
    for order in orders:
        for head in range(heads):
            loads = np.zeros(buckets, dtype=np.int64)
            for ngram in distinct[order]:
                value = 0
                for token in reversed(ngram):
                    value = (value * (65599 + 2 * head) + token + 1) % buckets
                loads[value] += 1
            unique = len(distinct[order])
            occupied = int(np.count_nonzero(loads))
            colliding = int(loads[loads > 1].sum())
            results.append(dict(
                order=order, head=head, observations=observations[order],
                distinct_ngrams=unique, repeated_observations=observations[order] - unique,
                occupied_buckets=occupied, occupancy_fraction=occupied / buckets,
                excess_distinct_collisions=unique - occupied,
                excess_collision_rate=(unique - occupied) / max(1, unique),
                distinct_in_colliding_buckets=colliding,
                distinct_collision_fraction=colliding / max(1, unique),
                colliding_distinct_pairs=int((loads * (loads - 1) // 2).sum()),
                max_distinct_bucket_load=int(loads.max()),
            ))
    return dict(tokens=consumed, rows=rows, max_tokens=max_tokens, results=results,
                method="Exact distinct tuples within contiguous row-prefix sample; reset per row; "
                       "instruction + response[:-1]; last row truncated at token cap. "
                       "Not a population collision estimate or a random sample.",
                memory_bound="O(max_tokens * sum(orders) + buckets) Python integers/tuples; "
                             "one int64 bucket histogram at a time; input mmap read-only.")


def pilot_rows(dataset, epoch, start, max_tokens):
    tokens = np.load(dataset / "tokens.npy", mmap_mode="r")
    arrays = {name: np.load(dataset / f"epoch_{epoch}" / f"{name}.npy", mmap_mode="r")
              for name in ("inst_start", "inst_len", "resp_start", "resp_len")}
    if not 0 <= start < len(arrays["inst_start"]):
        raise ValueError("Sample start outside dataset")
    for row in range(start, len(arrays["inst_start"])):
        parts = []
        remaining = max_tokens
        for kind in ("inst", "resp"):
            offset = int(arrays[f"{kind}_start"][row])
            length = max(0, int(arrays[f"{kind}_len"][row]) - (kind == "resp"))
            length = min(length, remaining)
            parts.append(tokens[offset:offset + length])
            remaining -= length
        yield np.concatenate(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--checkpoint-state", type=Path, required=True)
    parser.add_argument("--max-tokens", type=int, default=100000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    state = json.loads(args.checkpoint_state.read_text())
    epoch, start = state["epoch"] - 1, state["global_row_cursor_in_epoch"]
    report = measure(pilot_rows(args.dataset, epoch, start, args.max_tokens),
                     max_tokens=args.max_tokens)
    report.update(dataset=str(args.dataset.resolve()), epoch=epoch, start_row=start,
                  checkpoint_step=state["step"])
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
