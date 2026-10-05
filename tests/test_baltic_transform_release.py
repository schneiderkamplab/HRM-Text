import pytest
from dfm12.io import file_hash, write_json
from dfm12.wave_release import source_attribution, baltic_transform_pin


def test_parlamint_pin_and_row_integrity(tmp_path):
    root = tmp_path / 'baltic'
    path = root / 'parlamint/lv/documents.jsonl'
    path.parent.mkdir(parents=True)
    path.write_text('{}\n')
    sha = file_hash(path)
    write_json(path.parent / 'receipt.json', dict(sha256=sha, archive_sha256='archive',
               license='CC-BY-4.0', url='https://example.org/archive', version='5.0'))
    row = dict(source='parlamint_lv', file=str(path), file_sha256=sha, row=3)
    result = source_attribution(root, 'transform-parlamint_lv', row, 'denoising')
    assert result['license'] == 'cc-by-4.0'
    assert result['row'] == 3
    with pytest.raises(ValueError, match='provenance'):
        source_attribution(root, 'transform-parlamint_lv', {**row, 'file_sha256': 'wrong'}, 'denoising')
    baltic_transform_pin.cache_clear()
    path.write_text('changed')
    with pytest.raises(ValueError, match='source changed'):
        source_attribution(root, 'transform-parlamint_lv', row, 'denoising')


def test_other_transform_sources_remain_held(tmp_path):
    with pytest.raises(ValueError, match='separate source-hold'):
        source_attribution(tmp_path / 'baltic', 'transform-baltic_lt_finepdfs', {}, 'denoising')
