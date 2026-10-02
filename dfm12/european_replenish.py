"""Fill CPU transformation candidate margins without relaxing language or rights gates."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import math
import os
from pathlib import Path
import time

from .european_expansion import ROOT
from .io import file_hash, load, lock, write_json
from .prepare import Renderer, prepare_transforms


def options(name):
    return dict(window_samples=32 if name == "text-pt_pt" else 1,
                window_chars=4000 if name == "text-pt_pt" else 8000, reserve_factor=3)


def replenish(root, name):
    cfg = load(root / "config.json")
    baseline = load(root / "baselines.json")
    path = root / "candidates" / name / "receipt.json"
    marker = root / "text-replenishment" / (name + ".json")
    while not path.exists():
        from .european_screen import producer_running
        if not producer_running(root):
            raise ValueError("No completed candidates or active producer for " + name)
        time.sleep(30)
    while True:
        try:
            with lock(root / "workers" / (name + ".lock")):
                receipt = load(path)
                if marker.exists():
                    if load(marker)["sha256"] != receipt["sha256"]:
                        raise ValueError("Finalized transformation candidates changed")
                    return load(marker)
                if (root / "screened/candidates" / name / "receipt.json").exists():
                    raise ValueError("Already screened: do not replace inputs behind the audit queue")
                lang = cfg["sources"][name]["language"]
                needed = {task: math.ceil(item["target_per_language"] * 1.5) for task, item in baseline["tasks"].items()}
                if any(receipt["counts"].get(lang + "/" + task, 0) < count for task, count in needed.items()):
                    write_json(root / "text-replenishment/before" / (name + ".json"), receipt)
                    write_json(root / "progress" / (name + ".json"), dict(state="replenishing", source=name, options=options(name)))
                    print("REPLENISH", name, options(name), flush=True)
                    renderer = Renderer(load("data/sampled_dfm11/metadata.json")["tokenizer_info"], cfg["max_seq_len"])
                    receipt = prepare_transforms(root, name, baseline, cfg, renderer, **options(name))
                if file_hash(path.parent / "candidates.jsonl") != receipt["sha256"]:
                    raise ValueError("Transformation candidate checksum mismatch")
                shortages = {task: count - receipt["counts"].get(lang + "/" + task, 0) for task, count in needed.items()
                             if receipt["counts"].get(lang + "/" + task, 0) < count}
                result = dict(sha256=receipt["sha256"], counts=receipt["counts"], candidate_shortfalls=shortages,
                              audit_pending=True, accepted=False)
                write_json(root / "progress" / (name + ".json"), dict(state="candidates_ready", **result))
                write_json(marker, result)
                return result
        except BlockingIOError:
            time.sleep(10)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        parser.error("workers must be 1..16")
    os.environ.update(CUDA_VISIBLE_DEVICES="", TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="1")
    cfg = load(args.root / "config.json")
    names = [n for n, s in cfg["sources"].items() if s["kind"] == "documents"]
    with lock(args.root / "text-replenishment/.lock"):
        write_json(args.root / "text-replenishment/policy.json", dict(components=names, candidate_factor=1.5,
                   language_and_license_filters="unchanged", options={name: options(name) for name in names}))
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(replenish, args.root, name): name for name in names}
            failures = []
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result = future.result()
                    print("FINALIZED", name, result, flush=True)
                except Exception as exc:
                    failures.append(dict(source=name, error=str(exc)))
                    print("FAILED", name, repr(exc), flush=True)
            write_json(args.root / "text-replenishment/completion.json", dict(failures=failures, complete=not failures))


if __name__ == "__main__":
    main()
