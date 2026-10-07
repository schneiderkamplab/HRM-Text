"""Read only completed receipts and report measured language/source coverage."""
import argparse
from collections import Counter, defaultdict
from pathlib import Path

from dfm12.io import load, write_json
from dfm14.catalog import LANGUAGES


def report(root):
    coverage = {language: dict(instruction_rows=0, document_rows=0, transforms=Counter(),
                instruction_sources=set(), grounding_sources=set()) for language in LANGUAGES}
    holds = Counter()
    retained = Counter()
    for receipt in root.glob("candidates/*/*/receipt.json"):
        data = load(receipt)
        source, counts = data["source"], data["counts"]
        retained["files"] += 1
        retained[source["kind"]] += sum(v for k, v in counts.items() if k.startswith("language:"))
        retained["transforms"] += sum(v for k, v in counts.items() if k.startswith("transform:"))
        for key, value in counts.items():
            if key.startswith(("needs_review:", "filtered:", "transform_hold:")):
                holds[key] += value
        for language in source["languages"]:
            if language not in coverage:
                continue
            entry = coverage[language]
            count = counts.get("language:" + language, 0)
            kind = "instruction" if source["kind"] == "instruction" else "document"
            entry[kind + "_rows"] += count
            if count:
                entry["instruction_sources" if kind == "instruction" else "grounding_sources"].add(source["repo"])
            if kind == "document":
                for task, number in counts.items():
                    if task.startswith("transform:"):
                        entry["transforms"][task.split(":",1)[1]] += number
    for entry in coverage.values():
        for key in ("instruction_sources", "grounding_sources"):
            entry[key] = sorted(entry[key])
    return dict(progress=load(root / "progress.json"), retained=dict(retained), languages=coverage,
                holds=dict(holds), training_ready=False, rows_are="unaudited bounded candidates, not full source sizes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/dfm14/cpu-preparation-v2"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = report(args.root)
    if args.output:
        write_json(args.output, result)
    progress = result["progress"]
    print(f"Historical pass: {progress['phase']}; current retained receipts: {result['retained']}")
    print("Language | Instruction rows | Instruction repos | Document rows | Grounding repos | Transform rows")
    for lang, row in result["languages"].items():
        print(f"{lang:2} | {row['instruction_rows']:8,} | {len(row['instruction_sources']):2} | {row['document_rows']:8,} | {len(row['grounding_sources']):2} | {sum(row['transforms'].values()):8,}")


if __name__ == "__main__":
    main()
