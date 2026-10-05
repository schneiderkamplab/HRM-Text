import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from dfm12 import baltic_qa_quality_hold as h
from dfm12.io import file_hash, load, rows, write_json
from dfm12.wave_publication_holds import publication_hold, STATUS


@pytest.mark.parametrize('component', sorted(h.BALTIC_QA_COMPONENTS))
def test_fail_closed_release_and_stale_consumers(tmp_path, component):
    from dfm12.wave_release import release
    from scripts.tokenize_wave_releases import eligible, tokenize
    from scripts.assemble_dfm13_additions import unready_reason, verify_entry
    assert publication_hold(component) == STATUS
    with pytest.raises(ValueError, match=STATUS):
        release(tmp_path / 'missing', component, upload=True)
    stale = dict(name='dfm13_wave3_' + component, status='accepted_uploaded', uploaded=True,
        hf_revision='old', tokenization_performed=True, repeat=1)
    assert not eligible(stale)
    with pytest.raises(ValueError, match=STATUS):
        tokenize(stale)
    assert unready_reason(stale) == STATUS
    with pytest.raises(ValueError, match=STATUS):
        verify_entry(stale, {}, {})
    assert not list(tmp_path.iterdir())


def test_preexisting_assembly_cannot_bypass_hold(tmp_path):
    from scripts.assemble_dfm13_additions import verify_assembly
    write_json(tmp_path / 'assembly.json', dict(ready_additions=[dict(name=sorted(h.NAMES)[0])]))
    with pytest.raises(ValueError, match=STATUS):
        verify_assembly(tmp_path)


def test_registry_idempotent_preserves_published_fields(tmp_path):
    registry, receipt = tmp_path / 'registry.json', tmp_path / 'reason.json'
    entries = [dict(name=n, output=n, output_sha256='sha', hf_revision='commit',
                    status='accepted_uploaded', repeat=1, rows=10, tokenized_tokens=50)
               for n in sorted(h.NAMES)]
    before = copy.deepcopy(entries)
    write_json(registry, dict(additions=entries + [{'name':'untouched'}]))
    write_json(receipt, dict(components=sorted(h.BALTIC_QA_COMPONENTS), status=STATUS,
        review_sha256=h.REVIEW_SHA, admission_authorized=False,
        inputs={e['output']:e['output_sha256'] for e in entries}))
    h.mark_registry(receipt, registry)
    result = load(registry)
    assert result['additions'][-1] == {'name':'untouched'}
    for a,b in zip(before,result['additions']):
        assert all(b[k] == v for k,v in a.items() if k != 'status')
        assert b['status'] == STATUS and b['training_eligible'] is False
        assert b['quality_hold']['receipt_sha256'] == file_hash(receipt)
    h.mark_registry(receipt, registry)
    assert load(registry) == result
    receipt.unlink()
    assert all(publication_hold(c) == STATUS for c in h.BALTIC_QA_COMPONENTS)


def test_other_sources_not_held():
    from scripts.tokenize_wave_releases import eligible
    assert eligible(dict(name='dfm13_wave3_baltic_lt_summary_newgenltu',
        status='accepted_uploaded', uploaded=True, hf_revision='x'))
    assert publication_hold('baltic_lt_aya') is None


def test_blind_packet_contract():
    assert 'NOT a verified article or gold' in h.PROMPT
    assert 'earlier history' in h.PROMPT
    assert 'keep false' in h.PROMPT
    assert h.MODEL == 'google/gemma-4-31B-it'


def test_warning_changes_only_card(tmp_path):
    entry = dict(hf_repo_id='org/test', hf_revision='original')
    write_json(tmp_path / 'registry-held.json', [entry])
    card = tmp_path / 'downloaded.md'
    card.write_text('---\nlicense: cc-by-4.0\n---\nOriginal attribution\n')
    original = card.read_bytes()
    sibling = SimpleNamespace(rfilename='data/train.jsonl', blob_id='same',size=17,lfs=None)
    class API:
        def dataset_info(self, *args, **kwargs):
            return SimpleNamespace(sha='before',siblings=[sibling])
        def upload_file(self, **kwargs):
            assert kwargs['parent_commit'] == 'before'
            assert kwargs['path_in_repo'] == 'README.md'
            assert kwargs['path_or_fileobj'].startswith(original)
            card.write_bytes(kwargs['path_or_fileobj'])
            return SimpleNamespace(oid='warning')
    result = h.warn_hub(tmp_path, API(), lambda **kwargs: card)
    assert result[0]['original_data_revision'] == 'original'
    assert result[0]['warning_revision'] == 'warning'
    assert result[0]['unchanged_non_card_files'] == 1


def test_baltic_controller_does_not_process_held(tmp_path, monkeypatch):
    from scripts import advance_baltic_instructions as advance
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(advance, 'BALTIC_RELEASE_COMPONENTS', h.BALTIC_QA_COMPONENTS)
    monkeypatch.setattr(advance, 'process', lambda *a: pytest.fail('held processing'))
    monkeypatch.setattr(advance, 'release', lambda *a, **kw: pytest.fail('held release'))
    def stop(_):
        raise InterruptedError
    monkeypatch.setattr(advance.time, 'sleep', stop)
    with pytest.raises(InterruptedError):
        advance.main()
    assert load(Path('data/dfm13/baltic/release/advance-status.json'))['components'] == dict.fromkeys(h.BALTIC_QA_COMPONENTS, STATUS)
