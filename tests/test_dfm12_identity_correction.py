from collections import Counter
from copy import deepcopy

import pytest

from dfm12 import identity_correction as c
from dfm12.io import rows, digest, write_json


@pytest.fixture(scope="module")
def prepared():
    spec = c.read_spec()
    original, development, provenance = c.source_data(c.PREVIOUS)
    train, ledgers, exclusions = {}, [], []
    for lang in c.base.LANGUAGES:
        corrected, ledger, _ = c.correct(original[lang], spec, provenance)
        train[lang], excluded = c.deduplicate(corrected)
        ledgers += ledger
        exclusions += excluded
    return spec, original, development, train, ledgers, exclusions


def test_corrected_counts_and_split_isolation(prepared):
    spec, original, development, train, ledger, excluded = prepared
    assert {lang: len(train[lang]) for lang in train} == {"da": 1969, "en": 1981}
    assert len(excluded) == 1
    assert len(ledger) == 787
    test = c.heldout(spec)
    c.validate_splits(train, development, test, original)
    assert all(len(development[lang]) == 100 for lang in train)
    assert all(Counter(len(r["messages"]) // 2 for r in test[lang]) == {1: 30, 2: 20} for lang in train)


def test_unchanged_rows_preserved_exactly(prepared):
    _, original, _, train, ledger, _ = prepared
    changed = {r["original_id"] for r in ledger}
    assert len(changed) == len(ledger)
    for lang in train:
        old = {r["id"]: r for r in original[lang]}
        for row in train[lang]:
            if row["id"] in old:
                assert row == old[row["id"]]
                assert row["id"] not in changed


def test_all_confirmed_issues_have_exact_ledger(prepared):
    spec, _, _, _, ledger, _ = prepared
    edits = {(r["original_id"], x["message_index"]): x for r in ledger for x in r["changes"]}
    candidates = list(rows(c.REVIEW / "candidate-ledger.jsonl"))
    for row in candidates:
        key = row["record_id"], row["message_index_0based"]
        if row["disposition"] != "screened_no_confirmed_conflict":
            assert edits[key]["before"] == row["assistant_text"]
            assert edits[key]["after"] != row["assistant_text"]
        else:
            assert key not in edits
    assert len(spec["corrections"]) == 62
    for row in ledger:
        assert not row["human_reviewed"] and not row["gpu_audited"]
        for edit in row["changes"]:
            assert edit["before_sha256"] == digest({"role": edit["role"], "content": edit["before"]})
            assert edit["after_sha256"] == digest({"role": edit["role"], "content": edit["after"]})


def test_correction_fails_on_drift(prepared):
    spec, original, *_ = prepared
    record = deepcopy(next(r for r in original["da"] if r["id"] == spec["corrections"][0]["id"]))
    record["messages"][1]["content"] = "Different source"
    with pytest.raises(ValueError, match="precondition"):
        c.correct([record], spec)


def test_context_binding_adds_no_numerical_answer(prepared):
    _, _, _, _, ledger, _ = prepared
    scoped = [e for r in ledger for e in r["changes"] if e["category"] == "explicit_model_and_historical_scope"]
    assert len(scoped) == 734
    assert all(e["role"] == "user" and e["after"].endswith(e["before"]) for e in scoped)
    assert all("32" not in e["after"].removesuffix(e["before"]) for e in scoped)


def test_cross_split_prompt_overlap_rejected(prepared):
    spec, original, dev, train, *_ = prepared
    heldout = c.heldout(spec)
    heldout["en"][0]["messages"][0] = train["en"][0]["messages"][0]
    with pytest.raises(ValueError, match="overlap"):
        c.validate_splits(train, dev, heldout, original)


def test_current_tokenizer_binding_is_not_byte_identity(prepared):
    spec = prepared[0]
    assert "postprocessing and template differ" in spec["runtime_binding"]["scope"]
    assert "adapted" in spec["answers"]["current_tokenizer"]["en"]
    assert spec["answers"]["identical_template"]["en"].startswith("No,")


def test_heldout_asks_complete_roster_and_totals(prepared):
    spec = prepared[0]
    heldout = c.heldout(spec)["en"]
    assert all("Kenneth Enevoldsen" in r["messages"][1]["content"] for r in heldout
               if "who else" in r["messages"][0]["content"])
    assert all("70,479,308,606" in r["messages"][1]["content"] for r in heldout
               if "data volume" in r["messages"][0]["content"])


def test_full_native_render_and_response_accounting(prepared):
    spec, _, _, train, ledger, _ = prepared
    renderer = c.base.NativeRenderer(c.ROOT / "data/sampled_dfm11/metadata.json")
    changed_assistants = {r["corrected_id"] for r in ledger if any(e["role"] == "assistant" for e in r["changes"])}
    selected = [r for group in train.values() for r in group if r["id"] in changed_assistants]
    selected += [r for group in c.heldout(spec).values() for r in group]
    measurements = c.measure(selected, renderer)
    assert all(0 < r["response_tokens"] < r["rendered_tokens"] and r["max_rendered_length"] <= 4096 for r in measurements)
    assert all(len(r["response_lengths"]) == r["assistant_targets"] for r in measurements)


def test_v4_explicit_manifest_dispatch(tmp_path, monkeypatch):
    from dfm12.build_identity_adaptation import verify_identity_manifest
    called = []
    monkeypatch.setattr(c, "verify", lambda root: called.append(root))
    path = tmp_path / "manifest.json"
    write_json(path, {"schema": c.SCHEMA})
    assert verify_identity_manifest(path)["schema"] == c.SCHEMA
    assert called == [tmp_path]


def test_fourth_continuation_contract():
    from dfm12.build_identity_adaptation import continuation_contract
    result = continuation_contract(2880261, 1000, "step_2880261", 13)
    assert result["stop_after_step"] == 2881261 and result["trainer_epoch"] == 14
    assert result["data_epoch_index"] == 13
    assert result["required_batch_in_epoch"] == result["required_global_row_cursor_in_epoch"] == 0
    assert result["requires_isolated_zero_cursor_resume_metadata"]
