from dfm12 import wave4_compact_handoff as handoff
import pytest
from types import SimpleNamespace


def test_success_requires_complete_quota_and_no_active():
    row=('lt','math-code',6000,6000,0,10000)
    assert handoff.readiness([row],0,'complete')['state']=='ready_for_evidence_check'
    assert handoff.readiness([row],1,'complete')['state']=='waiting'
    assert handoff.readiness([row],0,'running')['state']=='waiting_final_complete_receipt'


def test_exhausted_budget_is_terminal_blocker():
    result=handoff.readiness([('lv','math-code',6000,1000,0,36000)],0,'running')
    assert result['state']=='blocked_attempt_budget'
    assert result['exhausted'][0]['accepted']==1000


def test_pid_exit_or_drained_does_not_launch():
    for phase in ('drained','blocked','interrupted_or_failed','approved_groups_finished'):
        assert handoff.readiness([('lt','math-code',6000,6000,0,20000)],0,phase)['state'].startswith('blocked')


def test_w4_is_private768_compact_all66_groups():
    import yaml
    from dfm12 import multilingual_quarter as shared
    c=handoff.controller()
    assert 768 in c.execute.__code__.co_consts and 64 in shared.execute.__code__.co_consts
    assert c.v6.adapters()[0] is handoff.compact
    rows=handoff.base.quotas(yaml.safe_load(handoff.base.CONFIG.read_text()))
    assert len(rows)==66 and sum(r['accepted_target'] for r in rows)==770000


def test_migrated_baltic_uses_recovery_proof_factory(tmp_path, monkeypatch):
    from dfm12 import compact_keep_recovery as recovery
    monkeypatch.setattr(handoff, 'load', lambda p: {'technical_review_adapter': 'dfm12.compact_keep_rationale'})
    verified = []
    c = SimpleNamespace(verify=lambda root: verified.append(root))
    monkeypatch.setattr(recovery, 'controller', lambda: c)
    assert handoff.baltic_proof_controller(tmp_path) is c
    assert verified == [tmp_path]
    assert handoff.baltic_client_module(tmp_path) == 'dfm12.compact_keep_recovery'


def test_unknown_baltic_adapter_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff, 'load', lambda p: {'technical_review_adapter': 'unapproved'})
    with pytest.raises(ValueError, match='Unknown'):
        handoff.baltic_proof_controller(tmp_path)
    with pytest.raises(ValueError, match='Unknown'):
        handoff.baltic_client_module(tmp_path)


def test_legacy_baltic_keeps_original_factory(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff, 'load', lambda p: {})
    c = object()
    verified = []
    monkeypatch.setattr(handoff.baltic, 'controller', lambda: c)
    monkeypatch.setattr(handoff.baltic, 'verify', lambda root, controller: verified.append((root, controller)))
    assert handoff.baltic_proof_controller(tmp_path) is c
    assert verified == [(tmp_path, c)]
    assert handoff.baltic_client_module(tmp_path) == 'dfm12.baltic_compact_successor'


def test_baltic384_proof_does_not_widen_w4(tmp_path, monkeypatch):
    from dfm12 import baltic_concurrency384 as upgrade
    monkeypatch.setattr(handoff, 'load', lambda p: dict(
        runtime_module='dfm12.baltic_concurrency384', runtime_concurrency_per_server=384,
        technical_review_adapter='dfm12.compact_keep_rationale'))
    verified = []
    c = SimpleNamespace(verify=lambda root: verified.append(root))
    monkeypatch.setattr(upgrade, 'controller', lambda: c)
    assert handoff.baltic_proof_controller(tmp_path) is c
    assert verified == [tmp_path]
    assert handoff.baltic_client_module(tmp_path) == 'dfm12.baltic_concurrency384'
    assert 768 in handoff.controller().execute.__code__.co_consts
    assert 384 not in handoff.controller().execute.__code__.co_consts


def test_io_baltic_proof_factory(tmp_path, monkeypatch):
    from dfm12 import baltic_io_runtime
    monkeypatch.setattr(handoff, 'load', lambda p: dict(
        runtime_module='dfm12.baltic_concurrency384', runtime_concurrency_per_server=384,
        technical_review_adapter='dfm12.compact_keep_rationale', io_runtime_module='dfm12.baltic_io_runtime'))
    c = SimpleNamespace(verify=lambda root: None)
    monkeypatch.setattr(baltic_io_runtime, 'controller', lambda: c)
    assert handoff.baltic_proof_controller(tmp_path) is c
    assert handoff.baltic_client_module(tmp_path) == 'dfm12.baltic_io_runtime'


def test_zero_spacing_baltic_proof_factory(tmp_path, monkeypatch):
    from dfm12 import baltic_zero_spacing
    manifest = dict(runtime_module='dfm12.baltic_concurrency384', runtime_concurrency_per_server=384,
        technical_review_adapter='dfm12.compact_keep_rationale', io_runtime_module='dfm12.baltic_io_runtime',
        zero_spacing_runtime_module='dfm12.baltic_zero_spacing', admission_spacing_seconds=0)
    monkeypatch.setattr(handoff, 'load', lambda p: manifest)
    verified = []
    c = SimpleNamespace(verify=lambda root: verified.append(root))
    monkeypatch.setattr(baltic_zero_spacing, 'controller', lambda: c)
    assert handoff.baltic_proof_controller(tmp_path) is c
    assert verified == [tmp_path]
    manifest['admission_spacing_seconds'] = .01
    with pytest.raises(ValueError, match='zero-spacing'):
        handoff.baltic_proof_controller(tmp_path)


def test_baltic768_exact_successor_factory(tmp_path, monkeypatch):
    from dfm12 import baltic_concurrency768
    manifest = dict(runtime_module='dfm12.baltic_concurrency384', runtime_concurrency_per_server=384,
        technical_review_adapter='dfm12.compact_keep_rationale', io_runtime_module='dfm12.baltic_io_runtime',
        zero_spacing_runtime_module='dfm12.baltic_zero_spacing', admission_spacing_seconds=0,
        concurrency768_runtime_module='dfm12.baltic_concurrency768', effective_concurrency_per_server=768)
    monkeypatch.setattr(handoff, 'load', lambda p: manifest)
    verified = []
    c = SimpleNamespace(verify=lambda root: verified.append(root))
    monkeypatch.setattr(baltic_concurrency768, 'controller', lambda: c)
    assert handoff.baltic_proof_controller(tmp_path) is c
    assert verified == [tmp_path]
    assert handoff.baltic_client_module(tmp_path) == 'dfm12.baltic_concurrency768'
    manifest['effective_concurrency_per_server'] = 384
    with pytest.raises(ValueError, match='Baltic768'):
        handoff.baltic_proof_controller(tmp_path)


def test_w4_offload_zero_spacing_and_no_shared_mutation(tmp_path):
    import asyncio
    from collections import Counter
    from dfm12.baltic_async_io import Owner
    from dfm12 import multilingual_quarter as shared
    owner = Owner()
    try:
        c = handoff.controller(owner)
        assert 768 in c.execute.__code__.co_consts
        gate = c.AdmissionGate(None, ['endpoint'], Counter(), {}, asyncio.Event())
        assert gate.spacing == 0
        assert gate.max_kv == .90
        assert shared.AdmissionGate(None, ['endpoint'], Counter(), {}, asyncio.Event()).spacing == .2
        assert 64 in shared.execute.__code__.co_consts
        c.write_json(tmp_path/'runtime.json', dict(concurrency_per_server=768,
            max_http_requests=6144, admission_spacing_seconds=.01))
        from dfm12.io import load
        emitted = load(tmp_path/'runtime.json')
        assert emitted['concurrency_per_server'] == 768
        assert emitted['max_http_requests'] == 6144
        assert emitted['admission_spacing_seconds'] == 0
    finally:
        owner.close()


def test_unapproved_runtime_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff, 'load', lambda p: dict(runtime_module='other'))
    with pytest.raises(ValueError, match='runtime'):
        handoff.baltic_proof_controller(tmp_path)
