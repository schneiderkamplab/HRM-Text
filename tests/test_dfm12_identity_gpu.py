import json

import pytest

from dfm12.catalog import config
from dfm12.identity import requests
from dfm12.identity_gpu import IdentityQueue, generated_record
from dfm12.io import load
from dfm12.prepare import Renderer as TrainingRenderer
from dfm12 import identity_gpu
from dfm12.io import write_json, digest
from pathlib import Path


class Renderer:
    def count(self, messages):
        return 100


def test_exact_nine_by_thousand_requests_and_profile():
    rows = list(requests(config(), "xl-full-bp", 1000, 0))
    assert len(rows) == 9000
    assert len({r["record"]["id"] for r in rows}) == 9000
    for language in config()["languages"]:
        slots = [r["record"]["provenance"]["slot"] for r in rows if r["record"]["language"] == language]
        assert slots == list(range(1000))
    assert all(r["record"]["profile"] == "xl-full-bp" for r in rows)
    assert all(r["request"]["chat_template_kwargs"] == {"enable_thinking": False} for r in rows)


def test_turn_contract_and_full_fact_context_preserved():
    request = next(requests(config(), "xl-full-bp", 1, 0))
    response = {"messages": [{"role": "user", "content": "Who are you?"},
                             {"role": "assistant", "content": "I am Mimir."}]}
    record = generated_record(request, response, Renderer())
    assert record["messages"] == response["messages"]
    assert record["audit_context"] == request["record"]["audit_context"]
    assert record["rendered_tokens"] == 100
    with pytest.raises(ValueError, match="turns"):
        generated_record(request, {"messages": response["messages"] * 2}, Renderer())


@pytest.mark.skipif(not Path("data/sampled_dfm11/metadata.json").exists(), reason="local training template unavailable")
def test_actual_pinned_training_template_accepts_native_identity():
    renderer = TrainingRenderer(load(Path("data/sampled_dfm11/metadata.json"))["tokenizer_info"], 4096)
    request = next(requests(config(), "xl-full-bp", 1, 0))
    result = {"messages": [{"role": "user", "content": "What is your name?"},
                           {"role": "assistant", "content": "My name is Mimir. I am an AI language model."}]}
    assert generated_record(request, result, renderer)["rendered_tokens"] > 0


def test_resume_refuses_changed_student_template_without_overwriting_receipt(tmp_path, monkeypatch):
    template, tokenizer = tmp_path / "template", tmp_path / "tokenizer"
    template.write_text("pinned template")
    tokenizer.write_text("pinned tokenizer")
    metadata = tmp_path / "metadata.json"
    write_json(metadata, {"tokenizer_info": {"chat_template_path": str(template), "tokenizer_path": str(tokenizer), "enable_thinking": False}})
    monkeypatch.setattr(identity_gpu, "Renderer", lambda info, limit: (info, limit))
    identity_gpu.training_renderer(tmp_path, metadata)
    pinned = (tmp_path / "training-template.json").read_bytes()
    identity_gpu.training_renderer(tmp_path, metadata)
    template.write_text("changed")
    with pytest.raises(ValueError, match="refusing resume"):
        identity_gpu.training_renderer(tmp_path, metadata)
    assert (tmp_path / "training-template.json").read_bytes() == pinned


def test_pilot_audits_dedup_and_held_bulk_are_idempotent(tmp_path):
    queue = IdentityQueue(tmp_path / "jobs.sqlite")
    request = next(requests(config(), "xl-full-bp", 1, 0))
    response = {"messages": [{"role": "user", "content": "Who?"}, {"role": "assistant", "content": "Mimir."}]}
    record = generated_record(request, response, Renderer())
    queue.promote("one", record)
    queue.promote("one", record)
    queue.promote("duplicate", record)
    later = json.loads(json.dumps(record))
    later["provenance"]["slot"] = 20
    later["messages"][0]["content"] = "Name?"
    queue.promote("later", later)
    assert queue.db.execute("SELECT stage,count(*) FROM jobs GROUP BY stage").fetchall() == [("audit-pilot", 1), ("audit-review-pending", 1)]
    assert queue.report()["duplicates"] == 1
    assert queue.next_job("worker")[0] == "audit-pilot"
    assert queue.next_job("other") is None
    queue.close()


def bulk_fixture(tmp_path):
    queue = IdentityQueue(tmp_path / "jobs.sqlite")
    audit = {"keep": True, "reason": "Reviewed", "language_quality": 5, "coherence": 5, "usefulness": 5}
    for language in config()["languages"]:
        key = queue.add("audit-pilot", {"record": {"language": language}})
        queue.db.execute("UPDATE jobs SET status='done',result=? WHERE id=?", (json.dumps(audit), key))
    queue.add("audit-review-pending", {"record": {"language": "en", "id": "bulk"}})
    generation = queue.add("generate", {"record": {"language": "en", "id": "failed"}})
    queue.db.execute("UPDATE jobs SET status='failed',attempts=4,error='retained failure' WHERE id=?", (generation,))
    write_json(tmp_path / "training-template.json", {"pinned": True})
    pilots = queue.db.execute("SELECT id,payload,result FROM jobs WHERE stage='audit-pilot' AND status='done' ORDER BY id").fetchall()
    review = tmp_path / "review.json"
    write_json(review, {"scope": "identity_pilot_operational_review", "findings": ["reviewed"],
                        "pilot_sha256": digest(pilots), "languages": list(config()["languages"])})
    return queue, review, generation


def test_bulk_activation_idempotent_and_generation_untouched(tmp_path):
    queue, review, generation = bulk_fixture(tmp_path)
    before = queue.db.execute("SELECT * FROM jobs WHERE id=?", (generation,)).fetchone()
    assert queue.activate_bulk(tmp_path, review) == 1
    assert queue.activate_bulk(tmp_path, review) == 0
    stage, job = queue.next_job("endpoint", bulk=True)
    assert stage == "audit-bulk"
    queue.finish(job[0], "endpoint", job[2] + 1, {"keep": False})
    assert not queue.work_remains(bulk=True)
    assert queue.db.execute("SELECT * FROM jobs WHERE id=?", (generation,)).fetchone() == before
    receipt = load(tmp_path / "bulk-audit-authorization.json")
    assert receipt["human_approval"] is False and receipt["regeneration_authorized"] is False
    queue.close()


def test_bulk_refuses_unreviewed_or_changed_pilot(tmp_path):
    queue, review, _ = bulk_fixture(tmp_path)
    doc = load(review)
    doc["pilot_sha256"] = "changed"
    write_json(review, doc)
    with pytest.raises(ValueError, match="review required"):
        queue.activate_bulk(tmp_path, review)
    assert queue.db.execute("SELECT count(*) FROM jobs WHERE stage='audit-review-pending'").fetchone()[0] == 1
    queue.close()


def test_bulk_lease_recovery_does_not_touch_generation(tmp_path):
    queue, review, generation = bulk_fixture(tmp_path)
    queue.activate_bulk(tmp_path, review)
    queue.db.execute("UPDATE jobs SET status='running',lease=0 WHERE id=?", (generation,))
    before = queue.db.execute("SELECT * FROM jobs WHERE id=?", (generation,)).fetchone()
    assert queue.next_job("endpoint", bulk=True)[0] == "audit-bulk"
    assert queue.db.execute("SELECT * FROM jobs WHERE id=?", (generation,)).fetchone() == before
    queue.close()
