import os
from pathlib import Path
import pytest
from dfm12.io import file_hash, load, write_json
from scripts import finish_dfm13_ready150_cards as mod


def fixture_queue(tmp_path, monkeypatch, verified=False):
    monkeypatch.chdir(tmp_path)
    old=Path('data/dfm13/upload-ready150-20261004-v1');old.mkdir(parents=True)
    card=tmp_path/'source-README.md'
    card.write_text('---\nlanguage: [be, pt_pt]\n---\nOriginal body.\n')
    payload=tmp_path/'source-data.jsonl';payload.write_text('unchanged accepted payload\n')
    packages=[];receipts={}
    for i in range(150):
        folder=old/'packages'/str(i);(folder/'data').mkdir(parents=True)
        if i==0:os.link(card,folder/'README.md')
        else:(folder/'README.md').write_text('---\nlanguage: [be, en]\n---\nOriginal body.\n')
        os.link(payload,folder/'data/train.jsonl')
        repo='schneiderkamplab/test-'+str(i)
        files={name:file_hash(folder/name) for name in ('README.md','data/train.jsonl')}
        packages.append(dict(repo=repo,folder=str(folder.resolve()),files=files))
        receipts[repo]={'status':'verified' if i or verified else 'blocked','files':files}
    write_json(old/'queue.json',dict(packages=packages))
    write_json(old/'seal.json',dict(sha256=file_hash(old/'queue.json')))
    write_json(old/'publication-receipts.json',receipts)
    write_json(old/'completion.json',dict(complete=False))
    monkeypatch.setattr(mod,'publish',lambda root:None)
    return card,payload,old


def test_atomic_card_fix_retains_source_payload_and_exact_scope(tmp_path,monkeypatch):
    card,payload,old=fixture_queue(tmp_path,monkeypatch)
    original=card.read_bytes();payload_sha=file_hash(payload);old_queue_sha=file_hash(old/'queue.json')
    mod.main()
    new=Path('data/dfm13/upload-ready150-20261004-v2')
    queue=load(new/'queue.json');old_queue=load(old/'queue.json')
    assert len(queue['packages'])==150
    assert [x['repo'] for x in queue['packages']]==[x['repo'] for x in old_queue['packages']]
    assert card.read_bytes()==original
    assert (old/'packages/0/README.md').read_bytes()==original
    assert file_hash(old/'queue.json')==old_queue_sha
    corrected=new/'packages/0/README.md'
    assert corrected.stat().st_ino!=card.stat().st_ino
    assert 'European Portuguese (pt-PT)' in corrected.read_text()
    assert 'pt_pt' not in corrected.read_text()
    assert all(x['files']['data/train.jsonl']==payload_sha for x in queue['packages'])
    receipts=load(new/'publication-receipts.json')
    assert len(receipts)==149
    assert all(x['status']=='verified' for x in receipts.values())


def test_already_verified_card_cannot_be_republished(tmp_path,monkeypatch):
    card,payload,old=fixture_queue(tmp_path,monkeypatch,verified=True)
    before=card.read_bytes()
    with pytest.raises(ValueError,match='already verified'):
        mod.main()
    assert card.read_bytes()==before
    assert not Path('data/dfm13/upload-ready150-20261004-v2/queue.json').exists()
