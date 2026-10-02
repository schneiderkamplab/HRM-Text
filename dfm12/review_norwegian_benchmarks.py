"""Read-only source/split review; never changes admissions or running audits."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

import pyarrow.parquet as pq
from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.errors import GatedRepoError

from .io import write_json

ROOT = Path("data/dfm12/norwegian-benchmark-review-20260925")
REV = "701f7db6a51f0264a282ce1ff8e59580251b391e"


def norm(text):
    return " ".join(text.split())


def flattened(payload):
    return [{"context": p["context"], "question": q["question"]}
            for a in payload["data"] for p in a["paragraphs"] for q in p["qas"]
            if not q.get("is_impossible") and q.get("answers")]


def compare(train, reference):
    contexts = {norm(r["context"]) for r in reference}
    questions = {norm(r["question"]) for r in reference}
    pairs = {(norm(r["context"]), norm(r["question"])) for r in reference}
    return {"reference_rows": len(reference),
            "train_question_matches": sum(norm(r["question"]) in questions for r in train),
            "train_context_matches": sum(norm(r["context"]) in contexts for r in train),
            "train_context_question_matches": sum((norm(r["context"]), norm(r["question"])) in pairs for r in train)}


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    evidence = []

    def fetch(url, name):
        with urlopen(url, timeout=90) as response:
            raw = response.read()
        path = ROOT / name
        path.write_bytes(raw)
        evidence.append({"url": url, "path": str(path), "sha256": hashlib.sha256(raw).hexdigest()})
        return raw

    def hf(repo, revision, file):
        path = hf_hub_download(repo, file, repo_type="dataset", revision=revision, cache_dir=ROOT / "hf-cache")
        evidence.append({"repo": repo, "revision": revision, "file": file,
                         "path": path, "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()})
        return path

    base = f"https://raw.githubusercontent.com/ltgoslo/norquad/{REV}/data/evaluation/"
    train = flattened(json.loads(fetch(base + "wiki/training_dataset_flattened.json", "norquad-wiki-train.json")))
    results = {"norquad_train_rows": len(train), "norquad_comparisons": {}}
    heldout = []
    for split in ("validation", "test"):
        ref = flattened(json.loads(fetch(base + f"all/{split}_dataset_flattened.json", f"norquad-all-{split}.json")))
        heldout.extend(ref)
        results["norquad_comparisons"]["original_all_" + split] = compare(train, ref)
    results["norquad_comparisons"]["original_heldout_union"] = compare(train, heldout)
    contexts = {norm(r["context"]) for r in heldout}
    questions = {norm(r["question"]) for r in heldout}
    results["norquad_passage_question_disjoint_candidates"] = sum(
        norm(r["context"]) not in contexts and norm(r["question"]) not in questions for r in train)
    api = HfApi()
    info = api.dataset_info("ltg/norquad")
    for split in ("validation", "test"):
        rows = []
        for item in info.siblings:
            if item.rfilename.startswith("data/" + split + "-") and item.rfilename.endswith(".parquet"):
                rows.extend(pq.read_table(hf(info.id, info.sha, item.rfilename)).to_pylist())
        results["norquad_comparisons"]["hf_" + split] = compare(train, rows)

    composite = "danish-foundation-models/norwegian-dyna-instruct"
    revision = "b7ea572dd64aa5d052e0086b57ad90da162db7d6"
    file = "data/fleurs-alpaca-en-no/fleurs-alpaca-en-no.parquet"
    rows = pq.read_table(hf(composite, revision, file)).to_pylist()
    english = [norm(row["messages"][0]["content"].split("\n\n", 1)[1]) for row in rows]
    flores = api.dataset_info("openlanguagedata/flores_plus")
    results["fleurs_rows"] = len(rows)
    results["fleurs_flores_plus_matches"] = {}
    for split in ("dev", "devtest"):
        try:
            path = hf(flores.id, flores.sha, f"{split}/eng_Latn.jsonl")
        except GatedRepoError:
            results["fleurs_flores_plus_matches"][split] = {"status": "gated_403_not_checked"}
            continue
        records = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
        text = {norm(r["text"]) for r in records}
        noquotes = {s.replace('"', '') for s in text}
        results["fleurs_flores_plus_matches"][split] = {
            "reference_rows": len(records), "exact": sum(s in text for s in english),
            "exact_or_ascii_quotes_removed": sum(s in text or s in noquotes for s in english)}
    results.update(evidence=evidence, admission_changed=False,
                   limitations="Exact whitespace-normalized matches only. EuroEval/norquad-mini unavailable (404); no full-suite or semantic clearance.")
    write_json(ROOT / "review.json", results)
    print(json.dumps({k: v for k, v in results.items() if k != "evidence"}, indent=2))


if __name__ == "__main__":
    main()
