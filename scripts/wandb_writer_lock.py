"""Exclusive cross-process lock serializing W&B writers resuming the same run.

Concurrent average writers resuming the same W&B run can allocate the same
next internal history step; the server keeps one row and the other writer's
payload is silently dropped (see wiki: dfm8 suite-average history repair
2026-07-28; dfm15 100K block 2026-11-03). Holding this lock from run resume
until finish makes the resume->log->finish section mutually exclusive per
run id. The lock is advisory (flock) and is released automatically if a
writer crashes; a hung writer blocks successors, which surfaces as a stuck
post row in the scheduler monitor.
"""
from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager


@contextmanager
def wandb_writer_lock(run_id: str):
    lock_path = os.environ.get("WANDB_WRITER_LOCK", f"/tmp/wandb_writer_{run_id}.lock")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o666)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
