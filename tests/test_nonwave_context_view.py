import json

import numpy as np
import pytest

from dfm12 import nonwave_context_view as view
from dfm12.io import file_hash, load, write_json
from scripts import assemble_dfm13_additions as api


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    source=tmp_path/'source.jsonl'
    rows=[dict(id=str(i),messages=[dict(role='user',content='full context'),
        dict(role='assistant',content='full answer')],target_message_index=1) for i in range(3)]
    source.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    root=tmp_path/'parent';part=root/'part-000000.jsonl';part.mkdir(parents=True)
    lengths=np.array([4096,4097,10],dtype=np.uint64);starts=np.array([0,4096,8193],dtype=np.uint64)
    for k,a in dict(tokens=np.arange(8203,dtype=np.uint32)%100,inst_start=starts,
        inst_len=lengths-2,resp_start=starts+lengths-2,resp_len=np.array([2,2,2])).items():np.save(part/(k+'.npy'),a)
    write_json(root/'tokenizer_info.json',{})
    receipt=dict(schema='dfm13-nonwave-target-only-tokenization-v1',source_sha256=file_hash(source),
        hard_truncation=False,regex_fix=False,target_policy='final_assistant_only_native_gemma',
        output=str(root),rows=3,tokens=8203,files={str(p):file_hash(p) for p in root.rglob('*') if p.is_file()})
    rp=tmp_path/'receipt.json';write_json(rp,receipt)
    e=dict(name='jjzha_croco',output=str(source),output_sha256=file_hash(source),rows=3,
        tokenized_path=str(root),tokenization_receipt=str(rp),tokenization_receipt_sha256=file_hash(rp),
        target_policy=receipt['target_policy'],repeat=1,hf_repo_id='test/repo',hf_revision='pin')
    path=view.build(e,tmp_path/'view');e.update(context_view=str(path),context_view_sha256=file_hash(path))
    monkeypatch.setattr('dfm12.nonwave_assembly.publication',lambda parent,pins,api:dict(source=parent['output']))
    monkeypatch.setattr(api,'token_contract',lambda *a:dict(vocab_size=100))
    monkeypatch.setattr(api,'verify_native_sample',lambda *a:dict(exact=True))
    return e,path,source,rows


def test_fit_view_retains_parent_bytes_and_masks(fixture):
    e,path,source,rows=fixture
    result=view.verify(e,dict(vocab_size=100),{},api)
    assert result['rows']==2 and result['tokens']==4106
    assert result['context_selection']['long_rows']==1
    assert source.read_text()==''.join(json.dumps(r)+'\n' for r in rows)
    m=load(path);assert open(m['source']).read()==json.dumps(rows[0])+'\n'+json.dumps(rows[2])+'\n'
    assert load(path.parent/'long-rows.jsonl')['id']=='1'


def test_existing_view_never_overwritten(fixture):
    e,path,_,_=fixture
    with pytest.raises(ValueError,match='Preserve'):
        view.build(e,path.parent)


def test_changed_parent_rejected(fixture):
    e,_,_,_=fixture;e['hf_revision']='replacement'
    with pytest.raises(ValueError,match='parent registry'):
        view.verify(e,dict(vocab_size=100),{},api)


@pytest.mark.parametrize('file', ['train.jsonl','long-rows.jsonl','tokens/part-000000.jsonl/parent_rows.npy'])
def test_tampered_view_files_rejected(fixture,file):
    e,path,_,_=fixture
    with (path.parent/file).open('ab') as out:out.write(b'altered')
    with pytest.raises(ValueError):view.verify(e,dict(vocab_size=100),{},api)


def test_context_policy_cannot_expand(fixture):
    e,path,_,_=fixture;m=load(path);m['context_limit']=4097;write_json(path,m)
    e['context_view_sha256']=file_hash(path)
    with pytest.raises(ValueError,match='policy'):
        view.verify(e,dict(vocab_size=100),{},api)
