import numpy as np
import pytest
from dfm12.io import write_json
from scripts.sample_dfm13_final import validate_sample, inherited_short_rows


def fixture(root):
    (root/'epoch_0').mkdir()
    np.save(root/'tokens.npy',np.array([1,2,3,4],dtype=np.uint32))
    for k,v in {'inst_start':[0],'inst_len':[2],'resp_start':[2],'resp_len':[2]}.items():
        np.save(root/'epoch_0'/(k+'.npy'),np.array(v,dtype=np.uint64))
    write_json(root/'metadata.json',dict(tokenizer_info={'vocab_size':10},max_seq_len=4,total_length=4))


def test_full_scan(tmp_path):
    fixture(tmp_path)
    assert validate_sample(tmp_path)['epoch_tokens']==4


def test_bad_pointer(tmp_path):
    fixture(tmp_path)
    np.save(tmp_path/'epoch_0/resp_start.npy',np.array([4],dtype=np.uint64))
    with pytest.raises(ValueError,match='Token bounds'):validate_sample(tmp_path)


def test_bad_vocab(tmp_path):
    fixture(tmp_path)
    np.save(tmp_path/'tokens.npy',np.array([1,2,3,99],dtype=np.uint32))
    with pytest.raises(ValueError,match='vocabulary'):validate_sample(tmp_path)


def test_inherited_short_response_requires_exact_approval(tmp_path):
    fixture(tmp_path)
    np.save(tmp_path/'epoch_0/inst_len.npy',np.array([3],dtype=np.uint64))
    np.save(tmp_path/'epoch_0/resp_start.npy',np.array([3],dtype=np.uint64))
    np.save(tmp_path/'epoch_0/resp_len.npy',np.array([1],dtype=np.uint64))
    with pytest.raises(ValueError,match='Unapproved short'):validate_sample(tmp_path)
    allowed=inherited_short_rows(tmp_path)
    assert validate_sample(tmp_path,allowed)['epoch_tokens']==4
    np.save(tmp_path/'epoch_0/resp_start.npy',np.array([2],dtype=np.uint64))
    with pytest.raises(ValueError,match='Unapproved short'):validate_sample(tmp_path,allowed)
    np.save(tmp_path/'epoch_0/resp_start.npy',np.array([3],dtype=np.uint64))
    allowed.update(allowed)
    with pytest.raises(ValueError,match='Missing inherited'):validate_sample(tmp_path,allowed)


def test_empty_inherited_response_rejected(tmp_path):
    fixture(tmp_path)
    np.save(tmp_path/'epoch_0/resp_len.npy',np.array([0],dtype=np.uint64))
    with pytest.raises(ValueError,match='Inherited empty'):inherited_short_rows(tmp_path)
