import pytest
from dfm12.inheritance_delta import classify
from dfm12.inheritance_delta import part_reference
from dfm12.io import write_json
import numpy as np


def test_replacements_are_not_additive_duplicates():
    old=[dict(name='keep',manifest_sha256='a'),dict(name='identity',manifest_sha256='b')]
    new=[*old[:1],dict(name='identity',manifest_sha256='c'),dict(name='new',manifest_sha256='d')]
    assert classify(old,new)==dict(keep='unchanged',identity='replacement',new='new')


def test_missing_or_duplicate_source_fails_closed():
    row=dict(name='a',manifest_sha256='x')
    with pytest.raises(ValueError):classify([row],[])
    with pytest.raises(ValueError):classify([row],[row,row])


def test_token_part_binds_source_and_bounds(tmp_path):
    source=tmp_path/'source.jsonl';source.write_text('{}\n')
    part=tmp_path/'part';part.mkdir()
    for key,value in dict(tokens=[1,2,3],inst_start=[0],inst_len=[1],resp_start=[1],resp_len=[2]).items():
        np.save(part/(key+'.npy'),np.array(value,dtype=np.uint64))
    metadata=dict(max_seq_len=4096,source_mtime=int(source.stat().st_mtime),source_size=source.stat().st_size)
    write_json(part/'metadata.json',metadata)
    result=part_reference(part,source)
    assert result['rows']==1 and result['tokens']==3
    np.save(part/'resp_start.npy',np.array([3],dtype=np.uint64))
    with pytest.raises(ValueError,match='outside'):part_reference(part,source)
    write_json(part/'metadata.json',dict(metadata,source_size=999))
    with pytest.raises(ValueError,match='drift'):part_reference(part,source)
