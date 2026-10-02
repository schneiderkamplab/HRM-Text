"""Import finalized PL/IS train pairs, with full raw held-outs and prior DaLA screening."""
import argparse
import os
from pathlib import Path

from .dala_integrate import integrate
from .dala_swedish import pin_previous
from .dala_verify import verify
from .io import load, lock, write_json

LANGUAGES = ("pl", "is")


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--producer", type=Path, default=Path("/work/mimir/DaLA"))
    parser.add_argument("--output", type=Path, default=Path("data/dfm12/dala-pl-is-20260925-v1"))
    parser.add_argument("--previous", type=Path, default=Path("data/dfm12/dala-sv-20260924-v1"))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    producer, output, previous = (p.resolve() for p in (args.producer, args.output, args.previous))
    if not 1 <= args.workers <= 16:
        parser.error("workers must be 1..16")
    if output.is_relative_to(producer) or output.is_relative_to(previous):
        raise ValueError("Separate local import root required")
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "RAYON_NUM_THREADS"):
        os.environ[name] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    output.mkdir(parents=True, exist_ok=True)
    with lock(output / ".pl-is.lock"):
        previous_manifest = load(previous / "integration.json")
        previous_seed = load(previous / "previous-screen.json")
        prior_paths = previous_seed["inputs"]
        if previous_manifest["integrated_languages"] != ["sv"] or not any(
                set(load(path).get("integrated_languages", [])) == {"nb", "nn", "fo"}
                for path in prior_paths if Path(path).name == "integration.json"):
            raise ValueError("Require Swedish screen inheriting NB/NN/FO")
        seed = pin_previous(previous, output)
        integrate(producer, output, args.workers, LANGUAGES, seed, final_outputs=True)
        manifest = load(output / "integration.json")
        for component in manifest["components"]:
            component["evidence"].append(str(output / "previous-screen.json"))
        manifest["linguistic_review_complete"] = False
        write_json(output / "integration.json", manifest)
        verify(output, LANGUAGES)
        print("PL_IS_VERIFIED", output / "integration.json", flush=True)


if __name__ == "__main__":
    main()
