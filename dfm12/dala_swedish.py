"""Completed Swedish-only CPU import; never changes producer or prior imports."""
import argparse
import os
from pathlib import Path
import sqlite3

from .dala_integrate import integrate
from .dala_verify import verify
from .io import file_hash, load, lock, write_json


def pin_previous(previous, output):
    proof = load(previous / "verification.json")
    if (proof["status"] != "verified_unaudited" or
            proof["integration_sha256"] != file_hash(previous / "integration.json")):
        raise ValueError("Previous DaLA integration is not verified")
    paths = [previous / p for p in ("integration.json", "verification.json", "screening.json", "screening.sqlite", "inputs.json")]
    if (previous / "previous-screen.json").exists():
        paths.append(previous / "previous-screen.json")
    pins = {str(p): file_hash(p) for p in paths}
    receipt = output / "previous-screen.json"
    seed = output / "previous-screen.sqlite"
    if receipt.exists():
        old = load(receipt)
        if old["inputs"] != pins or file_hash(seed) != old["seed_sha256"]:
            raise ValueError("Pinned previous screen changed")
    else:
        with sqlite3.connect((previous / "screening.sqlite").as_uri() + "?mode=ro", uri=True) as source:
            with sqlite3.connect(seed) as dest:
                source.backup(dest)
        if pins != {str(p): file_hash(p) for p in paths}:
            raise ValueError("Previous screen changed during snapshot")
        write_json(receipt, {"inputs": pins, "seed": str(seed), "seed_sha256": file_hash(seed),
                            "scope": "Completed previous DaLA train texts and full raw held-out texts/documents, including inherited seed",
                            "previous_integration_languages": load(previous / "integration.json")["integrated_languages"]})
    return seed


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/dfm12/dala-sv-20260924-v1"))
    parser.add_argument("--producer", type=Path, default=Path("/work/mimir/DaLA"))
    parser.add_argument("--previous", type=Path, default=Path("data/dfm12/dala-nb-nn-fo-20260924-v1"))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        parser.error("workers must be 1..16")
    output, producer, previous = args.output.resolve(), args.producer.resolve(), args.previous.resolve()
    if output.is_relative_to(producer) or output == previous or output.is_relative_to(previous):
        raise ValueError("Separate local output required")
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "RAYON_NUM_THREADS"):
        os.environ[name] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    output.mkdir(parents=True, exist_ok=True)
    with lock(output / ".swedish.lock"):
        seed = pin_previous(previous, output)
        integrate(producer, output, args.workers, languages=("sv",), seed=seed)
        manifest = load(output / "integration.json")
        for component in manifest["components"]:
            component["evidence"].append(str(output / "previous-screen.json"))
        write_json(output / "integration.json", manifest)
        verify(output, languages=("sv",))
        print("SWEDISH_VERIFIED", output / "integration.json", flush=True)


if __name__ == "__main__":
    main()
