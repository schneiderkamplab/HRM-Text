import copy

import pytest

from dfm12.io import file_hash, write_json
from scripts.dfm13_finalization_inventory import resolve_grouped_publications


def fixture(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = 'schneiderkamplab/dfm13-dala-v2-nl-compact'
    write_json('integration.json', {'complete': True})
    integration = dict(path='integration.json', sha256=file_hash('integration.json'))
    files = {'data/train.jsonl.gz': 'payload-hash'}
    write_json('receipt.json', {repo: dict(status='verified', revision='revision1',
        remote_payloads_sha256_verified=True, files=files)})
    write_json('exports_dfm13_dala_languages/inventory.json', dict(packages=[dict(
        hf_repo_id=repo, language='nl', files=files,
        integration_pins={'baseline': integration, 'recovery': integration})]))
    names = [f'dfm13_dala_v2_compact_nl_{pool}_{task}'
             for pool in ('baseline', 'recovery') for task in ('acceptability', 'correction')]
    inventory = dict(publication_destinations=[dict(repo=repo, components=[],
        publication_receipt='receipt.json')], components=[dict(name=n, integrated=True,
        recorded_hf_repo=None, integration_evidence={'source': '/local/train.jsonl'}) for n in names],
        publication_readiness=[dict(name=n, ready=False, requires_upload=True) for n in names])
    return inventory, repo


def test_grouped_publication_exposed_without_mutating_local_evidence(tmp_path, monkeypatch):
    inventory, repo = fixture(tmp_path, monkeypatch)
    evidence = copy.deepcopy([r['integration_evidence'] for r in inventory['components']])
    result = resolve_grouped_publications(inventory)
    for row in result['components']:
        assert row['hf_repo_id'] == repo and row['hf_revision'] == 'revision1'
        assert row['recorded_hf_repo'] is None
        assert row['publication_overlay']['local_view_is_derived']
        assert not row['publication_overlay']['byte_identity_claimed']
    assert [r['integration_evidence'] for r in result['components']] == evidence
    assert all(r['uploaded'] and not r['requires_upload'] for r in result['publication_readiness'])
    assert len(result['publication_destinations'][0]['components']) == 4
    assert resolve_grouped_publications(result) == result


@pytest.mark.parametrize('damage', ['integration', 'receipt', 'payload'])
def test_invalid_proof_not_promoted(tmp_path, monkeypatch, damage):
    inventory, repo = fixture(tmp_path, monkeypatch)
    if damage == 'integration':
        write_json('integration.json', {'changed': True})
    else:
        write_json('receipt.json', {repo: dict(status='verified', revision='revision1',
            remote_payloads_sha256_verified=damage != 'receipt', files={})})
    result = resolve_grouped_publications(inventory)
    assert all('hf_repo_id' not in r for r in result['components'])


def test_conflicting_repository_rejected(tmp_path, monkeypatch):
    inventory, _ = fixture(tmp_path, monkeypatch)
    inventory['components'][0]['hf_repo_id'] = 'different/repository'
    with pytest.raises(ValueError, match='conflicts'):
        resolve_grouped_publications(inventory)
