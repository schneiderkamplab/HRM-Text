import copy
from pathlib import Path

import pytest
import yaml

from dfm12.wave4_synthetic_campaign import quotas


def test_all_languages_and_families_have_full_targets():
    config=yaml.safe_load(Path('config/dfm13_wave4_synthetic.yaml').read_text())
    result=quotas(config)
    assert len(result)==66
    assert sum(row['accepted_target'] for row in result)==770000
    assert all(row['repo_id'].startswith('schneiderkamplab/dfm13-') for row in result)
    altered=copy.deepcopy(config)
    altered['languages']['fa']=2
    with pytest.raises(ValueError,match='70K'):
        quotas(altered)


def test_cannot_disable_audit():
    config=yaml.safe_load(Path('config/dfm13_wave4_synthetic.yaml').read_text())
    config['audit_every_candidate']=False
    with pytest.raises(ValueError,match='policy'):
        quotas(config)
