import os

import pytest

from dfm12 import audit_resize


def test_exact_pid_identity_and_command_required():
    pid = os.getpid()
    identity = audit_resize.identity(pid)
    command = [os.fsdecode(arg) for arg in identity[0]]
    assert audit_resize.verified(pid, command) == identity
    with pytest.raises(ValueError, match="pinned command"):
        audit_resize.verified(pid, command + ["wrong"])


def test_reused_pid_never_signalled(monkeypatch):
    signals = []
    monkeypatch.setattr(audit_resize, "identity", lambda _: ([b"command"], "new-birth"))
    monkeypatch.setattr(audit_resize.os, "kill", lambda *args: signals.append(args))
    with pytest.raises(ValueError, match="identity changed"):
        audit_resize.signal_exact(123, ([b"command"], "old-birth"))
    assert signals == []


def test_only_requested_server_option_changes():
    command = ["python", "-m", "vllm.entrypoints.openai.api_server",
               "--gpu-memory-utilization", "0.90", "--max-num-seqs", "256", "--enforce-eager"]
    updated = audit_resize.replace_option(command, "--max-num-seqs", 512)
    assert updated == command[:6] + ["512"] + command[7:]
    assert command[6] == "256"


def test_new_client_option_appended_without_changing_existing():
    command = ["python", "--preparation-workers", "16"]
    assert audit_resize.replace_option(command, "--concurrency", 512) == command + ["--concurrency", "512"]
