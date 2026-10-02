import pytest
from scripts import dfm13_repochat_grounded_repairs as m


def test_sealed_no_overwrite(tmp_path):
    path = tmp_path / 'sealed.json'
    m.sealed(path, {'admission': False})
    m.sealed(path, {'admission': False})
    with pytest.raises(ValueError):
        m.sealed(path, {'admission': True})
    assert m.b.load(path) == {'admission': False}


def test_source_hash_required(tmp_path):
    files = tmp_path / 'files'; files.mkdir()
    path = files / 'x.py'; path.write_text('return 1\nreturn 2\n')
    snapshot = tmp_path / 'snapshot.json'
    m.b.save(snapshot, {'files': {'x.py': m.b.file_sha(path)}, 'commit': 'a'*40})
    assert m.read_evidence(snapshot, [('x.py', 2, 1)])[0]['text'] == '2: return 2'
    path.write_text('changed')
    with pytest.raises(ValueError):
        m.read_evidence(snapshot, [('x.py', 1, 1)])


def test_prompt_bounds_and_no_execution():
    assert '150-350 words' in m.SYSTEM
    assert 'specific retrieved file' in m.SYSTEM
    assert 'label inference' in m.SYSTEM
    assert 'Do not\nclaim execution/testing' in m.SYSTEM
