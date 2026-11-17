import json
from pathlib import Path
import pytest
from scripts.render_experiment_node import ROOT, render


def test_all_recipes_are_rebased_without_launch(tmp_path):
    templates = ROOT / 'config/deployment/dfm11'
    profile = json.loads((ROOT / 'config/deployment/node2.json').read_text())
    result = render(profile, json.loads((templates / 'commands.json').read_text()), templates, tmp_path / 'out')
    assert len(result['commands']) == 15
    assert not result['launch_enabled']
    assert set(result['initial_runs']) <= result['commands'].keys()
    for command in result['commands'].values():
        assert '/work/dfm/HRM-Text/' not in ' '.join(command)
        assert '${repo_root}' not in ' '.join(command)
        assert '${env_root}' not in ' '.join(command)
    configs = list((tmp_path / 'out').glob('*.yaml'))
    assert len(configs) == 4
    assert all('${oc.env:HRM_REPO_ROOT}' not in p.read_text() for p in configs)


def test_existing_output_is_preserved(tmp_path):
    profile = dict(launch_enabled=False, repo_root='/repo', env_root='/env')
    with pytest.raises(FileExistsError):
        render(profile, {'runs': {}}, tmp_path, tmp_path)
