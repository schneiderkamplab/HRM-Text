from scripts.build_tokenized_dfm10_tree import (
    REPLACEMENT_SOURCES,
    is_replaced_base_task,
    normalized_tokenizer_info,
)


def test_tokenizer_info_normalizes_repo_relative_paths(tmp_path) -> None:
    import json

    relative = tmp_path / "relative.json"
    absolute = tmp_path / "absolute.json"
    template = "data_io/chat_templates/gemma4_native_chat.jinja"
    common = {
        "tokenizer_path": "/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json",
        "vocab_size": 262144,
    }
    relative.write_text(json.dumps({**common, "chat_template_path": template}))
    absolute.write_text(
        json.dumps({**common, "chat_template_path": f"/work/dfm/HRM-Text/{template}"})
    )
    assert normalized_tokenizer_info(relative) == normalized_tokenizer_info(absolute)


def test_native_dfm10_replacements_cover_legacy_terminal_and_dolci() -> None:
    replaced = (
        "nemotron_terminal_corpus__data__swe.parquet",
        "dolci_instruct_sft_tool_use__data__train-00000.parquet",
        "dolci_instruct_sft_tool_use_sa__data__train.jsonl",
        "dolci_native_tool_use__data__train.jsonl",
    )

    assert all(is_replaced_base_task(name) for name in replaced)
    assert REPLACEMENT_SOURCES["nemotron_terminal_corpus__"] == (
        "nemotron_terminal_native"
    )
    assert all(
        REPLACEMENT_SOURCES[prefix] == "dolci_tool_use_repaired"
        for prefix in REPLACEMENT_SOURCES
        if prefix.startswith("dolci_")
    )


def test_unrelated_dolci_instruction_data_is_retained() -> None:
    assert not is_replaced_base_task("dolci_instruct_sft__data__train.parquet")
    assert not is_replaced_base_task(
        "dolci_instruct_sft_no_tools__data__train.parquet"
    )
