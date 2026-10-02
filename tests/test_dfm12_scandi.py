from copy import deepcopy

import pytest

from dfm12.records import chat_fingerprint
from dfm12.scandi import FILES, REPO, REVISION, preserve, review_reason, validate_pin


def row(source="muri-it-language-split", language="sv"):
    return {"source": source, "language": language, "model": "Mixtral-8x7B",
            "messages": [{"role": "user", "content": "Question"},
                         {"role": "assistant", "content": "Answer"}]}


@pytest.mark.parametrize("source,language,reason", [
    ("aya_collection_language_split", "nn", "aya_constituent_rights_attribution_and_split_hold"),
    ("CohereLabs/aya_collection_language_split", "nb", "aya_constituent_rights_attribution_and_split_hold"),
    ("Alpaca-Lora-GPT4-Swedish-Refined", "sv", "alpaca_unspecified_license_hold"),
    ("muri-it-language-split", "sv", "muri_constituent_rights_attribution_and_split_hold"),
    ("muri-it-language-split", "nb", "muri_generic_nor_variant_and_constituent_rights_hold"),
    ("muri-it-language-split", "nn", "muri_generic_nor_variant_and_constituent_rights_hold"),
    ("muri-it-language-split", "no", "outside_requested_languages"),
    ("muri-it-language-split", "nor", "outside_requested_languages"),
    ("aya_collection_language_split", "da", "outside_requested_languages"),
    ("unknown", "sv", "unreviewed_constituent"),
])
def test_no_blanket_authorization(source, language, reason):
    value = row(source, language)
    value["license_authorization"] = "all DynaWord/DynaInstruct"
    assert review_reason(value) == reason


def test_multiturn_and_attribution_are_preserved():
    value = row()
    value["messages"] *= 2
    before = deepcopy(value)
    result = preserve(value, "data/train.parquet", 13)
    assert value == before
    assert result["messages"] == before["messages"]
    assert result["provenance"]["source_metadata"]["model"] == "Mixtral-8x7B"
    assert result["provenance"]["revision"] == REVISION
    assert result["provenance"]["original_split"] == "unknown"
    assert result["accepted"] is False
    assert result["audit_status"] == "unaudited"
    assert result["id"] != preserve(value, "data/train.parquet", 14)["id"]


@pytest.mark.parametrize("messages", [[], [{"role": "user", "content": "x"}],
    [{"role": "assistant", "content": "x"}, {"role": "user", "content": "y"}],
    [{"role": "user", "content": ""}, {"role": "assistant", "content": "y"}],
    [{"role": "user", "content": "x"}, {"role": "assistant", "content": "[INST]"}],
    [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y", "function_call": {"name": "f"}}],
])
def test_invalid_chats(messages):
    value = row()
    value["messages"] = messages
    with pytest.raises(ValueError):
        preserve(value, "data/train.parquet", 0)


def test_dedup_preserves_role_and_turn_boundaries():
    a = row()["messages"]
    b = deepcopy(a)
    b[0]["content"] = "  Question\n"
    assert chat_fingerprint(a) == chat_fingerprint(b)
    assert chat_fingerprint(a) != chat_fingerprint(a * 2)
    b[0]["role"] = "system"
    assert chat_fingerprint(a) != chat_fingerprint(b)


@pytest.mark.parametrize("key,value", [("repo", "other/repo"), ("revision", "main"),
                                      ("files", FILES[:-1]), ("files", FILES + ("extra.parquet",))])
def test_pin_and_complete_manifest_required(key, value):
    source = {"repo": REPO, "revision": REVISION, "files": FILES}
    validate_pin(source)
    source[key] = value
    with pytest.raises(ValueError, match="source_pin_or_manifest_changed"):
        validate_pin(source)
