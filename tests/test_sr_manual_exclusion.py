import json
import sqlite3

import pytest

from dfm12 import sr_manual_exclusion as sr
from dfm12.io import load, write_json, lock


@pytest.fixture
def setup(tmp_path):
    root = tmp_path/'wave4'; folder = root/'release/wikipedia-sr'
    folder.mkdir(parents=True)
    evidence = load(sr.REVIEW/'evidence.json')
    with sqlite3.connect(folder/'ledger.sqlite') as db:
        db.execute('CREATE TABLE rows (id TEXT PRIMARY KEY,record TEXT,status TEXT,review TEXT)')
        for row in evidence:
            db.execute('INSERT INTO rows VALUES (?,?,?,?)', (row['id'],json.dumps(row['record']),
                'accepted',json.dumps(row['acceptance_review'])))
    write_json(root/'audit-ready/wikipedia-sr/receipt.json',{'sha256':'seal','counts':{'ready':17}})
    write_json(folder/'status.json',{'input_sha256':'seal','counts':{'accepted':16},'export_ready':False})
    registry=tmp_path/'registry.json';write_json(registry,{'additions':[]})
    return root,tmp_path/'exports',registry


def test_four_only_case45_retained_originals_unchanged(setup):
    path=setup[0]/'release/wikipedia-sr/ledger.sqlite'
    with sqlite3.connect(path) as db:
        before=db.execute('SELECT id,record,review FROM rows ORDER BY id').fetchall()
    first=sr.apply(*setup); assert first==sr.apply(*setup)
    assert first['wikipedia-sr']['counts']=={'accepted':12,'excluded_manual_review':4}
    assert not first['wikipedia-sr']['export_ready']
    with sqlite3.connect(path) as db:
        assert before==db.execute('SELECT id,record,review FROM rows ORDER BY id').fetchall()
        assert db.execute('SELECT status FROM rows WHERE id=?',(sr.RETAINED_CASE45,)).fetchone()==('accepted',)
        assert {r[0] for r in db.execute('SELECT id FROM manual_review_decisions')}==set(sr.CASES.values())
        for raw, in db.execute('SELECT decision FROM manual_review_decisions'):
            event=json.loads(raw)
            assert 'Main-agent' in event['authority']
            assert 'Explicit user authorization' not in event['authority']
            assert event['prior_status']=='accepted'
            assert json.loads(event['original_model_review'])['keep']
        with pytest.raises(sqlite3.IntegrityError): db.execute('DELETE FROM manual_review_decisions')


@pytest.mark.parametrize('kind',['publication','export','lock'])
def test_publication_race_fails_closed(setup,kind):
    folder=setup[0]/'release/wikipedia-sr'
    if kind=='publication': write_json(folder/'denoising/publication.json',{})
    elif kind=='export': (setup[1]/'dfm13-wave4-wikipedia-sr-denoising').mkdir(parents=True)
    if kind=='lock':
        with lock(folder/'.lock'):
            with pytest.raises(BlockingIOError): sr.apply(*setup)
    else:
        with pytest.raises(ValueError): sr.apply(*setup)
    with sqlite3.connect(folder/'ledger.sqlite') as db:
        assert db.execute('SELECT DISTINCT status FROM rows').fetchall()==[('accepted',)]


def test_sr_review_pins_unchanged():
    assert {d['id'] for d in sr.reviewed_decisions()}==set(sr.CASES.values())
    assert sr.RETAINED_CASE45 not in sr.CASES.values()


def test_publication_evidence_binds_four_and_retained_case(setup):
    sr.apply(*setup)
    with sqlite3.connect(setup[0]/'release/wikipedia-sr/ledger.sqlite') as db:
        files=sr.publication_evidence(db,setup[0]/'evidence')
        assert len(files)==1
        payload=load(setup[0]/'evidence/manual-review-decisions.json')
        assert len(payload['decisions'])==4 and payload['retained_case45']==sr.RETAINED_CASE45
        db.execute("UPDATE rows SET status='rejected' WHERE id=?",(sr.RETAINED_CASE45,))
        with pytest.raises(ValueError,match='Case45'):
            sr.publication_evidence(db,setup[0]/'bad-evidence')


def test_real_release_excludes_only_manual_four_and_carries_evidence(setup,monkeypatch):
    from dfm12.wave_release import release
    from dfm12.io import file_hash
    sr.apply(*setup)
    root=setup[0]; folder=root/'release/wikipedia-sr'
    candidate=root/'audit-ready/wikipedia-sr/candidates.jsonl'
    candidate.write_text('test sealed input\n')
    write_json(candidate.parent/'receipt.json',{'path':str(candidate)})
    state=load(folder/'status.json');state.update(export_ready=True,input_sha256=file_hash(candidate))
    write_json(folder/'status.json',state)
    download=root/'downloads/wikipedia-sr'
    write_json(download/'wave4-download.json',{'repo':'wikimedia/wikipedia','revision':'b04c8d1ceb2f5cd4588862100d08de323dccfbaa'})
    (download/'README.md').write_text('---\nlicense:\n- cc-by-sa-3.0\n- gfdl\n---\n')
    monkeypatch.setattr(sr,'REVIEW',sr.REVIEW.resolve())
    monkeypatch.chdir(root.parent)
    ids=set()
    for task in ('denoising','paragraph-reordering','prefix-continuation','span-filling'):
        release(root,'wikipedia-sr',task=task)
        publication=load(folder/task/'publication.json')
        assert publication['attribution_files']
        for line in open(publication['output']): ids.add(json.loads(line)['id'])
    assert len(ids)==12 and not ids.intersection(sr.CASES.values())
    assert sr.RETAINED_CASE45 in ids
