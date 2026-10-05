"""Read-only local coverage and bounded ordinary HTTP checks; never publishes."""
import collections
import hashlib
import json
from pathlib import Path
import re
import zipfile

import requests

ROOT = Path(__file__).resolve().parent


def main():
    out = ROOT / "europarl-sitting-links"
    out.mkdir(exist_ok=False)
    archive_receipt = json.loads((ROOT / "evidence-europarl/receipt.json").read_text())
    report = {"publication_authorized": False, "languages": {}, "http_checks": []}
    for lang in ("lt", "lv"):
        path = Path(f"data/dfm13/baltic/audit-ready/transform-Europarl_{lang}/candidates.jsonl")
        counts = collections.Counter()
        sha = hashlib.sha256()
        with path.open("rb") as handle:
            for line in handle:
                sha.update(line)
                row = json.loads(line)
                if row["task"] == "prefix-continuation":
                    counts[row["provenance"]["source_document_id"]] += 1
        members = collections.defaultdict(list)
        with zipfile.ZipFile(archive_receipt["archives"][lang]["path"]) as archive:
            for name in archive.namelist():
                match = re.search(r"ep-(\d{2}-\d{2}-\d{2})-.*\.xml$", name)
                if match:
                    members[match[1]].append(name)
        rows = [{"sitting_id": date, "prefix_candidates": count,
                 "archive_members": sorted(members[date]),
                 "official_per_sitting_link": None,
                 "official_link_status": "unverified_not_cleared_for_release"}
                for date, count in sorted(counts.items())]
        (out / f"{lang}-sittings.json").write_text(json.dumps(rows, indent=2) + "\n")
        report["languages"][lang] = {
            "candidate_path": str(path), "candidate_sha256": sha.hexdigest(),
            "prefix_candidates_not_accepted_count": sum(counts.values()),
            "sittings": len(counts),
            "sittings_without_archive_members": [r["sitting_id"] for r in rows if not r["archive_members"]],
            "archive_pin": archive_receipt["archives"][lang],
        }
    # These are provisional URL constructions, not verified official references.
    # One ordinary GET per language, no retries or challenge bypass.
    for lang, term, date in (("LT", 7, "2010-11-22"), ("LV", 6, "2008-06-04")):
        url = f"https://www.europarl.europa.eu/doceo/document/CRE-{term}-{date}_{lang}.html"
        item = {"requested_url": url, "url_provenance": "inferred_unverified"}
        try:
            response = requests.get(url, timeout=30)
            body = response.content
            (out / f"http-{lang.lower()}.body").write_bytes(body)
            item.update(status=response.status_code, final_url=response.url,
                        bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                        content_type=response.headers.get("Content-Type"),
                        verified=False)
        except requests.RequestException as exc:
            item.update(error=str(exc), verified=False)
        report["http_checks"].append(item)
    report["conclusion"] = "Local archive membership is not verification of official sitting links or item-specific rights. No publication."
    (out / "receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
