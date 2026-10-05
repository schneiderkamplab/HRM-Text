import pytest

from dfm12.io import file_hash, load, write_json
from dfm12.wave_translation_release import attribution


def test_portuguese_card_preserves_variant():
    import yaml
    from dfm12.wave_translation_release import card_languages
    assert yaml.safe_load(card_languages('lt-pt_pt')) == {
        'language': ['lt', 'pt'], 'language_bcp47': ['lt', 'pt-PT']}
    assert yaml.safe_load(card_languages('lv-pt_pt'))['language_bcp47'] == ['lv', 'pt-PT']
    assert yaml.safe_load(card_languages('lt-lv')) == {'language': ['lt', 'lv']}


def test_attribution_preserves_both_pivot_legs(tmp_path):
    evidence = tmp_path / 'source.json'
    write_json(evidence, dict(entry=dict(status='approved', license='cc-by-4.0', url='https://example.org/source'),
        README='Original attribution', LICENSE='Original license'))
    leg = dict(attribution=str(evidence), license='cc-by-4.0', url='https://example.org/source', line=3)
    original = dict(method='exact_english_anchor_join', english_anchor='text', legs=[leg, leg])
    folder, files, licenses = tmp_path / 'export', {}, set()
    result = attribution(original, folder, files, licenses)
    assert result['english_anchor'] == 'text'
    assert len(result['legs']) == 2
    assert len(files) == 1
    assert licenses == {'cc-by-4.0'}
    assert file_hash(folder / result['legs'][0]['attribution']) == file_hash(evidence)
    assert original['legs'][0]['attribution'] == str(evidence)
    with pytest.raises(ValueError, match='license'):
        attribution(dict(leg, license='unknown'), folder, files, licenses)
    with pytest.raises(ValueError, match='mismatch'):
        attribution(dict(leg, url='https://example.org/different'), folder, files, licenses)
