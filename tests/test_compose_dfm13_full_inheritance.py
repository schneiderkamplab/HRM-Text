import json
import pytest
from scripts.compose_dfm13_full_inheritance import inheritance


def test_unready_handoff_rejected(tmp_path):
    path = tmp_path/'handoff.json'; path.write_text('{"ready": false}')
    with pytest.raises(ValueError, match='not ready'):
        inheritance(path)


def test_changed_handoff_dependency_rejected(tmp_path):
    child = tmp_path/'inheritance.json'; child.write_text('{}')
    path = tmp_path/'handoff.json'
    path.write_text(json.dumps({'ready': True, 'full_reference': str(child),
                                'full_reference_sha256': '0'*64}))
    with pytest.raises(ValueError, match='handoff drift'):
        inheritance(path)
