from scripts.dfm13_specification_reconciliation import disposition, gates, valid_pin
from dfm12.io import file_hash
from scripts import dfm13_specification_reconciliation as module


def test_missing_membership_is_not_disposed():
    components = {'a': {'stage': 'verified_integrated'}, 'b': {'stage': 'not_in_current_verified_assembly'}}
    assert disposition(['a', 'b'], components) == 'pending_integration'
    assert disposition([], components) == 'unresolved'


def test_holds_are_explicit_dispositions():
    components = {'a': {'stage': 'verified_integrated'}, 'b': {'stage': 'held'}}
    assert disposition(['b'], components) == 'held'
    assert disposition(['a', 'b'], components) == 'integrated_with_holds'


def test_gates_require_enumerated_evidence():
    assert not any(gates([], []).values())
    result = gates([{'disposition': 'pending_integration'}], [{'ready': True}])
    assert not result['all_specifications_disposed']
    result = gates([{'disposition': 'held'}], [{'ready': False}])
    assert result['all_specifications_disposed']
    assert not result['all_integrated_packages_locally_upload_ready']


def test_drift_fails(tmp_path):
    p = tmp_path/'proof.json'
    p.write_text('{}')
    value = {'path': str(p), 'sha256': file_hash(p)}
    assert valid_pin(value)
    p.write_text('{"changed":true}')
    assert not valid_pin(value)


def test_watch_releases_both_receipts_only_for_final_matching_composition(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path/'staged'
    root.mkdir()
    final = tmp_path/'data/dfm13/verified-all-finished-additions-20261005-v1'
    ref = {'root': str(final), 'assembly_sha256': 'final-sha'}
    module.write_json('data/dfm13/authoritative-additions.json', ref)
    module.write_json('data/dfm13/authoritative-composition.json', {'additions_sha256': 'final-sha'})
    def scan(path):
        module.write_json(path, {'valid': True})
        return {'valid': True}
    monkeypatch.setattr(module, 'scan_inherited_lengths', scan)
    monkeypatch.setattr(module, 'build', lambda: {})
    monkeypatch.setattr(module, 'reconcile', lambda _: dict(
        all_specifications_disposed=True, all_integrated_packages_locally_upload_ready=True,
        inherited_dfm12_coverage_verified=True, disposition_counts={'integrated': 1}, publication_unready=[]))
    module.watch(root/'reconciliation.json')
    canonical = tmp_path/'data/dfm13/all-source-finalization-20261004-v1'
    for name in ('reconciliation.json', 'sampling-reconciliation.json'):
        result = module.load(canonical/name)
        assert result['assembly_sha256'] == 'final-sha'
        assert result['sampling_authorized'] is True
        assert result['all_specifications_disposed'] is True


def test_watch_rejects_invalid_inherited_indices(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(module, 'scan_inherited_lengths', lambda _: {'valid': False})
    with pytest.raises(ValueError, match='would drop rows'):
        module.watch(tmp_path/'reconciliation.json')
    assert not (tmp_path/'completion.json').exists()
