import copy
from pathlib import Path

import pytest

from dfm12.io import load, write_json
from dfm12 import wave_publication_holds as h


@pytest.mark.parametrize('component', sorted(h.COMPONENTS))
def test_release_fails_before_any_io(tmp_path, component):
    from dfm12.wave_release import release
    with pytest.raises(ValueError, match=h.STATUS):
        release(tmp_path / 'missing', component, upload=True)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('component', [
    'ParsiAI--FarsInstruct-fa-persian_qa', 'ParsiAI--FarsInstruct-fa-farstail',
    'ParsiAI--FarsInstruct-fa-parsinlu_comp', 'unrelated'])
def test_other_components_unaffected(component):
    assert h.publication_hold(component) is None
    h.require_publication_allowed(component)


def test_registry_preserves_payload_and_is_idempotent(tmp_path):
    registry, receipt = tmp_path / 'registry.json', tmp_path / 'hold.json'
    rows = [dict(name='dfm13_wave4_ParsiAI_FarsInstruct_fa_' + s,
        status='accepted_uploaded', repeat=3, counts={'accepted':7},
        output='preserved', output_sha256='hash', hf_revision='revision')
        for s in ('pn_sum', 'wiki_sum', 'persian_qa')]
    before = copy.deepcopy(rows)
    write_json(registry, dict(additions=rows, other='preserved'))
    write_json(receipt, dict(components=sorted(h.COMPONENTS), status=h.STATUS))
    assert len(h.mark_registry(registry, receipt)) == 2
    result = load(registry)
    assert result['additions'][2] == before[2]
    for old, new in zip(before[:2], result['additions'][:2]):
        assert new['status'] == h.STATUS
        assert all(new[k] == v for k,v in old.items() if k != 'status')
    h.mark_registry(registry, receipt)
    assert load(registry) == result


def test_missing_receipt_never_clears_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(h, 'RECEIPT', tmp_path / 'absent')
    for component in h.COMPONENTS:
        with pytest.raises(ValueError, match=h.STATUS):
            h.require_publication_allowed(component)


def test_advance_skips_even_uploaded_and_never_calls_process(tmp_path, monkeypatch):
    from scripts import advance_wave4_instructions as advance
    monkeypatch.chdir(tmp_path)
    root = Path('data/dfm13/wave4')
    for component in h.COMPONENTS:
        write_json(root / 'instructions' / component / 'receipt.json', {'counts':{'ready':1}})
        write_json(root / 'release' / component / 'publication.json', {'uploaded':True})
    def forbidden(*args, **kwargs):
        pytest.fail('held component reached processing/publication')
    monkeypatch.setattr(advance, 'process', forbidden)
    monkeypatch.setattr(advance, 'release', forbidden)
    def stop(_):
        raise InterruptedError('test loop finished')
    monkeypatch.setattr(advance.time, 'sleep', stop)
    with pytest.raises(InterruptedError):
        advance.main()
    assert load(root / 'release/advance-status.json')['components'] == dict.fromkeys(h.COMPONENTS, h.STATUS)
