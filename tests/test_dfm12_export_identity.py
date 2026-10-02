import gzip
import json
import shutil
import sqlite3

import pytest
import yaml

from dfm12 import export_identity as module
from dfm12.catalog import config
from dfm12.identity import FACTS, requests
from dfm12.io import digest, file_hash, load, write_json
from dfm12.jobs import audit_payload


class Renderer:
    def count(self, messages):
        return 100


@pytest.fixture
def run(tmp_path, monkeypatch):
    root = tmp_path / "run"
    root.mkdir()
    shutil.copyfile(FACTS, root / "identity_facts.yaml")
    write_json(root / "training-template.json", {"test": True})
    (root / "student-chat-template.jinja").write_text("test template")
    db = sqlite3.connect(root / "jobs.sqlite")
    db.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY, stage TEXT, payload TEXT, result TEXT, status TEXT, attempts INTEGER, owner TEXT, error TEXT)")
    db.execute("CREATE TABLE identity_records(job_id TEXT PRIMARY KEY, record TEXT, duplicate_of TEXT, audit_id TEXT)")
    previous = {}
    for payload in requests(config(), module.PROFILE, 4):
        record = payload["record"]
        slot, lang = record["provenance"]["slot"], record["language"]
        gen_id = digest(["generate", payload])
        turns = json.loads(payload["request"]["messages"][1]["content"])["user_turns"]
        messages = [{"role": role, "content": f"{lang} {slot if slot != 2 else 0} {turn} {role}"}
                    for turn in range(turns) for role in ("user", "assistant")]
        generated = {"messages": messages}
        db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)", (gen_id, "generate", json.dumps(payload),
                   json.dumps(generated) if slot != 3 else None, "failed" if slot == 3 else "done", 1, "test", None))
        if slot == 3:
            continue
        record = dict(record, messages=messages, component="identity-" + module.PROFILE, rendered_tokens=100)
        if slot == 2:
            audit_id, duplicate = None, previous[lang]
        else:
            duplicate = None
            audit = audit_payload(record, config()["model"])
            audit_id = digest(["audit-pilot", audit])
            decision = {"keep": slot == 0, "language_quality": 5, "coherence": 5, "usefulness": 5, "reason": "fixture"}
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)", (audit_id, "audit-pilot", json.dumps(audit), json.dumps(decision), "done", 1, "test", None))
            previous[lang] = gen_id if slot == 0 else previous[lang]
        db.execute("INSERT INTO identity_records VALUES (?,?,?,?)", (gen_id, json.dumps(record), duplicate, audit_id))
    db.commit()
    pilot = db.execute("SELECT id,payload,result FROM jobs WHERE stage='audit-pilot' ORDER BY id").fetchall()
    db.close()
    write_json(root / "bulk-pilot-review.json", {"pilot_sha256": digest(pilot)})
    write_json(root / "enqueue.json", {"facts_sha256": file_hash(root / "identity_facts.yaml")})
    write_json(root / "bulk-audit-authorization.json", {"cohort": [], "count": 0,
        "facts_sha256": file_hash(root / "identity_facts.yaml"),
        "training_template_pin_sha256": file_hash(root / "training-template.json"),
        "review_sha256": file_hash(root / "bulk-pilot-review.json")})
    monkeypatch.setattr(module, "pinned_renderer", lambda *args: Renderer())
    return root


def read_rows(path):
    with gzip.open(path, "rt") as handle:
        return [json.loads(line) for line in handle]


def test_export_native_accepted_only_repeat_metadata_and_owned_companion(run, tmp_path):
    before = file_hash(run / "jobs.sqlite")
    output = tmp_path / "export"
    report = module.export_identity(run, output)
    assert report["rows"] == 9
    assert report["counts"] == dict(generation_requests=36, generated=27, failed_generations=9,
                                    audit_done=18, accepted=9, rendered_tokens=900, audit_rejected=9, duplicates=9)
    assert report["effective_tokens_per_epoch"] == 9000
    assert file_hash(run / "jobs.sqlite") == before
    assert len(module.verify_identity_source(output, report["identity_source_manifest"], report["packages"])) == 9
    for package in report["packages"]:
        folder = output / package["name"]
        rows = read_rows(folder / "data/train-00000.jsonl.gz")
        audits = read_rows(folder / "metadata/audits.jsonl.gz")
        assert len(rows) == len(audits) == 1
        assert rows[0]["messages"] == audits[0]["record"]["messages"]
        assert not {"provenance", "audit_context", "repeat", "audit"} & rows[0].keys()
        p = audits[0]["export_provenance"]
        assert p["source_record_sha256"] == digest(audits[0]["record"])
        assert p["facts_file_sha256"] == file_hash(folder / "metadata/identity_facts.yaml")
        excluded = read_rows(folder / "metadata/exclusions.jsonl.gz")
        assert len(excluded) == 1 and "record" not in excluded[0]
        assert load(folder / "metadata/manifest.json")["physical_row_repetition"] == 1
    with pytest.raises(FileExistsError):
        module.export_identity(run, output)


@pytest.mark.parametrize("mutation", ["pending", "facts", "messages", "audit_payload", "audit_scores", "render", "missing", "duplicate", "orphan"])
def test_fail_closed_snapshot(run, mutation):
    db = sqlite3.connect(run / "jobs.sqlite")
    key, raw, audit_id = db.execute("SELECT job_id,record,audit_id FROM identity_records WHERE duplicate_of IS NULL LIMIT 1").fetchone()
    record = json.loads(raw)
    if mutation == "pending":
        db.execute("UPDATE jobs SET status='pending' WHERE id=?", (audit_id,))
    elif mutation == "facts":
        record["provenance"]["facts_hash"] = "wrong"
    elif mutation == "messages":
        record["messages"][1]["content"] = "altered"
    elif mutation == "audit_payload":
        payload = json.loads(db.execute("SELECT payload FROM jobs WHERE id=?", (audit_id,)).fetchone()[0])
        payload["request"]["model"] = "changed"
        db.execute("UPDATE jobs SET payload=? WHERE id=?", (json.dumps(payload), audit_id))
    elif mutation == "audit_scores":
        result = dict(keep=True, language_quality=3, coherence=5, usefulness=5, reason="bad")
        db.execute("UPDATE jobs SET result=? WHERE id=?", (json.dumps(result), audit_id))
    elif mutation == "render":
        class WrongRenderer:
            def count(self, messages):
                return 101
    elif mutation == "missing":
        db.execute("DELETE FROM identity_records WHERE job_id=?", (key,))
    elif mutation == "duplicate":
        db.execute("UPDATE identity_records SET duplicate_of='absent' WHERE duplicate_of IS NOT NULL")
    elif mutation == "orphan":
        db.execute("DELETE FROM jobs WHERE id=?", (audit_id,))
    if mutation in {"facts", "messages"}:
        db.execute("UPDATE identity_records SET record=? WHERE job_id=?", (json.dumps(record), key))
    db.commit()
    with pytest.raises(ValueError):
        module.inspect_snapshot(db, yaml.safe_load(FACTS.read_text()), WrongRenderer() if mutation == "render" else Renderer())
    db.close()


@pytest.mark.parametrize("mutation", ["file", "extra", "inventory", "companion", "scope"])
def test_companion_rejects_unowned_or_changed_packages(run, tmp_path, mutation):
    output = tmp_path / "export"
    report = module.export_identity(run, output)
    folder = output / report["packages"][0]["name"]
    if mutation == "file":
        (folder / "README.md").write_text("changed")
    elif mutation == "extra":
        (folder / "unexpected.txt").write_text("unowned")
    elif mutation == "inventory":
        report["packages"][0]["rows"] += 1
    elif mutation == "companion":
        report["identity_source_manifest"]["sha256"] = "wrong"
    else:
        report["packages"].append(dict(report["packages"][0], component="identity-other", name="dfm12-identity-other"))
    with pytest.raises(ValueError):
        module.verify_identity_source(output, report["identity_source_manifest"], report["packages"])


def test_fact_file_pin_and_repeat_refused(run, tmp_path):
    with pytest.raises(ValueError, match="repeat"):
        module.export_identity(run, tmp_path / "out", repeat=1)
    (run / "identity_facts.yaml").write_text(FACTS.read_text() + "\n")
    with pytest.raises(ValueError, match="Fact registry"):
        module.export_identity(run, tmp_path / "out")


def test_multiturn_preserved_without_row_expansion(run):
    db = sqlite3.connect(run / "jobs.sqlite")
    for key, result in db.execute("SELECT id,result FROM jobs WHERE stage='audit-pilot'").fetchall():
        decision = json.loads(result)
        decision["keep"] = True
        db.execute("UPDATE jobs SET result=? WHERE id=?", (json.dumps(decision), key))
    accepted, _, counts = module.inspect_snapshot(db, yaml.safe_load(FACTS.read_text()), Renderer())
    assert counts["accepted"] == 18
    for items in accepted.values():
        record = next(item["record"] for item in items if len(item["record"]["messages"]) > 2)
        rows = list(module.export_validator.training_rows(record))
        assert len(rows) == 1 and rows[0]["messages"] == record["messages"]
    db.close()


def test_incremental_export_requires_explicit_identity_ownership(run, tmp_path):
    from dfm12.export_finished import validate_previous
    output = tmp_path / "export"
    report = module.export_identity(run, output)
    validate_previous(output, report["packages"], {}, report["identity_source_manifest"])
    with pytest.raises(ValueError, match="owning --run omitted"):
        validate_previous(output, report["packages"], {})
    with pytest.raises(ValueError, match="Duplicate identity/audit-root"):
        validate_previous(output, report["packages"], {report["packages"][0]["component"]: {}},
                          report["identity_source_manifest"])
