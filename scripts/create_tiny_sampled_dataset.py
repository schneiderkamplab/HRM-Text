#!/usr/bin/env python3
"""Create a tiny sampled dataset for smoke-testing training loops."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rows", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--vocab-size", type=int, default=512)
    parser.add_argument("--inst-len", type=int, default=5)
    parser.add_argument("--resp-len", type=int, default=11)
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    args.output.mkdir(parents=True, exist_ok=True)

    row_len = args.inst_len + args.resp_len
    tokens = rng.integers(1, args.vocab_size, size=args.rows * row_len, dtype=np.uint32)
    np.save(args.output / "tokens.npy", tokens)

    inst_start = np.arange(args.rows, dtype=np.uint64) * row_len
    resp_start = inst_start + args.inst_len
    inst_len = np.full(args.rows, args.inst_len, dtype=np.uint32)
    resp_len = np.full(args.rows, args.resp_len, dtype=np.uint32)

    for epoch in range(args.epochs):
        epoch_path = args.output / f"epoch_{epoch}"
        epoch_path.mkdir(exist_ok=True)
        order = rng.permutation(args.rows)
        np.save(epoch_path / "inst_start.npy", inst_start[order])
        np.save(epoch_path / "inst_len.npy", inst_len[order])
        np.save(epoch_path / "resp_start.npy", resp_start[order])
        np.save(epoch_path / "resp_len.npy", resp_len[order])

    metadata = {
        "tokenizer_info": {"vocab_size": args.vocab_size},
        "vocab_size": None,
        "max_seq_len": row_len + 1,
        "total_length": int(args.epochs * args.rows * (row_len - 1)),
    }
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Wrote tiny sampled dataset to {args.output}")


if __name__ == "__main__":
    main()
