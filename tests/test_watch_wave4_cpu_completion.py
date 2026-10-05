from dfm12.io import write_json,file_hash
from scripts.watch_wave4_cpu_completion import snapshot,timeout_exit
import pytest


def test_exact_terminal_timeout_only(tmp_path):
    log=tmp_path/'log'
    log.write_text('Traceback\nTimeoutError: Audit enqueue lock remained busy\n')
    assert timeout_exit(log)
    log.write_text('TimeoutError: Audit enqueue lock remained busy\nValueError: later failure\n')
    assert not timeout_exit(log)


def test_no_false_global_or_additive_completion(tmp_path):
    base=tmp_path/'base';root=tmp_path/'additive'
    assert not snapshot(base,root)['both_cpu_complete']
    main=base/'parallel-preparation.json'
    write_json(main,dict(status='direct_and_pivot_preparation_finished'))
    write_json(base/'audit/component-job-coverage.json',dict(exact_payload_coverage=True))
    write_json(base/'audit/translation-manifest.json',dict(preparation_sha256=file_hash(main)))
    assert snapshot(base,root)['selection_activated']
    assert not snapshot(base,root)['both_cpu_complete']
    write_json(root/'enqueue-complete.json',dict(cpu_preparation_complete=True))
    state=snapshot(base,root)
    assert state['both_cpu_complete'] and not state['global_ready'] and not state['audits_complete']
    write_json(main,dict(status='changed'))
    assert not snapshot(base,root)['both_cpu_complete']


def test_live_waiter_is_never_restarted(tmp_path,monkeypatch):
    from scripts import watch_wave4_cpu_completion as m
    contract=tmp_path/'contract.json'
    write_json(contract,dict(base=str(tmp_path/'base'),root=str(tmp_path/'root'),process={'pid':123}))
    monkeypatch.setattr(m,'alive',lambda pin:True)
    monkeypatch.setattr(m.subprocess,'Popen',lambda *a,**k:pytest.fail('Must not restart live waiter'))
    def stop(seconds):raise InterruptedError('test observation complete')
    monkeypatch.setattr(m.time,'sleep',stop)
    with pytest.raises(InterruptedError):m.run(contract)


def test_unknown_terminal_failure_is_not_retried(tmp_path,monkeypatch):
    from scripts import watch_wave4_cpu_completion as m
    contract=tmp_path/'contract.json';log=tmp_path/'log';log.write_text('ValueError: source drift\n')
    write_json(contract,dict(base=str(tmp_path/'base'),root=str(tmp_path/'root'),process={'pid':123},log=str(log)))
    monkeypatch.setattr(m,'alive',lambda pin:False)
    monkeypatch.setattr(m.subprocess,'Popen',lambda *a,**k:pytest.fail('Must not retry unknown failure'))
    with pytest.raises(RuntimeError,match='not the approved'):m.run(contract)
