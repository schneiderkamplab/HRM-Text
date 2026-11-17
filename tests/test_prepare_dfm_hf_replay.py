import pytest

from scripts.prepare_dfm_hf_replay import source_specs


def test_only_agreement_data_can_bypass_hf():
    assert source_specs(['dbc', 'lexdk']) == []
    with pytest.raises(ValueError, match='local fallback forbidden'):
        source_specs(['unpublished_local_export'])


def test_opus_uses_published_hf_repository():
    specs = source_specs(['opus', 'dbc', 'lexdk'])
    assert len(specs) == 1
    assert specs[0].repo_id == 'schneiderkamplab/opus-da-en-permissive'
