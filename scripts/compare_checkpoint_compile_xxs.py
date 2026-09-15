"""Compare the saved CPU gradient shards and XXS smoke summaries."""
import json
import argparse
from pathlib import Path
import re
import statistics

import torch


def main():
    torch.set_num_threads(1)
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1] / "logs/experiments/checkpoint_compile_xxs")
    parser.add_argument("--ranks", type=int, default=2)
    parser.add_argument("--candidate", default="block_compiled")
    parser.add_argument("--reference", default="eager")
    args = parser.parse_args()
    root = args.root
    candidate = args.candidate
    reference = args.reference
    summaries = {m: json.loads((root / m / "summary.json").read_text())
                 for m in (reference, candidate)}
    result = {"arms": {}}
    for mode, summary in summaries.items():
        log = (root / mode / "train.log").read_text()
        result["arms"][mode] = {
            "median_seconds": summary["median_step_seconds"],
            "mean_seconds": summary["mean_step_seconds"],
            "all_step_seconds": summary["all_step_seconds"],
            "losses": [r["train/loss"] for r in summary["metric_history"]],
            "grad_norms": [r["train/grad_norm"] for r in summary["metric_history"]],
            "peak_allocated_mib": max(map(float, re.findall(r"max_allocated=([\d.]+)", log))),
            "peak_reserved_mib": max(map(float, re.findall(r"max_reserved=([\d.]+)", log))),
        }
    diff2, ref2, dot, candidate2 = 0., 0., 0., 0.
    maximum = 0.
    tensors = 0
    for rank in range(args.ranks):
        a = torch.load(root / reference / f"first_grad_rank{rank}.pt", mmap=True, weights_only=True)
        b = torch.load(root / candidate / f"first_grad_rank{rank}.pt", mmap=True, weights_only=True)
        assert a.keys() == b.keys()
        for key in a:
            x, y = a[key], b[key]
            assert x.shape == y.shape
            assert torch.isfinite(x).all() and torch.isfinite(y).all()
            difference = x - y
            diff2 += difference.square().sum(dtype=torch.float64).item()
            ref2 += x.square().sum(dtype=torch.float64).item()
            candidate2 += y.square().sum(dtype=torch.float64).item()
            dot += (x * y).sum(dtype=torch.float64).item()
            maximum = max(maximum, difference.abs().max().item())
            tensors += 1
    result["first_step_post_clip_gradient"] = {
        "local_tensors_compared": tensors, "relative_l2_error": (diff2 / ref2) ** .5,
        "cosine_similarity": dot / (ref2 * candidate2) ** .5,
        "max_absolute_difference": maximum,
    }
    assert len(result["arms"][reference]["losses"]) == len(result["arms"][candidate]["losses"])
    result["max_loss_difference"] = max(abs(x-y) for x, y in zip(
        result["arms"][reference]["losses"], result["arms"][candidate]["losses"]))
    histories = [summaries[m]["metric_history"] for m in (reference, candidate)]
    assert [r["step"] for r in histories[0]] == [r["step"] for r in histories[1]]
    result["metrics"] = {}
    for key in ("train/loss", "train/accuracy", "train/exact_accuracy", "train/grad_norm"):
        values = [[r[key] for r in rows] for rows in histories]
        result["metrics"][key] = {
            "reference_mean": statistics.mean(values[0]),
            "candidate_mean": statistics.mean(values[1]),
            "max_absolute_difference": max(abs(a-b) for a,b in zip(*values)),
        }
    assert all(a[k] == b[k] for a,b in zip(*histories)
               for k in a if k.startswith("train/lr")), "Learning rates differ"
    for mode in (reference, candidate):
        result["arms"][mode]["last25_median_seconds"] = statistics.median(summaries[mode]["all_step_seconds"][-25:])
        result["arms"][mode]["state_fingerprint"] = summaries[mode]["state_fingerprint"]
    if (root / reference / "batch_audit_rank0.jsonl").exists():
        count = 0
        for rank in range(args.ranks):
            streams = []
            for mode in (reference, candidate):
                rows = [json.loads(line) for line in (root / mode / f"batch_audit_rank{rank}.jsonl").read_text().splitlines()]
                for row in rows:
                    row.pop("effective_gas")
                streams.append(rows)
            assert streams[0] == streams[1], f"Input mismatch on rank {rank}"
            count += len(streams[0])
        result["matched_rank_updates"] = count
    filename = "comparison.json" if candidate == "block_compiled" else f"comparison_{candidate}.json"
    (root / filename).write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
