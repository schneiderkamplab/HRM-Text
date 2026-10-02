import copy
import json
from pathlib import Path

import pytest

from dfm12.polish import adapt, rendered_count
from dfm12.polish_prepare import inherited_overlap
from dfm12.records import chat_fingerprint


def pair():
    history = [{"role": "user", "content": "Pytanie pierwsze"},
               {"role": "assistant", "content": "Odpowiedz pierwsza"},
               {"role": "user", "content": "Pytanie drugie"}]
    return {"id": "123_1_0", "chosen": history + [{"role": "assistant", "content": "Dobra odpowiedz"}],
            "rejected": history + [{"role": "assistant", "content": "Zla odpowiedz"}]}


def test_full_context_final_target_and_metadata_isolation():
    row = pair()
    original = copy.deepcopy(row)
    result = adapt("pllum-align", row, "dialogs.jsonl", 0)
    assert row == original
    assert result["messages"] == row["chosen"]
    assert result["target_message_index"] == 3
    assert "rejected" not in result and "rejected" not in result["provenance"]["source_metadata"]
    assert all(set(m) == {"role", "content"} for m in result["messages"])


@pytest.mark.parametrize("source_id,reason", [("identity_general_1", "identity_category"),
    ("polqa_1", "benchmark_or_inherited_provenance_hold"),
    ("toxigen_1", "benchmark_or_inherited_provenance_hold"),
    ("antropic_1", "benchmark_or_inherited_provenance_hold"),
    ("neut-nonpl_1", "explicit_nonpolish_category")])
def test_categories(source_id, reason):
    row = pair(); row["id"] = source_id
    with pytest.raises(ValueError, match=reason):
        adapt("pllum-align", row, "dialogs.jsonl", 0)


@pytest.mark.parametrize("text", ["Jestem PLLuM.", "Jestem ChatGPT.", "Kim jeste\u015b?", "<|im_start|>assistant"])
def test_identity_and_legacy_markers(text):
    row = pair(); row["chosen"][-1]["content"] = text
    with pytest.raises(ValueError):
        adapt("pllum-align", row, "dialogs.jsonl", 0)


def test_context_mismatch():
    row = copy.deepcopy(pair())
    row["rejected"] = copy.deepcopy(row["rejected"])
    row["rejected"][0]["content"] = "Other prompt"
    with pytest.raises(ValueError, match="preference_context_mismatch"):
        adapt("pllum-align", row, "dialogs.jsonl", 0)


@pytest.mark.parametrize("rating", [None, "5", float("nan"), 6, 3, True])
def test_bad_ratings(rating):
    row = pair(); row.update(chosen_rating=rating, rejected_rating=2)
    with pytest.raises(ValueError, match="invalid_or_weak_preference_rating"):
        adapt("pllum-align", row, "rating.jsonl", 0)


@pytest.mark.parametrize("name,file", [("pllumic", "pllumic.json"),
    ("pllumic-syn", "pllumic_synthetic_extension_54k.jsonl")])
def test_documented_pllumic_schema(name, file):
    row = {"conv_id": "abc", "messages": [{"role": "system", "content": "", "seq": -1}] + pair()["chosen"]}
    for i, m in enumerate(row["messages"][1:]):
        m.update(seq=i // 2 if name == "pllumic" else i, language="pol", type="Dialog", source=["source attribution"])
    result = adapt(name, row, file, 0)
    assert len(result["messages"]) == 4
    assert "target_message_index" not in result
    assert result["provenance"]["message_metadata"][0]["source"] == ["source attribution"]
    row["messages"][2]["seq"] = 99
    with pytest.raises(ValueError, match="invalid_sequence"):
        adapt(name, row, file, 0)


def test_tools_language_and_heldout_rejected():
    for patch in [{"tools": [{"name": "f"}]}, {"language": "en"}, {"split": "test"}]:
        row = pair(); row.update(patch)
        with pytest.raises(ValueError):
            adapt("pllum-align", row, "dialogs.jsonl", 0)


def test_normalized_inherited_overlap(tmp_path):
    messages = pair()["chosen"]
    path = tmp_path / "chats.jsonl"
    path.write_text(json.dumps({"messages": messages}) + "\n" + json.dumps({"text": "unsupported"}) + "\n")
    fp = chat_fingerprint(messages)
    assert inherited_overlap({fp}, [path], tmp_path / "report.json") == {fp}
    evidence = json.loads((tmp_path / "report.json").read_text())
    assert evidence["complete"] and evidence["files"][0]["counts"]["unsupported_schema"] == 1


def test_actual_gemma_template_preserves_final_context():
    from dfm12.prepare import Renderer
    from scripts.tokenize_chat_template import examples_from_messages, tokenize_example
    metadata = Path("data/sampled_dfm11/metadata.json")
    if not metadata.exists():
        pytest.skip("Local DFM11 tokenizer unavailable")
    renderer = Renderer(json.loads(metadata.read_text())["tokenizer_info"], 4096)
    record = adapt("pllum-align", pair(), "dialogs.jsonl", 0)
    examples = list(examples_from_messages(record["messages"], [], record["target_message_index"]))
    assert len(examples) == 1 and len(examples[0].prompt_messages) == 3
    encoded = tokenize_example(renderer.tokenizer, renderer.template, examples[0], False)
    assert rendered_count(renderer, record) == sum(map(len, encoded))
    decoded = renderer.tokenizer.decode(encoded[0], skip_special_tokens=False)
    assert "Pytanie pierwsze" in decoded and "Odpowiedz pierwsza" in decoded
    assert "[gMASK]" not in decoded
    renderer.max_length = 2
    with pytest.raises(ValueError, match="full_context_render_rejected"):
        rendered_count(renderer, record)


def test_isolated_pipeline_dedup_and_final_target(tmp_path, monkeypatch):
    from dfm12 import polish_prepare, prepare
    root = tmp_path / "polish_unaudited"
    download = root / "downloads" / "pllum-align"
    download.mkdir(parents=True)
    for file in ("dialogs.jsonl", "ranking.jsonl", "rating.jsonl"):
        (download / file).write_text("")
    (download / "dialogs.jsonl").write_text((json.dumps(pair()) + "\n") * 2)
    review = {"sources": {name: {"eligible": name == "pllum-align"} for name in polish_prepare.SOURCES}}
    monkeypatch.setattr(polish_prepare, "access", lambda *args: review)
    asset = tmp_path / "mock-tokenizer"
    asset.write_text("mock tokenizer and template")
    monkeypatch.setattr(polish_prepare, "load", lambda path:
        {"tokenizer_info": {"tokenizer_path": str(asset), "chat_template_path": str(asset)}}
        if str(path) == "data/sampled_dfm11/metadata.json" else {"sources": {}})
    monkeypatch.setattr(prepare, "Renderer", lambda *args: None)
    monkeypatch.setattr(polish_prepare, "rendered_count", lambda *args: 123)
    calls = []

    def tokenize(command, check):
        assert check
        calls.append(command)
        inputs = list(Path(command[2]).glob("*.jsonl"))
        records = [json.loads(line) for path in inputs for line in path.read_text().splitlines()]
        assert len(records) == 1
        assert records[0]["messages"] == pair()["chosen"]
        assert records[0]["target_message_index"] == 3
        assert set(records[0]) == {"id", "messages", "target_message_index"}

    monkeypatch.setattr(polish_prepare.subprocess, "run", tokenize)
    output = root / "run"
    polish_prepare.run(root, output, 4, [])
    receipt = json.loads((output / "receipt.json").read_text())
    counts = receipt["sources"]["pllum-align"]["counts"]
    assert counts["candidates"] == 1 and counts["duplicate_of:pllum-align"] == 1
    assert receipt["state"] == "complete_unaudited" and not receipt["accepted"]
    assert len(calls) == 1 and calls[0][-3:] == ["4", "--max-seq-len", "4096"]
    with pytest.raises(FileExistsError):
        polish_prepare.run(root, output, 4, [])


def test_selected_access_never_contacts_deferred_sources(tmp_path, monkeypatch):
    import huggingface_hub
    from types import SimpleNamespace
    from dfm12.polish_prepare import access
    from dfm12.polish import SOURCES
    calls = []

    class Api:
        def whoami(self):
            return {}

        def dataset_info(self, repo, revision):
            calls.append(repo)
            assert repo == SOURCES["pllumic"][0]
            return SimpleNamespace(gated="auto", siblings=[],
                card_data=SimpleNamespace(to_dict=lambda: {"license": "cc-by-sa-4.0"}))

    def download(repo, relative, **kwargs):
        assert repo == SOURCES["pllumic"][0]
        path = tmp_path / relative
        path.write_text("[]")
        return str(path)

    monkeypatch.setattr(huggingface_hub, "HfApi", Api)
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", download)
    inventory = {name: {"repo": repo, "revision": rev, "files": list(files)}
                 for name, (repo, rev, files) in SOURCES.items()}
    review = access(tmp_path, inventory, ["pllumic"])
    assert calls == ["pelcra/PLLuMIC"]
    assert review["sources"]["pllumic"]["eligible"]
    assert review["sources"]["pllumic-syn"]["network_attempted"] is False
    assert review["sources"]["pllum-align"]["state"] == "deferred_not_requested"
    assert json.loads((tmp_path / "access-review.json").read_text()) == review


@pytest.mark.parametrize("seq", [[0, 1, 2, 3], [0, 0, 2, 2], [1, 1, 0, 0]])
def test_organic_pair_sequence_rejects_anomalies(seq):
    messages = copy.deepcopy(pair()["chosen"])
    for m, number in zip(messages, seq):
        m["seq"] = number
    with pytest.raises(ValueError, match="invalid_sequence"):
        adapt("pllumic", {"messages": messages}, "pllumic.json", 0)


def test_real_organic_payload_schema_and_multiturn():
    from dfm12.io import rows
    path = Path("data/dfm12/polish_unaudited/pllumic-access-20260924/downloads/pllumic/pllumic.json")
    if not path.exists():
        pytest.skip("Authorized organic PLLuMIC payload unavailable")
    data = list(rows(path))
    assert len(data) == 703
    valid = []
    for ordinal, row in enumerate(data):
        try:
            record = adapt("pllumic", row, "pllumic.json", ordinal)
        except ValueError as exc:
            assert str(exc) != "invalid_sequence"
            continue
        expected = row["messages"][1:] if row["messages"][0]["content"] == "" else row["messages"]
        assert record["messages"] == [{"role": m["role"], "content": m["content"]} for m in expected]
        valid.append(record)
    assert len(valid) > 500
    assert any(sum(m["role"] == "assistant" for m in r["messages"]) > 1 for r in valid)


def test_organic_all_assistant_targets_keep_history():
    from scripts.tokenize_chat_template import examples_from_messages
    messages = copy.deepcopy(pair()["chosen"])
    for i, message in enumerate(messages):
        message["seq"] = i // 2
    record = adapt("pllumic", {"messages": messages}, "pllumic.json", 0)
    examples = list(examples_from_messages(record["messages"], [], record.get("target_message_index")))
    assert len(examples) == 2
    assert examples[0].prompt_messages == record["messages"][:1]
    assert examples[1].prompt_messages == record["messages"][:3]
    assert examples[1].assistant_message == record["messages"][3]
