import json

import pytest

from dfm12 import audit_review_gpu as review
from dfm12.io import file_hash, write_json
from dfm12.jobs import Queue


class Gate:
    def reasons(self, record):
        return ["flagged"] if record["id"] == "flagged" else []


def snapshot(path, records):
    source = path / "review_only/audit_records.jsonl"
    source.parent.mkdir(parents=True)
    source.write_text("".join(json.dumps({"record": r}) + "\n" for r in records))
    write_json(path / "manifest.json", {"model": review.MODEL,
               "sources": [{"component": r["component"]} for r in records],
               "review_records_sha256": file_hash(source)})
    return path


def test_latest_component_authoritative_no_resurrection(tmp_path):
    old = snapshot(tmp_path / "old", [{"id": "old", "component": "a"}, {"id": "b", "component": "b"}])
    new = snapshot(tmp_path / "new", [{"id": "new", "component": "a"}, {"id": "flagged", "component": "a"}])
    records, report = review.collect([old, new], Gate(), skip_ids={"b"})
    assert [r["id"] for r in records] == ["new"]
    assert len(report["exclusions"]) == 2


def test_changed_snapshot_rejected(tmp_path):
    path = snapshot(tmp_path / "s", [{"id": "a", "component": "a"}])
    (path / "review_only/audit_records.jsonl").write_text("")
    with pytest.raises(ValueError, match="checksum"):
        review.collect([path], Gate())


def test_endpoint_provenance_and_pilot_only_stage(tmp_path, monkeypatch):
    database = tmp_path / "jobs.sqlite"
    queue = Queue(database)
    queue.add(review.STAGE, {"request": {"model": review.MODEL}})
    monkeypatch.setattr(review, "query", lambda endpoint, request: {
        "keep": True, "reason": "Fixture", "language_quality": 5, "coherence": 5, "usefulness": 5})
    review.execute(database, ["http://fixture/v1"], concurrency=2)
    assert queue.status() == [{"stage": "pilot-review", "status": "done", "count": 1}]
    owner = queue.db.execute("SELECT owner FROM jobs").fetchone()[0]
    assert owner.startswith("http://fixture/v1|")
    assert list(queue.completed("audit")) == []
    queue.close()


@pytest.mark.parametrize("workers", [0, 129, 256])
def test_concurrency_cap(tmp_path, workers):
    with pytest.raises(ValueError, match="1..128"):
        review.execute(tmp_path / "jobs.sqlite", ["http://fixture/v1"], workers)


def test_concurrent_http_uses_one_database_broker(tmp_path, monkeypatch):
    import threading
    database = tmp_path / "jobs.sqlite"
    q = Queue(database)
    for i in range(16):
        q.add(review.STAGE, {"request": {"id": i}})
    q.close()


    created, threads = [], set()
    original = review.Queue

    class ObservedQueue(original):
        def __init__(self, path):
            created.append(path)
            threads.add(threading.get_ident())
            super().__init__(path)

        def claim(self, *args, **kwargs):
            threads.add(threading.get_ident())
            return super().claim(*args, **kwargs)

        def finish(self, *args, **kwargs):
            threads.add(threading.get_ident())
            return super().finish(*args, **kwargs)

    monkeypatch.setattr(review, "Queue", ObservedQueue)
    monkeypatch.setattr(review, "query", lambda *args: {
        "keep": True, "reason": "fixture", "language_quality": 5, "coherence": 5, "usefulness": 5})
    review.execute(database, ["http://fixture/v1"], concurrency=8)
    assert len(created) == 1 and len(threads) == 1
    q = original(database)
    assert len(list(q.completed(review.STAGE))) == 16
    q.close()


def test_existing_done_and_inflight_jobs_unchanged(tmp_path, monkeypatch):
    database = tmp_path / "jobs.sqlite"
    q = Queue(database)
    result = {"keep": True, "reason": "fixture", "language_quality": 5, "coherence": 5, "usefulness": 5}
    done = q.add(review.STAGE, {"request": {"id": "done"}})
    q.claim(review.STAGE, "original")
    q.finish(done, "original", 1, result=result)
    running = q.add(review.STAGE, {"request": {"id": "inflight"}})
    q.claim(review.STAGE, "active-original")
    before = q.db.execute("SELECT * FROM jobs ORDER BY id").fetchall()
    q.add(review.STAGE, {"request": {"id": "pending"}})
    monkeypatch.setattr(review, "query", lambda *args: result)
    review.execute(database, ["http://fixture/v1"], concurrency=2)
    after = q.db.execute("SELECT * FROM jobs WHERE id IN (?,?) ORDER BY id", (done, running)).fetchall()
    assert before == after
    q.close()
