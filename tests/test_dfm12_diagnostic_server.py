import signal
import pytest

from dfm12 import diagnostic_server as server


def memory(free=40960):
    return {"devices": [{"index": i, "uuid": f"GPU-{i}", "free_mib": free} for i in (6, 7)]}


def test_headroom_guard():
    server.guard(memory())
    with pytest.raises(RuntimeError):
        server.guard(memory(40959))


def test_command_is_exact_bounded_tp2():
    command, env = server.command_env(memory(), "test-owner")
    for flag, value in {"--tensor-parallel-size": "2", "--gpu-memory-utilization": "0.18",
                        "--max-num-seqs": "8", "--max-num-batched-tokens": "4096",
                        "--max-model-len": "8192", "--generation-config": "vllm", "--port": "8590"}.items():
        assert command[command.index(flag) + 1] == value
    assert "--enforce-eager" in command
    assert env["CUDA_VISIBLE_DEVICES"] == "GPU-6,GPU-7"
    assert env["VLLM_PORT"] == "29000" and env["VLLM_USE_FLASHINFER_SAMPLER"] == "0"
    assert env[server.OWNER_ENV] == "test-owner"


def test_mismatched_process_is_never_signalled(monkeypatch):
    sent, closed = [], []
    monkeypatch.setattr(server, "pidfd_open", lambda pid: 55)
    monkeypatch.setattr(server.os, "close", closed.append)
    monkeypatch.setattr(server, "owned_alive", lambda *args: False)
    monkeypatch.setattr(server, "pidfd_signal", lambda *args: sent.append(args))
    assert not server.signal_owned({"pid": 123}, {"owner": "ours", "server_session": 123}, signal.SIGTERM)
    assert sent == [] and closed == [55]


def test_verified_process_uses_pidfd(monkeypatch):
    sent = []
    monkeypatch.setattr(server, "pidfd_open", lambda pid: 55)
    monkeypatch.setattr(server.os, "close", lambda fd: None)
    monkeypatch.setattr(server, "owned_alive", lambda *args: True)
    monkeypatch.setattr(server, "pidfd_signal", lambda *args: sent.append(args))
    assert server.signal_owned({"pid": 123}, {"owner": "ours", "server_session": 123}, signal.SIGTERM)
    assert sent == [(55, signal.SIGTERM)]


def test_existing_root_is_never_overwritten(tmp_path):
    with pytest.raises(FileExistsError):
        server.launch(tmp_path)


def test_maximum_lifetime(tmp_path):
    with pytest.raises(ValueError):
        server.supervise(tmp_path, 7201)


def test_real_cleanup_only_owns_its_child(tmp_path, monkeypatch):
    import os
    import subprocess
    import sys
    import uuid
    owner = uuid.uuid4().hex
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                             env=dict(os.environ, **{server.OWNER_ENV: owner}), start_new_session=True)
    try:
        record = {"owner": owner, "server_session": child.pid,
                  "owned": [server.identity(child.pid), server.identity(os.getpid())]}
        monkeypatch.setattr(server, "headroom", lambda: memory())
        result = server.cleanup(tmp_path, record)
        child.wait(timeout=5)
        assert not result["survivors"]
        assert {a["pid"] for a in result["actions"]} == {child.pid}
        assert child.returncode == -signal.SIGTERM
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
