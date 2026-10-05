from collections import Counter
import io
import json
from pathlib import Path
import stat
import zipfile
import pytest
from dfm12 import wave4_persian_local as p


@pytest.mark.parametrize('name',['../escape.jsonl','/root.jsonl','a/../../b','a\\b','C:/data'])
def test_paths(name):
    with pytest.raises(ValueError,match='unsafe'):
        p.safe_name(name)


def test_zip_stream(tmp_path):
    path=tmp_path/'fixture.zip'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('data/rows.jsonl',json.dumps({'text':'test-only fixture'})+'\n')
        z.writestr('never-execute.pkl',b'not executed')
    counts=Counter();rows=list(p.local_rows(path,counts))
    assert rows==[('data/rows.jsonl',0,{'text':'test-only fixture'})]
    assert counts['unsupported_archive_member']==1


def test_zip_symlink(tmp_path):
    path=tmp_path/'fixture.zip';info=zipfile.ZipInfo('link')
    info.external_attr=(stat.S_IFLNK|0o777)<<16
    with zipfile.ZipFile(path,'w') as z:z.writestr(info,'outside')
    with pytest.raises(ValueError,match='symlink'):
        list(p.local_rows(path,Counter()))


def test_oversize_and_corrupt(tmp_path,monkeypatch):
    path=tmp_path/'fixture.zip'
    with zipfile.ZipFile(path,'w') as z:z.writestr('a.jsonl','x'*50)
    monkeypatch.setattr(p,'MAX_MEMBER',10)
    with pytest.raises(ValueError,match='member_limit'):
        list(p.local_rows(path,Counter()))
    path.write_bytes(b'corrupt zip')
    with pytest.raises(zipfile.BadZipFile):list(p.local_rows(path,Counter()))
    with pytest.raises(ValueError,match='limit'):
        list(p.json_lines(io.BytesIO(b'x'*20),Counter(),byte_limit=10))


def test_schema_and_boundaries():
    text,meta=p.document({'category':{'textType':'Formal'},'content':[{'text':'first','type':'paragraph'},{'text':'second','type':'heading'}], 'comments':[{'text':'not prose'}]},'tlpc')
    assert text=='first\n\nsecond'
    assert meta['content_types']==['paragraph','heading']
    with pytest.raises(ValueError):p.document({'content':'guess me'},'matina')
    with pytest.raises(ValueError):p.document({'category':{'textType':'Unknown'},'content':[]},'tlpc')


def test_allocation_deterministic_and_broad():
    files=[{'path':f'{site}/{month}.jsonl.gz','bytes':5} for site in ['a','b','c'] for month in range(3)]
    one,stats=p.allocate(files,'tlpc',max_shards=3,max_bytes=15,max_shard_bytes=10)
    two,_=p.allocate(list(reversed(files)),'tlpc',max_shards=3,max_bytes=15,max_shard_bytes=10)
    assert one==two and stats['selected_bytes']==15 and stats['selected_strata']==3


def test_missing_blocks_without_renderer_or_network(tmp_path,monkeypatch):
    plan={'implementation_sha256':p.file_hash(Path(p.__file__)), 'sources':{'matina':{'files':[{'path':'missing.zip'}],'local_root':str(tmp_path/'absent')}}}
    p.write_json(tmp_path/'plan.json',plan)
    p.write_json(tmp_path/'seal.json',{'sha256':p.file_hash(tmp_path/'plan.json')})
    p.prepare(tmp_path,'matina')
    assert p.load(tmp_path/'matina/status.json')['network_requests']==0
    assert not (tmp_path/'matina/candidates.jsonl').exists()
