"""Scoped Scandi preparation authorization, not a license or quality grant."""
from .io import digest
from .records import chat_fingerprint, validate_messages
from .scandi import FILES, PINS, REPO, REVISION, preserve

POLICY = "user_include_whole_pinned_scandi_20260925_v1"
AUTHORIZATION = {
    "policy": POLICY, "repo": REPO, "revision": REVISION,
    "request": "Include pinned whole Scandi release NB NN SV DA; blank MURI nor becomes generic no. Retain known MURI heldout/source overlaps as annotations; exact dedup and quality audit remain required.",
    "languages": ["da", "nb", "nn", "sv", "no"],
    "license_grant": False, "quality_acceptance": False,
    "known_muri_heldout_policy": "annotate_not_exclude",
    "upload_or_sampling_authorized": False,
}
AUTHORIZATION_SHA256 = digest(AUTHORIZATION)
MURI = "akoksal/muri-it-language-split"


def authorized_record(record):
    p = record.get("provenance", {})
    return (p.get("repo") == REPO and p.get("revision") == REVISION
            and p.get("file") in FILES and type(p.get("ordinal")) is int
            and p["ordinal"] >= 0 and p.get("admission_policy") == POLICY
            and p.get("authorization_sha256") == AUTHORIZATION_SHA256)


def valid_lineage(record, match):
    """A runner-verified upstream pointer bound to the complete original chat."""
    return (isinstance(match, dict) and match.get("revision") == PINS[MURI]
            and match.get("language") in {"nor", "swe"}
            and match.get("split") in {"train", "validation", "test"}
            and match.get("file") == f"{match['language']}/{match['split']}-00000-of-00001.parquet"
            and type(match.get("ordinal")) is int and match["ordinal"] >= 0
            and match.get("messages_sha256") == digest(record.get("messages"))
            and match.get("match_method") == "exact_original_messages")


def authorized_language(record):
    """Boolean exception for generic no only; ordinary language gates stay intact."""
    if not authorized_record(record) or record.get("language") != "no":
        return False
    p = record["provenance"]
    messages = record.get("messages", [])
    matches = p.get("muri_lineage", [])
    try:
        validate_messages(messages)
    except ValueError:
        return False
    return (p.get("source_metadata", {}).get("source") == "muri-it-language-split"
            and p.get("source_metadata", {}).get("language") == ""
            and record.get("norwegian_standard") == "unknown"
            and record.get("message_languages") == ["no"] * len(messages)
            and bool(matches) and all(valid_lineage(record, m) and m["language"] == "nor" for m in matches))


def authorized_muri_heldout(record):
    """Known pinned MURI overlaps only, including the recorded whitespace alias."""
    if (not authorized_record(record)
            or record.get("provenance", {}).get("source_metadata", {}).get("source") != "muri-it-language-split"):
        return False
    matches = [m for m in record.get("provenance", {}).get("muri_lineage", []) if valid_lineage(record, m)]
    if any(m["split"] in {"validation", "test"} for m in matches):
        return True
    overlap = record.get("audit_context", {}).get("frozen_overlap", {})
    if not matches or overlap.get("chat_sha256") != chat_fingerprint(record["messages"]):
        return False
    # Source snapshots pin the frozen overlap ledger. Require an exact original
    # MURI lineage too; an arbitrary caller-supplied heldout label is not enough.
    allowed = {f"heldout:muri:{m['language']}:{split}" for m in matches for split in ("test", "validation")}
    return any(c.get("scope") == "heldout" and c.get("component") in allowed
               for c in overlap.get("components", []))


def adapt(row, relative, ordinal, matches):
    result = preserve(row, relative, ordinal)
    p = result["provenance"]
    p.update(admission_policy=POLICY, authorization_sha256=AUTHORIZATION_SHA256,
             constituent=row["source"], split="train", muri_lineage=matches)
    p["original_split"] = sorted({m["split"] for m in matches}) or "unknown"
    p["original_tasks"] = [{k: m.get(k) for k in ("dataset_name", "subdataset_name")} for m in matches]
    result["task"] = "instruction"
    if result["language"] == "":
        result.update(language="no", norwegian_standard="unknown",
                      message_languages=["no"] * len(result["messages"]))
        if not authorized_language(result):
            raise ValueError("blank_language_without_exact_nor_lineage")
    elif result["language"] not in {"da", "nb", "nn", "sv"}:
        raise ValueError("unsupported_scandi_language")
    result["audit_context"] = {
        "admission_policy": POLICY, "known_muri_heldout": authorized_muri_heldout(result),
        "benchmark_clearance": False, "license_grant": False,
        "review_required": ["actual_language_and_variant", "translation_quality", "answer_correctness", "training_usefulness"],
        "declared_language_not_verified": True,
        "original_task_split_unknown": not bool(matches),
        "chat_sha256": chat_fingerprint(result["messages"]),
    }
    return result


def exact_key(record):
    """Training semantics: do not normalize text or ignore target/tool metadata."""
    return digest({k: v for k, v in record.items() if k not in {
        "id", "provenance", "audit_context", "rendered_tokens", "audit_status", "accepted"}})
