import hashlib
import pytest
from dfm12.wave4_gemma31_download import verify_file
from dfm12.wave4_gemma31_fresh import endpoint_limit, MODEL


def test_lfs_verified_and_corruption_rejected(tmp_path):
    p = tmp_path / 'weight'
    p.write_bytes(b'abc')
    item = {'name': 'weight', 'size': 3, 'sha256': hashlib.sha256(b'abc').hexdigest()}
    assert verify_file(p, item)['local_sha256'] == item['sha256']
    p.write_bytes(b'xyz')
    with pytest.raises(ValueError, match='SHA256'):
        verify_file(p, item)


def test_git_blob_and_size(tmp_path):
    p = tmp_path / 'config'
    p.write_bytes(b'{}')
    item = {'name': 'config', 'size': 2, 'blob_id': hashlib.sha1(b'blob 2\0{}').hexdigest()}
    assert verify_file(p, item)['local_sha256']
    item['size'] = 3
    with pytest.raises(ValueError, match='size'):
        verify_file(p, item)


def test_fail_closed_wrong_teacher_and_context():
    assert endpoint_limit({'data': [{'id': MODEL, 'max_model_len': 32768}]}) == 32768
    for models in ([{'id': 'google/gemma-4-26B-A4B-it', 'max_model_len': 32768}],
                   [{'id': MODEL, 'max_model_len': 8192}],
                   [{'id': MODEL, 'max_model_len': 32768}, {'id': 'alias'}]):
        with pytest.raises(ValueError):
            endpoint_limit({'data': models})
