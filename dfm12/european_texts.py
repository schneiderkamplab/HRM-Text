"""Source-specific document screening before the shared transformation sampler."""
from urllib.parse import urlparse
import math


def corege_allowed(row):
    if any(str(row.get(k)).lower() != "true" for k in ("pt.auto", "pt.pt.auto")):
        return False
    for key in ("pt.mean.confidence.auto", "pt.pt.mean.confidence.auto"):
        try:
            confidence = float(row[key])
        except (KeyError, TypeError, ValueError):
            return False
        if not math.isfinite(confidence) or not .8 <= confidence <= 1:
            return False
    url = urlparse(str(row.get("dc.rights.uri", "")).strip())
    if url.hostname not in {"creativecommons.org", "www.creativecommons.org"}:
        return False
    parts = url.path.strip("/").split("/")
    return (len(parts) >= 3 and parts[0] == "licenses" and
            parts[1] in {"by", "by-sa", "by-nc", "by-nc-sa"} and
            parts[2] in {"1.0", "2.0", "2.5", "3.0", "4.0"}) or url.path.startswith("/publicdomain/zero/1.0/")


def approve_corege(root):
    from .io import load, write_json, lock
    source = load(root / "sources.lock.json")["sources"]["text-pt_pt"]
    with lock(root / ".catalog.lock"):
        write_json(root / "approvals/text-pt_pt.json", dict(revision=source["revision"],
            files=source["files"], document_filter="corege_pt",
            evidence="2026-09-26 card and schema checked. Preparation ONLY: require pt.auto and pt.pt.auto true, both confidences >=0.8, explicit CC URI permitting adaptations. Missing/ND rights excluded. Independent window language/quality audit remains required.",
            source_card=f"https://huggingface.co/datasets/{source['repo']}/blob/{source['revision']}/README.md"))
