from copy import deepcopy

from dfm12.io import digest
from dfm12.scandi import FILES, PINS
from dfm12.scandi_admission import (
    MURI, adapt, authorized_language, authorized_muri_heldout, exact_key,
)


def fixture(language="", split="test"):
    row = {"language": language, "source": "muri-it-language-split", "model": "Mixtral-8x7B",
           "messages": [{"role": "user", "content": "Sporsmal"}, {"role": "assistant", "content": "Svar"}]}
    match = {"revision": PINS[MURI], "language": "nor", "split": split,
             "file": f"nor/{split}-00000-of-00001.parquet", "ordinal": 0,
             "messages_sha256": digest(row["messages"]), "match_method": "exact_original_messages"}
    return row, match


def test_generic_no_narrow_authorization():
    row, match = fixture()
    record = adapt(row, FILES[1], 1, [match])
    assert authorized_language(record)
    assert authorized_muri_heldout(record)
    assert record["messages"] == row["messages"]
    for field, value in [("repo", "other"), ("revision", "main"), ("admission_policy", "other"),
                         ("authorization_sha256", "other"), ("file", "other"), ("ordinal", -1)]:
        changed = deepcopy(record)
        changed["provenance"][field] = value
        assert not authorized_language(changed)
    for field, value in [("language", "swe"), ("revision", "main"), ("messages_sha256", "bad"),
                         ("file", "nor/train-00000-of-00001.parquet"), ("match_method", "normalized")]:
        changed = deepcopy(record)
        changed["provenance"]["muri_lineage"][0][field] = value
        assert not authorized_language(changed)
    changed = deepcopy(record)
    changed["messages"][0]["content"] = "changed"
    assert not authorized_language(changed)
    changed = deepcopy(record)
    changed["message_languages"] = ["nb", "nb"]
    assert not authorized_language(changed)


def test_multiturn_and_declared_languages_preserved():
    row, _ = fixture("da")
    row["messages"] *= 2
    record = adapt(row, FILES[0], 0, [])
    assert record["messages"] == row["messages"]
    assert len(record["messages"]) == 4
    assert record["language"] == "da"
    assert not authorized_language(record)
    assert not authorized_muri_heldout(record)
    assert record["accepted"] is False


def test_normalized_heldout_annotation_does_not_fake_original_split():
    from dfm12.records import chat_fingerprint
    row, match = fixture("nn", "train")
    record = adapt(row, FILES[1], 1, [match])
    assert not authorized_muri_heldout(record)
    record["audit_context"]["frozen_overlap"] = {
        "chat_sha256": chat_fingerprint(record["messages"]),
        "components": [{"scope": "heldout", "component": "heldout:muri:nor:test"}]}
    assert authorized_muri_heldout(record)
    assert record["provenance"]["original_split"] == ["train"]
    assert not authorized_language(record)
    record["audit_context"]["frozen_overlap"]["components"][0]["component"] = "heldout:other:test"
    assert not authorized_muri_heldout(record)


def test_exact_semantics_include_targets_tools_language_and_whitespace():
    row, match = fixture()
    record = adapt(row, FILES[1], 1, [match])
    alias = deepcopy(record)
    alias["id"] = "alias"
    alias["provenance"]["ordinal"] = 3
    assert exact_key(alias) == exact_key(record)
    for key, value in [("target_message_index", 1), ("tools", [{}]), ("language", "nb")]:
        assert exact_key(dict(record, **{key: value})) != exact_key(record)
    alias["messages"][0]["content"] += " "
    assert exact_key(alias) != exact_key(record)


def test_blank_requires_lineage_and_heldout_does_not_exclude():
    import pytest
    row, match = fixture()
    with pytest.raises(ValueError, match="blank_language"):
        adapt(row, FILES[0], 0, [])
    record = adapt(row, FILES[0], 0, [match])
    assert record["audit_context"]["known_muri_heldout"]
    assert record["provenance"]["original_split"] == ["test"]


def test_inherited_openhermes_attribution_not_target_metadata():
    from dfm12.cpu_scandi_admission import plain_instruction
    row, _ = fixture()
    inherited = {"messages": row["messages"], "language": "en", "dfm8_synthetic_family": "openhermes",
                 "source_answer_defective": False, "source_row_id": "original", "openhermes_category": ""}
    assert plain_instruction(inherited, "messages")
    assert plain_instruction(dict(inherited, source_answer_defective=True, english_repair_request_id="repair"), "messages")
    for key, value in [("target_message_index", 1), ("tools", []), ("unknown_field", None)]:
        assert not plain_instruction(dict(inherited, **{key: value}), "messages")
    assert not plain_instruction(inherited, "reverse_messages")


def test_token_accounting_preserves_all_targets():
    import pytest
    from dfm12.scandi_admission_verify import token_counts
    row, _ = fixture("da")
    row["messages"] *= 2
    record = adapt(row, FILES[0], 0, [])
    record["rendered_tokens"] = 8
    example = {"prompt_ids": [1, 2], "response_ids": [3, 4]}
    assert token_counts(record, {"id": record["id"], "examples": [example, example]}) == (8, 2)
    with pytest.raises(ValueError, match="missing_multiturn_target"):
        token_counts(record, {"id": record["id"], "examples": [example]})
    with pytest.raises(ValueError, match="token_record_id"):
        token_counts(record, {"id": "other", "examples": [example, example]})


def test_isolated_cpu_runner_and_independent_replay(tmp_path, monkeypatch):
    import sqlite3
    import pyarrow as pa
    import pyarrow.parquet as pq
    from tokenizers import Tokenizer, models, pre_tokenizers
    from dfm12.io import file_hash, load, write_json
    from dfm12.scandi import REPO, REVISION
    from dfm12.cpu_scandi_admission import run
    from dfm12.scandi_admission_verify import run as verify_run
    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "RAYON_NUM_THREADS"):
        monkeypatch.setenv(key, "1")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    base, cross, out = (tmp_path / name for name in ("base", "cross", "out"))
    base.mkdir()
    cross.mkdir()
    tokenizer = Tokenizer(models.WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer.save(str(base / "tokenizer.json"))
    (base / "template.jinja").write_text("{% for message in messages %}{{ message['content'] }}\n{% endfor %}")
    write_json(base / "receipt.json", {
        "tokenizer_info": {"tokenizer_path": str(base / "tokenizer.json"), "chat_template_path": str(base / "template.jinja")},
        "tokenizer_sha256": file_hash(base / "tokenizer.json"), "template_sha256": file_hash(base / "template.jinja")})
    raw, _ = fixture()
    raw["messages"] = [{"role": "user", "content": "two words"}, {"role": "assistant", "content": "answer words"}]
    multi = deepcopy(raw)
    multi.update(language="da", source="aya_collection_language_split")
    multi["messages"] *= 2
    bad = deepcopy(raw)
    bad["messages"][1]["content"] = ""
    table = pa.Table.from_pylist([raw, raw, multi, bad])
    evidence = []
    for i, relative in enumerate(FILES):
        path = base / "downloads" / REPO / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table if i == 0 else table.slice(0, 0), path)
        evidence.append({"path": str(path), "sha256": file_hash(path), "repo": REPO, "revision": REVISION, "file": relative})
    path = base / "nor-test.parquet"
    pq.write_table(pa.Table.from_pylist([{"input": "two words", "output": "answer words", "split": "test", "language": "nor"}]), path)
    evidence.append({"path": str(path), "sha256": file_hash(path), "repo": MURI, "revision": PINS[MURI], "file": "nor/test-00000-of-00001.parquet"})
    write_json(base / "evidence.json", evidence)
    write_json(cross / "coverage.json", {"files": []})
    db = sqlite3.connect(cross / "observations.sqlite")
    db.execute("CREATE TABLE observations (hash BLOB, file INTEGER, ordinal INTEGER, direction TEXT)")
    db.close()
    (cross / "collision-groups.jsonl").write_text("")
    write_json(cross / "audit-manifest.json", {"coverage_sha256": file_hash(cross / "coverage.json"),
        "outputs": {"observations.sqlite": file_hash(cross / "observations.sqlite")}})
    run(base, cross, out, workers=1)
    result = load(out / "integration.json")
    assert result["counts"]["input"] == 4
    assert result["counts"]["candidates"] == 2
    assert result["counts"]["training_examples"] == 3
    assert result["counts"]["known_heldout_retained"] == 1
    assert result["counts"]["excluded:exact_within_release_duplicate"] == 1
    verify_run(base, out)
    assert load(out / "verification.json")["all_original_rows_partitioned"]
