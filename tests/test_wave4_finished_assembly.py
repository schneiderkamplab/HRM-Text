from dfm12.wave4_finished_assembly import CONTRACT, unready
from scripts.assemble_dfm13_additions import unready_reason


def test_contract_requires_completed_tokenization():
    entry = dict(publication_contract=CONTRACT, status='accepted_local_tokenized', uploaded=False)
    assert unready(entry) == 'wave4_tokenization_not_ready'
    entry.update(tokenization_performed=True, export_manifest_sha256='a'*64)
    assert unready_reason(entry) is None


def test_does_not_relabel_publication():
    assert unready(dict(publication_contract=CONTRACT, status='accepted_local_tokenized', uploaded=True))


def test_shared_proof_reuses_only_unchanged_identity(tmp_path):
    from dfm12.wave4_finished_assembly import pin_shared_proof, _proof_cache
    from scripts import assemble_dfm13_additions as api
    import pytest
    path = tmp_path/'proof'; path.write_text('original')
    sha = api.checksum(path); first = {}; second = {}
    pin_shared_proof(path, sha, first, api)
    pin_shared_proof(path, sha, second, api)
    assert first == second
    path.write_text('changed')
    with pytest.raises(ValueError, match='Hash mismatch'):
        pin_shared_proof(path, sha, {}, api)
    _proof_cache.clear()
