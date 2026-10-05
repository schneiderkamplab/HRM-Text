from types import SimpleNamespace
import pytest
from dfm12.io import file_hash
from scripts.upload_dfm13_ready150 import verify_remote


def test_remote_verification_binds_exact_revision_and_hash(tmp_path, monkeypatch):
    import huggingface_hub
    payload=tmp_path/'train.jsonl';payload.write_text('accepted\n')
    calls=[]
    def download(repo,name,**kwargs):
        calls.append((repo,name,kwargs['revision']))
        return str(payload)
    monkeypatch.setattr(huggingface_hub,'hf_hub_download',download)
    api=SimpleNamespace(list_repo_files=lambda *args,**kwargs:['.gitattributes','data/train.jsonl'])
    item={'repo':'schneiderkamplab/test','files':{'data/train.jsonl':file_hash(payload)}}
    verify_remote(api,item,'pinned-commit')
    assert calls==[('schneiderkamplab/test','data/train.jsonl','pinned-commit')]
    item['files']['data/train.jsonl']='0'*64
    with pytest.raises(ValueError,match='digest differs'):verify_remote(api,item,'pinned-commit')


def test_extra_remote_file_is_not_overwritten_or_accepted():
    api=SimpleNamespace(list_repo_files=lambda *args,**kwargs:['data/train.jsonl','other.jsonl'])
    with pytest.raises(ValueError,match='inventory differs'):
        verify_remote(api,{'repo':'schneiderkamplab/test','files':{'data/train.jsonl':'a'}},'commit')
