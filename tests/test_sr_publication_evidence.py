from pathlib import Path
import shutil
import sqlite3
from types import SimpleNamespace

import pytest

from dfm12 import sr_publication_evidence as s
from dfm12.io import file_hash, load, write_json


def setup(tmp_path,monkeypatch):
    root=tmp_path/'wave4'; ledger=root/'release/wikipedia-sr'
    write_json(ledger/'status.json',{'terminal':True,'export_ready':True,'counts':{'excluded_manual_review':4}})
    sqlite3.connect(ledger/'ledger.sqlite').close()
    canonical=tmp_path/'export';(canonical/'data').mkdir(parents=True)
    data=canonical/'data/train.jsonl';data.write_text('unchanged-data\n')
    (canonical/'README.md').write_text('Original attribution and license\n')
    pub=dict(name='dfm13_wave4_wikipedia_sr_denoising',uploaded=True,hf_repo_id='test/repo',
        hf_revision='old',output=str(data),output_sha256=file_hash(data),rows=1)
    write_json(canonical/'manifest.json',pub);write_json(ledger/'denoising/publication.json',pub)
    registry=tmp_path/'registry.json'
    write_json(registry,{'additions':[dict(pub,tokenized_path='old-token-root',tokenization_performed=True,tokenized_tokens=123)]})
    monkeypatch.setattr(s,'ROOT',root);monkeypatch.setattr(s,'REGISTRY',registry)
    monkeypatch.setattr(s,'TASKS',('denoising',))
    def evidence(db,folder):
        path=Path(folder)/'manual-review-decisions.json';write_json(path,{'decisions':[1,2,3,4]})
        return {file_hash(path):path.name}
    monkeypatch.setattr(s,'publication_evidence',evidence)
    remote=tmp_path/'remote';remote.mkdir()
    class API:
        sha='old'
        calls=0
        def repo_info(self,*args,**kwargs): return SimpleNamespace(sha=self.sha)
        def upload_folder(self,**kwargs):
            assert kwargs['parent_commit']=='old'
            assert set(kwargs['allow_patterns'])=={'README.md','manifest.json','manual-review-decisions.json'}
            assert 'data/train.jsonl' not in kwargs['allow_patterns']
            for name in kwargs['allow_patterns']: shutil.copyfile(Path(kwargs['folder_path'])/name,remote/name)
            self.calls+=1;self.sha='new';return SimpleNamespace(oid='new')
    api=API()
    def download(repo,name,**kwargs):
        assert kwargs['revision']=='new'
        return data if name=='data/train.jsonl' else remote/name
    return tmp_path/'backfill',api,download,registry,canonical,ledger


def test_metadata_only_verified_idempotent_preserves_tokens(tmp_path,monkeypatch):
    output,api,download,registry,canonical,ledger=setup(tmp_path,monkeypatch)
    before=file_hash(canonical/'data/train.jsonl')
    s.backfill(output,api,download);s.backfill(output,api,download)
    assert api.calls==1 and file_hash(canonical/'data/train.jsonl')==before
    entry=load(registry)['additions'][0]
    assert entry['hf_revision']=='new' and entry['tokenized_path']=='old-token-root' and entry['tokenized_tokens']==123
    assert len(load(output/'denoising/verified.json')['remote_verified_files'])==4
    assert load(output/'denoising/parent-publication.json')['hf_revision']=='old'


def test_remote_parent_conflict_does_not_modify_canonical(tmp_path,monkeypatch):
    output,api,download,registry,canonical,ledger=setup(tmp_path,monkeypatch)
    api.sha='someone-else'
    with pytest.raises(ValueError,match='Remote parent changed'): s.backfill(output,api,download)
    assert load(registry)['additions'][0]['hf_revision']=='old'
    assert not (canonical/'manual-review-decisions.json').exists()


def test_remote_bad_hash_no_registry_promotion(tmp_path,monkeypatch):
    output,api,download,registry,canonical,ledger=setup(tmp_path,monkeypatch)
    bad=tmp_path/'bad';bad.write_text('bad')
    with pytest.raises(ValueError,match='hash mismatch'): s.backfill(output,api,lambda *a,**k:bad)
    assert load(registry)['additions'][0]['hf_revision']=='old'
    assert load(ledger/'denoising/publication.json')['hf_revision']=='old'
