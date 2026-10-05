"""Pin the ten reviewed automated keeps and verify their exact inserted sources."""
import hashlib
import json
from pathlib import Path

root = Path("data/dfm13/gemma31-balanced-execution-20261003-v2/baltic")
out = Path(__file__).resolve().parent
families = {"grounded-instruct", "summary-rewrite", "multiturn"}
specs = json.loads((root / "specifications.json").read_text())
files = {root / "specifications.json", root / "manifest.json",
         out / "balanced-accepted-review.md"}
rows = []
for path in sorted((root / "outcomes").glob("*.json")):
    outcome = json.loads(path.read_text())
    if not outcome.get("effective_keep") or outcome["family"] not in families:
        continue
    spec, = [s for s in specs if (s["language_code"], s["family"], s["slot"]) ==
             (outcome["language"], outcome["family"], outcome["slot"])]
    candidate_path = root / "candidates" / path.name
    candidate = json.loads(candidate_path.read_text())
    source = spec["source"]["text"]
    assert source in candidate["messages"][0]["content"]
    sha = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    assert sha == outcome["independent_candidate_sha256"]
    files.update((path, candidate_path))
    files.update((root / "requests").glob(outcome["id"] + "-*.json"))
    rows.append({"id": outcome["id"], "language": outcome["language"],
                 "family": outcome["family"], "candidate_sha256": sha,
                 "source_text_sha256": hashlib.sha256(source.encode()).hexdigest(),
                 "source_document_id": spec["source"]["source_document_id"],
                 "source_inserted_exactly": True,
                 "assistant_turns": sum(m["role"] == "assistant" for m in candidate["messages"])})
assert len(rows) == 10
assert sum(r["assistant_turns"] for r in rows) == 18
payload = {"rows": rows, "admission_authorized": False,
           "manual_counts": {"good": 6, "partial": 3, "prompt_framing_concern": 1},
           "sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}}
with (out / "balanced-pins.json").open("x") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
print("Verified 10 candidate hashes and exact source insertions; 18 assistant turns")
