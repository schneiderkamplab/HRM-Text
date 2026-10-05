from contextlib import nullcontext

import pytest

from scripts import authorize_wave4_gpu_release as gate
from dfm12.io import load, write_json


@pytest.mark.parametrize('terminal_ok,idle', [(False, True), (True, False), (True, True)])
def test_release_requires_terminal_and_quiescence(tmp_path, monkeypatch, terminal_ok, idle):
    monkeypatch.setattr(gate.watcher, 'WORK', tmp_path)
    monkeypatch.setattr(gate.watcher, 'CAMPAIGN', tmp_path)
    monkeypatch.setattr(gate, 'lock', lambda _: nullcontext())
    write_json(tmp_path / 'release-authorization.json', dict(no_additional_gpu_work=True,
        cpu_recovery_may_continue=True, authorize_existing_dfm12_resume=True))
    write_json(tmp_path / 'armed.json', dict(deadline=float('inf')))
    write_json(tmp_path / 'supervisor-launch.json', {})
    write_json(tmp_path / 'terminal.json', {})
    monkeypatch.setattr(gate.watcher, 'verify_pins', lambda _: None)
    monkeypatch.setattr(gate.watcher, 'pass_finished', lambda *_: terminal_ok)
    monkeypatch.setattr(gate.watcher, 'same', lambda _: True)
    monkeypatch.setattr(gate.watcher, 'gate_servers', lambda: (idle, {}))
    def stop_poll(_):
        raise TimeoutError('test polling boundary')
    monkeypatch.setattr(gate.time, 'sleep', stop_poll)
    if terminal_ok and idle:
        gate.main()
        assert gate.watcher.release_authorized(load(tmp_path / 'gpu-work-complete.json'))
    else:
        with pytest.raises(TimeoutError):
            gate.main()
        assert not (tmp_path / 'gpu-work-complete.json').exists()
