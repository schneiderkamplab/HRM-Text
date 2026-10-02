import pytest
import io
import json

from dfm12 import audit_pilot_gpu as pilot

from dfm12.audit_pilot_gpu import LANGUAGES, MODEL, norwegian_supplement, payload, select


def records():
    return [{"id": f"{lang}-{i}", "language": lang, "task": "instruction",
             "messages": [{"role": "user", "content": "Question"},
                          {"role": "assistant", "content": "Answer"}],
             "provenance": {"component": "fixture"}}
            for lang in LANGUAGES for i in range(22)]


def test_bounded_nine_language_selection():
    selected = select(records())
    assert len(selected) == 180
    assert len({r["id"] for _, r in selected}) == 180
    assert all(sum(l == lang for l, _ in selected) == 20 for lang in LANGUAGES)
    assert selected == select(records())


@pytest.mark.parametrize("limit", [0, 21, -1])
def test_no_bulk_limit(limit):
    with pytest.raises(ValueError):
        select(records(), limit)


def test_missing_language_fails():
    with pytest.raises(ValueError, match="Insufficient"):
        select([r for r in records() if r["language"] != "fo"])


def test_round_robin_uses_top_level_component():
    rows = records()
    for row in rows:
        row["component"] = "rare" if row["id"].endswith("-21") else "common"
    selected = select(rows, per_language=2)
    assert all({r["component"] for lang, r in selected if lang == language} == {"rare", "common"}
               for language in LANGUAGES)


def test_reverse_language_is_not_relabelled():
    rows = records()
    for row in rows:
        if row["language"] == "da":
            row.update(language="nl", reverse_language="da")
    assert all(row["language"] == "nl" for lang, row in select(rows) if lang == "da")


def test_prompt_preserves_unknown_norwegian_and_student_data():
    record = records()[0]
    record.update(language="no", norwegian_standard="unknown", target_message_index=1)
    result = payload("no", record)
    assert result["record"] == record
    assert result["request"]["model"] == MODEL
    assert "do not infer that all text must be Bokmal" in result["request"]["messages"][0]["content"]
    schema = result["request"]["response_format"]["json_schema"]["schema"]
    assert set(schema["required"]) == {"keep", "reason", "language_quality", "coherence", "usefulness"}
    assert "approved" not in result
    assert result["request"]["max_tokens"] == 512


def test_supplement_refuses_unverified_generic_norwegian():
    with pytest.raises(ValueError, match="authorized"):
        norwegian_supplement([dict(r, language="no", norwegian_standard="unknown") for r in records()])


def test_readiness_waits_past_old_one_hour_deadline(monkeypatch, tmp_path):
    calls = []
    clock = [0]

    def request(url, timeout):
        calls.append(url)
        if len(calls) < 3:
            raise OSError("not ready")
        return io.StringIO(json.dumps({"data": [{"id": MODEL}]}))

    monkeypatch.setattr(pilot.urllib.request, "urlopen", request)
    monkeypatch.setattr(pilot.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(pilot.time, "sleep", lambda _: clock.__setitem__(0, clock[0] + 4000))
    path = tmp_path / "heartbeat.json"
    pilot.wait_for_endpoints(["http://localhost/v1"], path)
    assert clock[0] == 8000
    assert json.loads(path.read_text())["phase"] == "ready"


def test_wrong_model_never_ready_and_optional_timeout(monkeypatch, tmp_path):
    clock = [0]
    monkeypatch.setattr(pilot.urllib.request, "urlopen", lambda *a, **k:
                        io.StringIO(json.dumps({"data": [{"id": "wrong"}]})))
    monkeypatch.setattr(pilot.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(pilot.time, "sleep", lambda _: clock.__setitem__(0, 2))
    path = tmp_path / "heartbeat.json"
    with pytest.raises(TimeoutError, match="unclaimed"):
        pilot.wait_for_endpoints(["http://localhost/v1"], path, timeout=1)
    assert json.loads(path.read_text())["pending"] == {"http://localhost/v1": "ValueError"}


def test_reordering_supplement_preserves_both_task_labels():
    rows = [{"id": f"{language}-{task}-{i}", "language": language, "task": task,
             "component": f"reordering-integrated-{language}-{task}"}
            for language in ("nb", "nn", "nl", "sv")
            for task in ("paragraph-reordering", "text-block-reordering") for i in range(12)]
    selected = pilot.reordering_supplement(rows)
    assert len(selected) == 80
    assert all(sum(lang == language for lang, _ in selected) == 20 for language in ("nb", "nn", "nl", "sv"))
    assert {r["task"] for _, r in selected} == {"paragraph-reordering", "text-block-reordering"}
    with pytest.raises(ValueError, match="Insufficient"):
        pilot.reordering_supplement([r for r in rows if r["task"] != "text-block-reordering"])
