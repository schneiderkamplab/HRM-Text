from pathlib import Path
import pytest
from dfm12.io import write_json
from scripts import dfm16_english_production as production


def test_no_implicit_self_review_admission(tmp_path, monkeypatch):
    monkeypatch.setattr(production, 'verify', lambda root: None)
    write_json(tmp_path/'selected-policy.json', {'policy':'odin_specialists'})
    with pytest.raises(ValueError, match='explicit Odin'):
        production.materialize(tmp_path)
    assert not (tmp_path/'accepted').exists()


def test_combined_policy_cannot_fall_back_to_odin(tmp_path, monkeypatch):
    monkeypatch.setattr(production, 'verify', lambda root: None)
    write_json(tmp_path/'selected-policy.json', {'policy':'combined', 'self_review_authorized':True})
    with pytest.raises(ValueError):
        production.materialize(tmp_path)


def test_changed_dependency_blocks_execution(tmp_path):
    dependency=tmp_path/'source.json'
    dependency.write_text('changed')
    write_json(tmp_path/'authorization.json', {'pins':{str(dependency):'wrong hash'}})
    with pytest.raises(ValueError, match='changed production dependency'):
        production.verify(tmp_path)
