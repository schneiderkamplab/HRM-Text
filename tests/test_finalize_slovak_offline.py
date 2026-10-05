import inspect
import pytest
from dfm12.io import write_json, file_hash
from scripts import finalize_slovak_offline as offline


def fixture(tmp_path):
    root, base = tmp_path/'root', tmp_path/'base'
    status = base/'release/component/status.json'
    write_json(status, dict(terminal=True, export_ready=True, input_sha256='abc'))
    write_json(base/'audit-ready/component/receipt.json', dict(sha256='abc'))
    write_json(root/'combined-audit-manifest.json', dict(components=[dict(component='component', sha256='abc')]))
    write_json(root/'recovery-drain.json', dict(components=[dict(component='component', status_sha256=file_hash(status))]))
    return root, base, status


def test_terminal_proof(tmp_path):
    root, base, _ = fixture(tmp_path)
    assert len(offline.terminal_entries(root, base)) == 1


@pytest.mark.parametrize('field,value', [('terminal', False), ('export_ready', False), ('input_sha256', 'changed')])
def test_changed_or_nonterminal_fails(tmp_path, field, value):
    root, base, path = fixture(tmp_path)
    state = dict(terminal=True, export_ready=True, input_sha256='abc')
    state[field] = value
    write_json(path, state)
    with pytest.raises(ValueError, match='proof mismatch'):
        offline.terminal_entries(root, base)


def test_no_source_controller_or_upload():
    source = inspect.getsource(offline)
    assert 'wave_repair' not in source
    assert 'upload=True' not in source
    assert '?mode=ro' in source
