"""Freeze file hashes for this read-only 12-case review, without touching inputs."""
import hashlib
import json
from pathlib import Path

root = Path("data/dfm13/baltic/gemma31-fresh-comparison12-v3")
report = Path(__file__).resolve().parent
files = {root / name for name in ("manifest.json", "pairs.json", "specifications.json")}
for folder in ("candidates", "outcomes", "requests", "raw"):
    files.update((root / folder).glob("*.json"))
for pair in json.loads((root / "pairs.json").read_text()):
    old = Path("data/dfm13/baltic/production-probe-coherence")
    files.add(old / "outcomes" / (pair["id"] + ".json"))
    if pair["baseline_candidate"]:
        files.add(Path(pair["baseline_candidate"]))
files.add(old / "raw/3099bf2bafe44e0290eeea7db22167d7-000003.response.json")
files.add(report / "report.md")
payload = {"scope": "12 complete paired source cases, diagnostic only",
           "manual_counts": {"good": 2, "partial": 4, "defective": 6},
           "admission_authorized": False,
           "sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted(files)}}
with (report / "pins.json").open("x") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
print(f"Pinned {len(files)} files")
