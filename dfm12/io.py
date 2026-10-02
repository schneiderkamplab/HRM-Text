"""Bounded readers and crash-safe, single-writer stage outputs."""
from contextlib import contextmanager
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


@contextmanager
def lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


@contextmanager
def atomic(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            yield handle
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_json(path, value):
    with atomic(path) as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def rows(path):
    path = Path(path)
    if path.suffix == ".parquet":
        import pyarrow.parquet as pq
        for batch in pq.ParquetFile(path).iter_batches(batch_size=256):
            yield from batch.to_pylist()
    elif path.suffix == ".json":
        # A few upstream releases are JSON arrays, not JSONL.
        import ijson
        with path.open("rb") as handle:
            yield from ijson.items(handle, "item")
    else:
        opener = gzip.open if path.name.endswith(".gz") else open
        with opener(path, "rt", encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if line.strip():
                    try:
                        yield json.loads(line)
                    except ValueError as exc:
                        raise ValueError(f"{path}:{number}: {exc}") from exc


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class Seen:
    """Disk-backed deduplication; no growing Python set for multilingual corpora."""
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS seen (hash TEXT PRIMARY KEY)")

    def add(self, value):
        return self.db.execute("INSERT OR IGNORE INTO seen VALUES (?)", (value,)).rowcount == 1

    def close(self):
        self.db.commit()
        self.db.close()
