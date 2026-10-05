from pathlib import Path

import pytest

from dfm12 import source_instruction_probe as probe
from dfm12.io import file_hash, write_json


def sealed(root, count=7, model=probe.adapter.DEFAULT_MODEL):
    write_json(root / 'manifest.json', dict(count=count, model=model, pins={}))
    write_json(root / 'seal.json', dict(manifest_sha256=file_hash(root / 'manifest.json')))


def test_probe_exact_bound_and_teacher(tmp_path):
    sealed(tmp_path)
    assert probe.verify(tmp_path)['count'] == 7
    sealed(tmp_path, count=8)
    with pytest.raises(ValueError, match='seven-case'):
        probe.verify(tmp_path)
    sealed(tmp_path, model='google/gemma-4-31B-it')
    with pytest.raises(ValueError, match='seven-case'):
        probe.verify(tmp_path)


def test_probe_manifest_drift(tmp_path):
    sealed(tmp_path)
    write_json(tmp_path / 'manifest.json', {'changed': True})
    with pytest.raises(ValueError, match='seal drift'):
        probe.verify(tmp_path)


def test_existing_stage_executor_retained():
    c = probe.campaign.controller()
    assert c.v6.Stages.call.__module__.endswith('multilingual_calibration_v6')
    assert callable(c.stream_query)
