import pytest

from scripts.prepare_dfm10_hf_exports import (
    EXPORT_VERSION_METADATA,
    ExportSpec,
    PLANNED_UPLOAD_METADATA,
    SkippableRow,
    normalized_row,
)


SPEC = ExportSpec(
    "test-export",
    "data/test",
    ("*.jsonl",),
    ("example/source",),
    ("en",),
    "Test",
    "Test export.",
    "Test transformation.",
)


def test_empty_response_is_a_recorded_skip() -> None:
    with pytest.raises(SkippableRow, match="empty response") as exc_info:
        normalized_row(
            {"instruction": "Classify this.", "response": ""},
            SPEC,
            "train.parquet",
            7,
        )

    assert exc_info.value.reason == "empty_response"


def test_nonempty_instruction_row_is_preserved() -> None:
    row = normalized_row(
        {"instruction": "Classify this.", "response": "valid"},
        SPEC,
        "train.parquet",
        7,
    )

    assert row["messages"][-1] == {"role": "assistant", "content": "valid"}
    assert row["source"]["source_row"] == 7


def test_target_message_index_remains_a_tokenizer_control_field() -> None:
    row = normalized_row(
        {
            "messages": [
                {"role": "user", "content": "Run it."},
                {"role": "assistant", "content": "First."},
                {"role": "user", "content": "Again."},
                {"role": "assistant", "content": "Second."},
            ],
            "target_message_index": 3,
        },
        SPEC,
        "train.jsonl",
        9,
    )

    assert row["target_message_index"] == 3
    assert "target_message_index" not in row.get("metadata", {})


def test_native_replacements_have_versioned_export_lineage() -> None:
    terminal = EXPORT_VERSION_METADATA["dfm10-nemotron-terminal-sft"]
    dolci = EXPORT_VERSION_METADATA["dfm10-dolci-tool-use-repaired"]

    assert terminal["replaces_training_prefixes"] == [
        "nemotron_terminal_corpus__"
    ]
    assert "dolci_native_tool_use__" in dolci["replaces_training_prefixes"]
    assert terminal["training_rendering"]["max_seq_len"] == 4096
    assert "dfm10-nemotron-terminal-sft" in PLANNED_UPLOAD_METADATA


def test_all_policy_filtered_sapient_packages_have_planned_versions() -> None:
    names = {
        name
        for name in EXPORT_VERSION_METADATA
        if name.startswith("dfm10-sapient-") and name.endswith("-filtered-sft")
    }

    assert len(names) == 15
    assert names <= PLANNED_UPLOAD_METADATA.keys()
