import pytest

from scripts import handoff_dfm13_pending_arena as h


@pytest.mark.parametrize('names', [[], ['prism'], ['comparia', 'comparia'], ['unknown']])
def test_only_explicit_supported_components(tmp_path, names):
    with pytest.raises(ValueError, match='Explicit non-PRISM'):
        h.prepare(tmp_path/'screen', tmp_path/'original', names, tmp_path/'output')
    assert not (tmp_path/'output').exists()


def test_hash_accepts_json_path_strings(tmp_path):
    path = tmp_path/'evidence'
    path.write_text('pinned')
    assert h.sha256(str(path)) == h.sha256(path)
