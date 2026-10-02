import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3

import pytest

from dfm12.catalog import config, selected_source
from dfm12.identity import requests
from dfm12.io import atomic, digest, load, write_json
from dfm12.jobs import Queue, validate_audit, response_json, audit_payload
from dfm12.opus import pairs, validate_license
from dfm12.prepare import convert_source, export_accepted
from dfm12.records import convert, language, validate_messages
from dfm12.transform import transform
from dfm12.budgets import opus_budget
from dfm12.pilot import require_pilot


def messages():
    return [{"role": "user", "content": "Please answer."}, {"role": "assistant", "content": "Answer."}]


class Renderer:
    info = {"test": True}
    def count(self, value):
        return sum(len(m["content"]) for m in value)


def test_all_translation_pairs_and_caps():
    cfg = config()
    mesh = pairs(cfg)
    assert len(mesh) == len(set(mesh)) == 33
    assert ("nb", "nn") in mesh and ("da", "fo") in mesh
    assert ("en", "fo") not in mesh
    assert cfg["english_translation_fraction"] / 4 == cfg["other_translation_fraction"]


@pytest.mark.parametrize("license", ["cc-by-nc-4.0", "cc-by-nd-4.0", "unknown", "CC-BY-*"])
def test_opus_rejects_unapproved_license(license):
    with pytest.raises(ValueError):
        validate_license(dict(status="approved", license=license, license_evidence="x", url="https://object.pouta.csc.fi/x"))


def test_language_variants_are_not_guessed():
    source = {"languages": ["nb", "nn"]}
    assert language({"language": ["nno"]}, source) == "nn"
    with pytest.raises(ValueError):
        language({"language": "nor"}, source)
    with pytest.raises(ValueError):
        language({"language": ["nob", "nno"]}, source)


def test_dala_explicit_language_and_metadata():
    source = dict(kind="dala", language="en", repo="a/b", revision="123")
    row = dict(messages=[{"role": "user", "content": "Is this English sentence correct?"},
                         {"role": "assistant", "content": "yes"}], secret="judge metadata")
    result = convert(row, source, "data/acceptability/train-0.jsonl.gz", 0)
    assert "secret" not in result and result["task"] == "acceptability"
    row["messages"][-1]["content"] = "Yes, correct"
    with pytest.raises(ValueError, match="invalid_acceptability"):
        convert(row, source, "data/acceptability/train-0.jsonl.gz", 0)


@pytest.mark.parametrize("lang", config()["new_languages"])
@pytest.mark.parametrize("task", config()["tasks"])
def test_transform_deterministic_and_recoverable(lang, task):
    original = "\n\n".join(f"Paragraph {i}. " + "This is a sentence with several words. " * 7 for i in range(5))
    first = transform(original, lang, task, {"document": "x"})
    assert first == transform(original, lang, task, {"document": "x"})
    validate_messages(first["messages"])
    answer = first["messages"][-1]["content"]
    assert answer in original
    if task in {"denoising", "paragraph-reordering"}:
        assert answer == original
    if task == "span-filling":
        assert "<GAP>" in first["messages"][0]["content"]


def test_identity_profile_and_historical_conflict():
    jobs = list(requests(config(), "xl-full-bp", count=2))
    assert len(jobs) == 18
    assert len({digest(j) for j in jobs}) == 18
    context = jobs[0]["record"]["audit_context"]
    assert "five steps" in context["facts"]["v1_backprop"]["text"]
    assert "full backpropagation" in context["profile"]["facts"][0]["text"]
    assert list(requests(config(), "generic", count=1))[0]["record"]["audit_context"]["profile"]["facts"] == []


def test_atomic_write_keeps_previous_on_crash(tmp_path):
    p = tmp_path / "out.json"
    write_json(p, {"old": True})
    with pytest.raises(RuntimeError):
        with atomic(p) as handle:
            handle.write("bad")
            raise RuntimeError()
    assert load(p) == {"old": True}


def test_queue_concurrent_claims_and_resume(tmp_path):
    path = tmp_path / "jobs.sqlite"
    q = Queue(path)
    for i in range(100):
        q.add("audit", {"index": i})
    q.close()
    def worker(i):
        q = Queue(path)
        claimed = []
        try:
            while job := q.claim("audit", str(i)):
                key, _, n = job
                claimed.append(key)
                q.finish(key, str(i), n + 1, result={"keep": True})
        finally:
            q.close()
        return claimed
    with ThreadPoolExecutor(max_workers=8) as pool:
        seen = [key for group in pool.map(worker, range(8)) for key in group]
    assert len(seen) == len(set(seen)) == 100
    q = Queue(path)
    assert q.claim("audit", "new") is None
    q.close()


def test_stale_worker_cannot_overwrite_new_owner(tmp_path):
    q = Queue(tmp_path / "jobs.sqlite")
    key = q.add("audit", {})
    q.claim("audit", "old")
    q.db.execute("UPDATE jobs SET lease=0")
    assert q.claim("audit", "new")[0] == key
    q.finish(key, "old", 1, result={"old": True})
    assert not list(q.completed("audit"))
    q.finish(key, "new", 2, result={"new": True})
    assert list(q.completed("audit"))[0][-1] == {"new": True}
    q.close()


def test_failed_requests_have_four_attempts_and_error_log(tmp_path):
    q = Queue(tmp_path / "jobs.sqlite")
    key = q.add("audit", {})
    for attempt in range(4):
        assert q.claim("audit", "a")[2] == attempt
        q.finish(key, "a", attempt + 1, error="length")
    assert q.claim("audit", "a") is None
    assert q.status() == [{"stage": "audit", "status": "failed", "count": 1}]
    assert q.db.execute("SELECT count(*) FROM events").fetchone()[0] == 4
    q.close()


def test_audit_schema_is_strict():
    result = dict(keep=True, language_quality=4, coherence=4, usefulness=4, reason="ok")
    validate_audit(result)
    for patch in ({"keep": "true"}, {"language_quality": True}, {"usefulness": 3}):
        with pytest.raises(ValueError):
            validate_audit(dict(result, **patch))
    assert response_json('```json\n{"keep":false}\n```') == {"keep": False}


def test_review_approval_requires_pinned_revision(tmp_path):
    write_json(tmp_path / "sources.lock.json", {"sources": {"s": dict(status="review", review="check", revision="abc", files=["data.parquet"])}})
    with pytest.raises(ValueError):
        selected_source(tmp_path, "s")
    write_json(tmp_path / "approvals/s.json", dict(revision="old", evidence="yes", files=["data.parquet"]))
    with pytest.raises(ValueError):
        selected_source(tmp_path, "s")


def test_only_audited_rows_export_and_translation_is_paired(tmp_path):
    q = Queue(tmp_path / "jobs.sqlite")
    row = dict(id="pair", component="opus-en-sv", messages=messages(), reverse_messages=list(reversed(messages())),
               language="sv", reverse_language="en", task="translation", provenance={})
    row["reverse_messages"] = messages()
    key = q.add("audit", audit_payload(row, "model"))
    q.claim("audit", "w")
    q.finish(key, "w", 1, result=dict(keep=True, language_quality=5, coherence=5, usefulness=5, reason="ok"))
    q.add("audit", audit_payload(dict(row, id="unaudited"), "model"))
    q.close()
    report = export_accepted(tmp_path, "opus-en-sv", Renderer(), config())
    assert report["repeat"] == 1
    assert report["counts"]["accepted"] == 2
    chats = [json.loads(line) for p in (tmp_path / "accepted/opus-en-sv/data").glob("*.jsonl") for line in p.read_text().splitlines()]
    assert {r["language"] for r in chats} == {"en", "sv"}
    assert all("provenance" not in r and "audit" not in r for r in chats)
    with pytest.raises(FileExistsError):
        export_accepted(tmp_path, "opus-en-sv", Renderer(), config())


def test_identity_repeat_is_sampling_metadata_not_duplicate_rows(tmp_path):
    q = Queue(tmp_path / "jobs.sqlite")
    row = dict(id="identity", component="identity-xl-full-bp", messages=messages(),
               language="en", task="identity", provenance={})
    key = q.add("audit", audit_payload(row, "model"))
    q.claim("audit", "w")
    q.finish(key, "w", 1, result=dict(keep=True, language_quality=5, coherence=5,
                                     usefulness=5, reason="ok"))
    q.close()
    report = export_accepted(tmp_path, "identity-xl-full-bp", Renderer(), config())
    assert report["repeat"] == 10
    assert report["counts"]["accepted"] == 1
    assert report["final_sampling"] is False
    paths = (tmp_path / "accepted/identity-xl-full-bp/data").glob("*.jsonl")
    assert sum(len(p.read_text().splitlines()) for p in paths) == 1


def test_converter_is_incrementally_reproducible(tmp_path):
    source = dict(repo="a/b", revision="abc", kind="chat", language="en", status="ready", files=["train.jsonl"])
    write_json(tmp_path / "sources.lock.json", {"sources": {"s": source}})
    data = tmp_path / "downloads/s/train.jsonl"
    data.parent.mkdir(parents=True)
    data.write_text(json.dumps({"messages": messages()}) + "\n")
    first = convert_source(tmp_path, "s", Renderer())
    assert first == convert_source(tmp_path, "s", Renderer())
    assert first["counts"]["candidates"] == 1


def test_budget_uses_sampled_tokens_not_stored_tokens(tmp_path):
    report = tmp_path / "report.log"
    report.write_text("### Task Coverage Stats\n"
                      "| **opus_da_en_repaired__shard0** | 100 (1%) | 900 (1%) | 30 (1%) | 400 (1%) | 200 (1%) | 200 (1%) |\n")
    result = opus_budget(report, config())
    assert result["baseline_tokens"] == 400
    assert result["english_pair_cap"] == 100
    assert result["non_english_pair_cap"] == 25
    report.write_text("### Task Coverage Stats\n| **opus__old** | 1 | 1 | 1 | 1 |\n")
    with pytest.raises(ValueError):
        opus_budget(report, config())


def test_pilot_needs_evidence_for_every_language(tmp_path):
    cfg = config()
    with pytest.raises(ValueError):
        require_pilot(tmp_path, cfg)
    approval = dict(approved=True, model=cfg["model"], languages=list(cfg["languages"]), evidence="Reviewed all language pilots")
    write_json(tmp_path / "pilot-approval.json", approval)
    require_pilot(tmp_path, cfg)
    approval["languages"].remove("nn")
    write_json(tmp_path / "pilot-approval.json", approval)
    with pytest.raises(ValueError):
        require_pilot(tmp_path, cfg)


def test_tools_are_not_silently_lost():
    with pytest.raises(ValueError, match="native_tool"):
        convert(dict(messages=messages(), tools=[{"name": "search"}]),
                dict(kind="chat", language="en", repo="a/b", revision="abc"), "train.parquet", 0)


def test_real_training_tokenizer_keeps_multiturn_boundaries():
    metadata = Path("data/sampled_dfm11/metadata.json")
    if not metadata.exists():
        pytest.skip("Production tokenizer not available")
    from dfm12.prepare import Renderer as RealRenderer
    info = load(metadata)["tokenizer_info"]
    if not all(Path(info[k]).exists() for k in ("tokenizer_path", "chat_template_path")):
        pytest.skip("Relocated production tokenizer")
    render = RealRenderer(info)
    conversation = messages() + [{"role": "user", "content": "And in Danish?"},
                                  {"role": "assistant", "content": "Her er svaret."}]
    assert render.count(conversation) > render.count(messages())
    with pytest.raises(ValueError, match="context"):
        render.count([messages()[0], {"role": "assistant", "content": " word" * 5000}])
