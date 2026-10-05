import io
import json

import pytest

from dfm12 import hr_transform_subset as hr
from dfm12.io import digest, load, write_json


def fixture(monkeypatch, tmp_path):
    rows = [dict(id=str(i), language='hr', task='paragraph-reordering',
        messages=[dict(role='user',content='q'),dict(role='assistant',content='a')],
        target_message_index=1, admission_authorized=True, rendered_tokens=10) for i in range(3)]
    lines = [(json.dumps(row)+'\n').encode() for row in rows]
    source = tmp_path/'source.jsonl'
    source.write_bytes(b''.join(lines))
    review = {'1':dict(record_sha256=digest(rows[1]), window_sha256='window', note='manually read')}
    monkeypatch.setattr(hr, 'reviewed', lambda: review)
    monkeypatch.setattr(hr, 'COUNTS', {'paragraph-reordering': (3,1)})
    return source, lines, review


def test_exact_id_only_bytes_and_order(monkeypatch, tmp_path):
    source, lines, _ = fixture(monkeypatch, tmp_path)
    keep, excluded = io.BytesIO(), io.BytesIO()
    assert hr.replay(source,keep,excluded) == (2,20)
    assert keep.getvalue() == lines[0]+lines[2]
    assert json.loads(excluded.getvalue())['id'] == '1'
    keep.seek(0); excluded.seek(0)
    assert hr.replay(source,keep,excluded,checking=True) == (2,20)


@pytest.mark.parametrize('failure', ['hash','missing','duplicate','task','target','extra_output'])
def test_fail_closed_exact_coverage(monkeypatch,tmp_path,failure):
    source,lines,review = fixture(monkeypatch,tmp_path)
    if failure=='hash': review['1']['record_sha256']='bad'
    if failure=='missing': review['absent']=review.pop('1')
    if failure=='duplicate': source.write_bytes(lines[0]+lines[0]+lines[2])
    if failure in ('task','target'):
        row=json.loads(lines[0])
        row['task' if failure=='task' else 'target_message_index']='wrong'
        source.write_bytes((json.dumps(row)+'\n').encode()+lines[1]+lines[2])
    with pytest.raises(ValueError):
        if failure=='extra_output':
            kept,excluded=io.BytesIO(),io.BytesIO()
            hr.replay(source,kept,excluded)
            hr.replay(source,io.BytesIO(kept.getvalue()+b'extra'),
                      io.BytesIO(excluded.getvalue()),checking=True)
        else:
            hr.replay(source,io.BytesIO(),io.BytesIO())


def test_only_reordering_registry_promoted(monkeypatch,tmp_path):
    with pytest.raises(ValueError,match='Only HR'):
        hr.promote_registry(tmp_path,[{'name':'dfm13_wave4_wikipedia_hr_denoising'}])


def test_shared_tokenization_scoped(monkeypatch,tmp_path):
    def tokenizer(folder, *, verifier, token_root):
        assert verifier is hr.verify_package
        assert token_root == hr.TOKEN_ROOT
        assert 'tokenized_wave_releases' not in str(token_root)
        return {'ok':True}
    monkeypatch.setattr(hr.shared,'tokenize',tokenizer)
    assert hr.tokenize(tmp_path) == {'ok':True}


def test_old_finalizer_guard_is_task_specific(tmp_path):
    from dfm12.wave_release import release
    with pytest.raises(ValueError,match='Croatian reordering publication superseded'):
        release(tmp_path,'wikipedia-hr',True,'paragraph-reordering')
    # Other tasks pass the new guard and reach normal missing-ledger validation.
    with pytest.raises(FileNotFoundError):
        release(tmp_path,'wikipedia-hr',False,'denoising')


def test_frozen_proposal_pins():
    evidence=hr.reviewed()
    assert len(evidence)==44
