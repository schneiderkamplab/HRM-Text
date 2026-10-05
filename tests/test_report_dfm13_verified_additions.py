import hashlib
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.report_dfm13_verified_additions import language, lengths, remote


def test_language_requires_explicit_label():
    assert language({'language': 'lt'}) == 'lt'
    assert language({'name': 'english', 'metadata': {'language': 'en'}}) == 'unknown'
    assert language({'language': None}) == 'unknown'


def test_lengths_preserve_row_order(tmp_path):
    np.save(tmp_path/'inst_len.npy', np.array([3, 8]))
    np.save(tmp_path/'resp_len.npy', np.array([4, 2]))
    assert list(lengths({'parts': [{'path': str(tmp_path)}]})) == [7, 10]


def test_length_mismatch_refused(tmp_path):
    np.save(tmp_path/'inst_len.npy', np.array([3, 8]))
    np.save(tmp_path/'resp_len.npy', np.array([4]))
    with pytest.raises(ValueError):
        list(lengths({'parts': [{'path': str(tmp_path)}]}))


@pytest.mark.parametrize('corrupt', [False, True])
def test_remote_pinned_lfs_and_git(tmp_path, monkeypatch, corrupt):
    import huggingface_hub
    (tmp_path/'data').mkdir()
    contents = {'data/train.jsonl': b'data', 'README.md': b'card', 'manifest.json': b'{}'}
    siblings = []
    for name, value in contents.items():
        (tmp_path/name).write_bytes(value)
        sha = hashlib.sha256(value).hexdigest()
        blob = hashlib.sha1(b'blob '+str(len(value)).encode()+b'\0'+value).hexdigest()
        siblings.append(SimpleNamespace(rfilename=name, blob_id=blob,
            lfs=SimpleNamespace(sha256='wrong' if corrupt else sha) if name.startswith('data/') else None))
    api = SimpleNamespace(repo_info=lambda *a, **k: SimpleNamespace(sha='revision', siblings=siblings))
    monkeypatch.setattr(huggingface_hub, 'HfApi', lambda: api)
    entry = dict(name='test', hf_repo_id='repo', hf_revision='revision',
                 output=str(tmp_path/'data/train.jsonl'), output_sha256=hashlib.sha256(b'data').hexdigest())
    if corrupt:
        with pytest.raises(ValueError, match='LFS hash'):
            remote(entry)
    else:
        name, result = remote(entry)
        assert name == 'test' and len(result['files']) == 3
