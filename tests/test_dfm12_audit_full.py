import json
import asyncio
import multiprocessing
from concurrent.futures import ThreadPoolExecutor

import pytest

from dfm12.audit_full import (Database, Prepare, TOKENIZER_DIR, commit_prepared,
                             park_pending, unpark_pending, preparation_process, preparation_exchange,
                             preparation_hash, validate_sources, concurrency_limits)
from dfm12.audit_gates import CrossScreen, FILES, legacy_tool_reasons
from dfm12.io import write_json, file_hash


def test_malformed_unicode_failure_is_persisted_and_retried(tmp_path):
    db = Database(tmp_path / "jobs.sqlite")
    source = {"component": "test", "sha256": "fixed"}
    db.register(source)
    db.put(source, [(0, {"id": "one", "messages": []}, [])])
    job = db.claim(1, ["endpoint"], 0)[0]
    result = {"reason": "broken\udbac"}
    with pytest.raises(UnicodeEncodeError):
        json.dumps(result, ensure_ascii=False).encode("utf-8")
    db.finish(job[1], job[4], job[3], result, "invalid Unicode \udbac")
    status, encoded, error = db.db.execute("SELECT status,result,error FROM jobs").fetchone()
    assert status == "pending"
    assert json.loads(encoded) == result
    assert error == "invalid Unicode \\udbac"
    retry = db.claim(1, ["endpoint"], 0)[0]
    db.finish(retry[1], retry[4], retry[3], {"reason": "Valid Danish: æøå"}, None)
    assert db.unfinished() == 0
    db.close()


def test_resume_waits_for_live_lease_and_recovers_expired(tmp_path):
    db = Database(tmp_path / "jobs.sqlite")
    source = {"component": "test", "sha256": "fixed"}
    assert db.register(source) == (-1, 0)
    db.put(source, [(0, {"id": "one", "messages": []}, [])])
    job = db.claim(1, ["endpoint"], 0)[0]
    assert db.pending() == 0
    assert db.unfinished() == 1
    assert db.claim(1, ["endpoint"], 0) == []
    db.db.execute("UPDATE jobs SET lease=0")
    retry = db.claim(1, ["endpoint"], 0)[0]
    db.finish(job[1], job[4], job[3], {"keep": True}, None)
    assert db.unfinished() == 1
    db.finish(retry[1], retry[4], retry[3], {"keep": False}, None)
    assert db.unfinished() == 0
    assert json.loads(db.db.execute("SELECT result FROM jobs").fetchone()[0]) == {"keep": False}
    db.close()


def test_quarantine_checkpoint_and_source_pin(tmp_path):
    db = Database(tmp_path / "jobs.sqlite")
    source = {"component": "test", "sha256": "fixed"}
    db.register(source)
    record = {"id": "one", "messages": [{"role": "assistant", "content": "original"}]}
    db.put(source, [(0, record, ["legacy_tools"])])
    assert db.register(source) == (0, 0)
    assert db.pending() == 0
    assert json.loads(db.db.execute("SELECT record FROM quarantine").fetchone()[0]) == record
    with pytest.raises(ValueError, match="changed"):
        db.register(dict(source, sha256="changed"))
    db.close()


@pytest.mark.parametrize("content", ["<functions>legacy</functions>", "<function_calls><invoke>tool</invoke></function_calls>"])
def test_legacy_xml_quarantined(content):
    assert legacy_tool_reasons({"messages": [{"role": "user", "content": content}]})


def test_ordinary_xml_not_tool_quarantine():
    assert not legacy_tool_reasons({"messages": [{"role": "user", "content": "<article>text</article>"}]})


def test_native_tools_quarantined():
    assert legacy_tool_reasons({"messages": [{"role": "tool", "content": "result"}]})


def test_duplicate_source_ownership_rejected():
    with pytest.raises(ValueError, match="Duplicate source"):
        validate_sources([{"component": "same"}, {"component": "same"}])
    with pytest.raises(ValueError, match="excluded"):
        validate_sources([{"component": "dala-pl-correction"}])


@pytest.mark.parametrize("concurrency", [256, 512])
def test_concurrency_scales_all_limits(concurrency):
    limits = concurrency_limits(concurrency, [str(i) for i in range(8)])
    assert limits == {"client_workers_per_endpoint": concurrency,
                      "total_http_coroutines": concurrency * 8,
                      "http_queue_capacity_per_endpoint": concurrency,
                      "max_outstanding_jobs": concurrency * 16,
                      "max_pending_jobs": concurrency * 32}


@pytest.mark.parametrize("concurrency,endpoints", [(0, ["one"]), (1025, ["one"]), (512, []), (512, ["same", "same"])])
def test_invalid_concurrency_or_endpoints_rejected(concurrency, endpoints):
    with pytest.raises(ValueError):
        concurrency_limits(concurrency, endpoints)


def test_hash_is_equivalent_and_cancellable(tmp_path):
    path = tmp_path / "input"
    path.write_bytes(b"content")
    assert preparation_hash(path) == file_hash(path)
    stop = multiprocessing.get_context("spawn").Event()
    stop.set()
    with pytest.raises(InterruptedError):
        preparation_hash(path, stop)


def test_cursor_rejects_replay_gap_and_reordering_atomically(tmp_path):
    db = Database(tmp_path / "jobs.sqlite")
    source = {"component": "one", "sha256": "hash"}
    db.register(source)
    db.put(source, [(0, {"id": "zero"}, [])])
    for batch in ([(0, {"id": "zero"}, [])], [(2, {"id": "two"}, [])],
                  [(2, {"id": "two"}, []), (1, {"id": "one"}, [])]):
        with pytest.raises(ValueError, match="Noncontiguous"):
            db.put(source, batch)
        assert db.register(source) == (0, 0)
        assert db.pending() == 1
    db.put(source, [(1, {"id": "one"}, [])])
    assert db.register(source) == (1, 0)
    db.close()


def test_legacy_drain_retains_responses_and_attempts(tmp_path):
    db = Database(tmp_path / "jobs.sqlite")
    source = {"component": "one", "sha256": "hash"}
    db.register(source)
    db.put(source, [(i, {"id": str(i)}, []) for i in range(3)])
    first, second = db.claim(2, ["endpoint"], 0)
    park_pending(db.db)
    db.put(source, [(3, {"id": "3"}, [])])
    assert db.claim(8, ["endpoint"], 0) == []
    db.finish(first[1], first[4], first[3], {"keep": False}, None)
    db.finish(second[1], second[4], second[3], None, "temporary")
    assert db.pending() == 0
    assert db.db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0] == 0
    unpark_pending(db.db)
    assert db.pending() == 3
    assert db.db.execute("SELECT status,attempts,result FROM jobs WHERE id='0'").fetchone() == ("done", 1, '{"keep": false}')
    assert db.db.execute("SELECT attempts FROM jobs WHERE id='1'").fetchone()[0] == 1
    db.close()


def test_concurrent_producers_respect_pending_bound(tmp_path):
    db = Database(tmp_path / "jobs.sqlite")
    peak = [0]

    async def exercise():
        mutex, stopping = asyncio.Lock(), asyncio.Event()

        async def sql(method, *args):
            await asyncio.sleep(0)
            result = getattr(db, method)(*args)
            peak[0] = max(peak[0], db.pending())
            return result

        async def producer(index):
            source = {"component": str(index), "sha256": "hash"}
            db.register(source)
            for ordinal in range(4):
                await commit_prepared(sql, mutex, source,
                                      [(ordinal, {"id": f"{index}-{ordinal}"}, [])], stopping, limit=8)

        tasks = [asyncio.create_task(producer(i)) for i in range(16)]
        while not all(task.done() for task in tasks):
            for _, key, _, attempt, owner in db.claim(4, ["endpoint"], 0):
                db.finish(key, owner, attempt, {"keep": True}, None)
            await asyncio.sleep(0.01)
        await asyncio.gather(*tasks)

    asyncio.run(exercise())
    assert peak[0] <= 8
    assert db.db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 64
    assert all(row[0] == 3 for row in db.db.execute("SELECT cursor FROM sources"))
    db.close()


@pytest.mark.skipif(not (TOKENIZER_DIR / "tokenizer.json").exists(), reason="cached Gemma tokenizer unavailable")
def test_spawned_preparation_matches_serial_full_records(tmp_path):
    for name in FILES:
        (tmp_path / name).write_text("")
    write_json(tmp_path / "coverage.json", {"files": []})
    screen = tmp_path / "audit-manifest.json"
    write_json(screen, {"snapshot_stable_at_finalization": True,
                       "coverage_sha256": file_hash(tmp_path / "coverage.json"),
                       "outputs": {name: file_hash(tmp_path / name) for name in FILES}})
    records = [{"id": str(i), "language": "no", "norwegian_standard": "unknown", "task": "instruction",
                "target_message_index": 3, "provenance": {"speaker": "P8"},
                "messages": [{"role": "user", "content": "Question"},
                             {"role": "assistant", "content": "Answer"},
                             {"role": "user", "content": "Another question"},
                             {"role": "assistant", "content": "<functions>tool</functions>" if i == 1 else "Answer"}]}
               for i in range(130)]
    path = tmp_path / "rows.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    write_json(tmp_path / "receipt.json", {"accepted": False})
    source = {"component": "fixture", "path": str(path), "sha256": file_hash(path),
              "receipt": str(tmp_path / "receipt.json"), "receipt_sha256": file_hash(tmp_path / "receipt.json")}
    expected = list(Prepare(CrossScreen(screen)).batches(source, -1))
    ctx = multiprocessing.get_context("spawn")
    workers = []
    try:
        for _ in range(2):
            parent, child = ctx.Pipe()
            process = ctx.Process(target=preparation_process, args=(child, screen))
            process.start()
            child.close()
            workers.append((process, parent))
        def collect(connection):
            result = []
            command = ("source", source, -1)
            while True:
                batch = preparation_exchange(connection, command)
                if batch is None:
                    return result
                result.append(batch)
                command = ("next",)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(collect, [connection for _, connection in workers]))
        assert results == [expected, expected]
        assert expected[0][1][2] == ["legacy_xml_tool_flattening_requires_quarantine"]
        assert expected[0][0][1]["target_message_index"] == 3
        assert len(expected[0][0][1]["messages"]) == 4
    finally:
        for process, connection in workers:
            connection.send(None)
            process.join(30)
            connection.close()
            assert process.exitcode == 0
