import gzip
import json

import pytest

from dfm12 import verify_multilingual_completed as v
from dfm12.io import write_json


def empty_package(root):
    (root / 'data').mkdir()
    (root / 'metadata').mkdir()
    for family in v.FAMILIES:
        for directory, prefix in [('data', 'train'), ('metadata', 'audits')]:
            with gzip.open(root / directory / f'{prefix}-{family}.jsonl.gz', 'wt'):
                pass
    write_json(root / 'metadata/manifest.json', dict(
        language='de', rows=35000, families={}, origins={}, files={}))


def test_recount_rejects_empty_package(tmp_path):
    empty_package(tmp_path)
    with pytest.raises(ValueError, match='row count'):
        v.verify_package(tmp_path)


def test_rejects_unpaired_audit(tmp_path):
    empty_package(tmp_path)
    with gzip.open(tmp_path / 'metadata/audits-tool-dialogue.jsonl.gz', 'wt') as stream:
        stream.write('{}\n')
    with pytest.raises(ValueError, match='length mismatch'):
        v.verify_package(tmp_path)


def test_rejects_changed_native_tools(tmp_path):
    empty_package(tmp_path)
    row = dict(id='x', messages=[], tools=[{'type': 'function'}])
    audit = dict(id='x', training_row_sha256=v.digest(row), fingerprint='wrong')
    for directory, prefix, value in [('data', 'train', row), ('metadata', 'audits', audit)]:
        with gzip.open(tmp_path / directory / f'{prefix}-tool-dialogue.jsonl.gz', 'wt') as stream:
            stream.write(json.dumps(value) + '\n')
    with pytest.raises(ValueError, match='fingerprint mismatch'):
        v.verify_package(tmp_path)
