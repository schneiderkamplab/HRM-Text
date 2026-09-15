"""CPU-only attribution of saved probe gradient differences; no training writes."""
import json
import argparse
from pathlib import Path
import torch


def main():
    torch.set_num_threads(4)
    root = Path("logs/experiments/checkpoint_compile_xxl_619000")
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate")
    parser.add_argument("--reference", default="eager")
    args = parser.parse_args()
    results = {}
    pairs = [(args.reference, args.candidate)] if args.candidate else [("eager", "block_compiled"), ("baseline", "baseline_repeat")]
    for left, right in pairs:
        totals = {}
        for rank in range(8):
            a, b = [torch.load(root / arm / f"first_grad_rank{rank}.pt",
                               mmap=True, weights_only=True) for arm in (left, right)]
            assert a.keys() == b.keys()
            for key, x in a.items():
                y = b[key]
                assert x.shape == y.shape
                s = totals.setdefault(key, [0., 0., 0., 0.])
                s[0] += x.square().sum(dtype=torch.float64).item()
                s[1] += y.square().sum(dtype=torch.float64).item()
                s[2] += (x-y).square().sum(dtype=torch.float64).item()
                s[3] += (x*y).sum(dtype=torch.float64).item()
        total = [sum(s[i] for s in totals.values()) for i in range(4)]
        rows = [{"parameter": k, "relative_l2": (s[2]/s[0])**.5 if s[0] else None,
                 "difference_energy_fraction": s[2]/total[2] if total[2] else 0,
                 "reference_energy_fraction": s[0]/total[0]} for k,s in totals.items()]
        result = {"relative_l2": (total[2]/total[0])**.5,
                  "cosine": total[3]/(total[0]*total[1])**.5,
                  "parameters": sorted(rows, key=lambda r:r["difference_energy_fraction"], reverse=True)}
        results[f"{left}_vs_{right}"] = result
        print(left, right, json.dumps({**result, "parameters": result["parameters"][:8]}), flush=True)
    suffix = f"_{args.candidate}" if args.candidate else ""
    (root / f"gradient_attribution{suffix}.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
