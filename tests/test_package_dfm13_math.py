import json
import pytest
from dfm12.io import file_hash, write_json
from scripts import package_dfm13_math as package


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(package.math_assembly, 'ROWS', 1)
    (tmp_path / 'data').mkdir()
    row = dict(id='one', messages=[dict(role='user', content='Problem'),
        dict(role='assistant', content='Solution')], target_message_index=1,
        metadata=dict(split='train', source=package.math_assembly.REPO,
                      revision=package.math_assembly.REVISION, license='mit'))
    (tmp_path / 'data/train.jsonl').write_text(json.dumps(row)+'\n')
    write_json(tmp_path / 'manifest.json', dict(repeat=5, physical_repetition=1, rows=1,
        source_sha256=file_hash(tmp_path / 'data/train.jsonl'),
        files={'data/train.jsonl':file_hash(tmp_path / 'data/train.jsonl')}))
    return tmp_path


def test_metadata_repeat_only(root):
    assert package.validate(root)['rows'] == 1


def test_tamper(root):
    (root / 'data/train.jsonl').write_text('{}\n')
    with pytest.raises(ValueError, match='hash/path'):
        package.validate(root)


def test_physical_repeat_forbidden(root):
    manifest = json.loads((root / 'manifest.json').read_text())
    manifest['physical_repetition'] = 5
    write_json(root / 'manifest.json', manifest)
    with pytest.raises(ValueError, match='metadata only'):
        package.validate(root)


def test_duplicate_even_with_updated_hash(root):
    path = root / 'data/train.jsonl'
    path.write_text(path.read_text()*2)
    manifest = json.loads((root / 'manifest.json').read_text())
    manifest['files']['data/train.jsonl'] = file_hash(path)
    manifest['source_sha256'] = file_hash(path)
    write_json(root / 'manifest.json', manifest)
    with pytest.raises(ValueError, match='Duplicate'):
        package.validate(root)


def test_preserves_existing(root):
    with pytest.raises(ValueError, match='Fresh package'):
        package.prepare(root)
