"""Read-only SQLite snapshot/pins for the manual article20 review; no inference."""
import collections
import hashlib
import json
from pathlib import Path
import sqlite3

root = Path("data/dfm13/baltic/qa31-article-diagnostic20-consumer-v3")
out = Path(__file__).resolve().parent


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


with sqlite3.connect(f"file:{root / 'catalog.sqlite'}?mode=ro", uri=True) as db:
    packets = dict(db.execute("SELECT id,packet FROM catalog ORDER BY id"))
with sqlite3.connect(f"file:{root / 'runtime.sqlite'}?mode=ro", uri=True) as db:
    db.execute("BEGIN")
    jobs = db.execute("SELECT id,state,phase,candidate FROM jobs ORDER BY id").fetchall()
    stages = db.execute("SELECT id,phase,attempt,status,record FROM stages ORDER BY id,phase,attempt").fetchall()
assert len(jobs) == len(packets) == 20
rows = []
for key, state, phase, repaired_json in jobs:
    packet = json.loads(packets[key])
    original = packet["candidate"]
    articles = packet["candidate_articles"]
    item = dict(id=key, state=state, phase=phase, packet_string_sha256=digest(packets[key]),
                candidate_sha256=digest(canonical(original)), articles=articles,
                original_messages=original["messages"],
                candidate_binding=packet["binding"])
    if repaired_json:
        repaired = json.loads(repaired_json)
        target = original["target_message_index"]
        assert len(repaired["messages"]) == len(original["messages"])
        assert repaired.get("tools", []) == original.get("tools", [])
        assert all(a == b for i, (a, b) in enumerate(zip(original["messages"], repaired["messages"])) if i != target)
        item.update(repaired_candidate_string_sha256=digest(repaired_json),
                    repaired_messages=repaired["messages"], protected_history_unchanged=True,
                    changed_message_indices=[i for i, (a, b) in enumerate(zip(original["messages"], repaired["messages"])) if a != b])
    rows.append(item)
payload = dict(root=str(root), publication_allowed=False, semantic_approval=False,
               operational_counts=dict(collections.Counter(r[1] for r in jobs)),
               manual_counts=dict(article_supported_provisional_keeps=6, challenged_provisional_keeps=6,
                                  withholding_supported=7, invalid_review_remains_unresolved=1),
               rows=rows, stages=[dict(id=k, phase=p, attempt=a, status=s,
                                      record_string_sha256=digest(r), record=json.loads(r))
                                 for k, p, a, s, r in stages],
               report_sha256=hashlib.sha256((out / "report.md").read_bytes()).hexdigest(),
               manifest_sha256=hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest())
with (out / "receipt.json").open("x") as handle:
    json.dump(payload, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
print(json.dumps(payload["operational_counts"]))
print("20 rows pinned; all 3 repairs preserve protected history and tools")
