"""Fail-closed adapter for the pinned Scandi translated mixture."""
from .io import digest
from .records import validate_messages

REPO = "V4ldeLund/scandi-translated-instruct"
REVISION = "5da16f97d23330fd029fec4462140433f65295d7"
FILES = tuple(f"data/train-{i:05d}-of-00004.parquet" for i in range(4))
PINS = {
    REPO: REVISION,
    "akoksal/muri-it-language-split": "4987fc82a54145caf778efec6a682863591be1f2",
    "CohereLabs/aya_collection_language_split": "a3af2fde4b4cb5b2775830b11244a1a20b5f004f",
    "neph1/Alpaca-Lora-GPT4-Swedish-Refined": "5dbae8fe27b8e8b1a69810b7a4aeb635d4461c37",
    "V4ldeLund/da-translated-instruct": "ff73bcd22072bc01866cf3fe066744330abbf9c6",
}


def validate_pin(source):
    if (source.get("repo"), source.get("revision"), tuple(source.get("files", []))) != (REPO, REVISION, FILES):
        raise ValueError("source_pin_or_manifest_changed")


def review_reason(row):
    if row.get("language") not in ("nb", "nn", "sv"):
        return "outside_requested_languages"
    source = row.get("source", "").split("/")[-1]
    if source == "aya_collection_language_split":
        return "aya_constituent_rights_attribution_and_split_hold"
    if source == "Alpaca-Lora-GPT4-Swedish-Refined":
        return "alpaca_unspecified_license_hold"
    if source == "muri-it-language-split":
        if row["language"] in ("nb", "nn"):
            return "muri_generic_nor_variant_and_constituent_rights_hold"
        return "muri_constituent_rights_attribution_and_split_hold"
    return "unreviewed_constituent"


def preserve(row, relative, ordinal):
    """Lossless chat projection for review, never an eligibility override."""
    validate_messages(row.get("messages"))
    for message in row["messages"]:
        if any(message.get(k) for k in ("function_call", "tool_call_id", "tools")):
            raise ValueError("tool_metadata")
    provenance = {"repo": REPO, "revision": REVISION, "file": relative,
                  "ordinal": ordinal, "release_split": "train",
                  "original_split": "unknown",
                  "source_metadata": {k: v for k, v in row.items() if k != "messages"}}
    return {"id": digest(provenance), "messages": row["messages"],
            "language": row.get("language"), "provenance": provenance,
            "audit_status": "unaudited", "accepted": False}
