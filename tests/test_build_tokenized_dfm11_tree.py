import json
from pathlib import Path

from scripts.build_tokenized_dfm11_tree import build_union


def make_root(root: Path, names: list[str], tokenizer_path: str) -> None:
    root.mkdir()
    (root / "tokenizer_info.json").write_text(json.dumps({
        "tokenizer_path": tokenizer_path,
        "chat_template_path": "data_io/chat_templates/gemma4_native_chat.jinja",
        "template_mode": "jinja_chat_template",
        "vocab_size": 262144,
    }))
    for name in names:
        task = root / name
        task.mkdir(parents=True)
        (task / "metadata.json").write_text("{}")


def test_union_replaces_only_selected_tool_sources(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tokenizer.json").write_text("{}")
    (tmp_path / "data_io/chat_templates").mkdir(parents=True)
    (tmp_path / "data_io/chat_templates/gemma4_native_chat.jinja").write_text("template")
    base, additions, output = tmp_path / "base", tmp_path / "additions", tmp_path / "output"
    make_root(base, [
        "glaive_native_tool_use__train",
        "nemotron_agentic__data__tool_calling",
        "nemotron_agentic__data__interactive_agent",
        "ordinary_task",
    ], str(tmp_path / "tokenizer.json"))
    make_root(
        additions,
        ["dfm11-glaive-native-tool-use-repaired__data__train"],
        str(tmp_path / "tokenizer.json"),
    )

    manifest = build_union(base, additions, output)

    assert manifest["counts"] == {"base_kept": 2, "base_replaced": 2, "additions": 1}
    assert not (output / "glaive_native_tool_use__train").exists()
    assert not (output / "nemotron_agentic__data__tool_calling").exists()
    assert (output / "nemotron_agentic__data__interactive_agent").is_symlink()
    assert (output / "ordinary_task").is_symlink()
    assert (output / "dfm11-glaive-native-tool-use-repaired__data__train").is_symlink()
