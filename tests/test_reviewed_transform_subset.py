import copy
import io
import json

import pytest

from dfm12 import reviewed_transform_subset as s
from dfm12.io import load


def exported():
    e = next(x for x in load(s.manual.REVIEW/'evidence.json') if x['case'] == 1)
    row = copy.deepcopy(e['record'])
    row['provenance'].update(license=['cc-by-sa-3.0','gfdl'], license_card_sha256='card')
    row.update(admission_authorized=True, target_message_index=1, quality_status='accepted', audit=e['acceptance_review'])
    return e, row


def test_preadmission_to_attributed_export():
    evidence, row = exported()
    s.verify_excluded(row, evidence)


@pytest.mark.parametrize('field', ['messages','provenance','audit','extra','status'])
def test_mapping_rejects_content_or_audit_change(field):
    evidence, row = exported()
    if field == 'messages': row['messages'][-1]['content'] += ' changed'
    elif field == 'provenance': row['provenance']['row'] += 1
    elif field == 'audit': row['audit'] = dict(row['audit'], reason='new')
    elif field == 'status': row['quality_status'] = 'accepted_repair'
    else: row['new_field'] = True
    with pytest.raises(ValueError): s.verify_excluded(row, evidence)


def fixture(monkeypatch, tmp_path):
    _, bad = exported()
    good = copy.deepcopy(bad); good['id'] = 'unaffected'
    rows = [(json.dumps(x, ensure_ascii=False)+'\n').encode() for x in (good,bad)]
    source = tmp_path/'source.jsonl'; source.write_bytes(b''.join(rows))
    monkeypatch.setitem(s.PARENTS, ('sl','prefix-continuation'), (2,'rev','sha',1))
    return source, rows


def test_exact_subset_and_receipt(monkeypatch,tmp_path):
    source, lines = fixture(monkeypatch,tmp_path)
    keep, removed = io.BytesIO(),io.BytesIO()
    n,_ = s.replay(source,'sl','prefix-continuation',keep,removed)
    assert n == 1 and keep.getvalue() == lines[0]
    event = json.loads(removed.getvalue())
    assert event['status'] == 'excluded_manual_review' and event['prior_status'] == 'accepted'
    assert event['original_model_review']['keep'] is True
    assert event['record_sha256'] != event['published_record_sha256']
    keep.seek(0);removed.seek(0)
    s.replay(source,'sl','prefix-continuation',keep,removed,True)


@pytest.mark.parametrize('failure',['duplicate','missing','extra_output','mutated'])
def test_replay_fail_closed(monkeypatch,tmp_path,failure):
    source, lines = fixture(monkeypatch,tmp_path)
    if failure == 'duplicate': source.write_bytes(lines[0]+lines[0]+lines[1])
    elif failure == 'missing': source.write_bytes(lines[0])
    elif failure == 'mutated':
        row=json.loads(lines[1]); row['rendered_tokens'] += 1
        source.write_bytes(lines[0]+(json.dumps(row)+'\n').encode())
    with pytest.raises(ValueError):
        if failure == 'extra_output':
            keep,excluded=io.BytesIO(),io.BytesIO()
            s.replay(source,'sl','prefix-continuation',keep,excluded)
            s.replay(source,'sl','prefix-continuation',io.BytesIO(keep.getvalue()+b'bad'),io.BytesIO(excluded.getvalue()),True)
        else: s.replay(source,'sl','prefix-continuation',io.BytesIO(),io.BytesIO())


@pytest.mark.parametrize('language',['sl','sq'])
@pytest.mark.parametrize('task',['prefix-continuation','paragraph-reordering'])
def test_old_finalizer_refuses_exact_tasks(tmp_path,language,task):
    from dfm12.wave_release import release
    with pytest.raises(ValueError,match='Exact reviewed-ID'):
        release(tmp_path,'wikipedia-'+language,True,task)


def test_unaffected_task_not_blocked(tmp_path):
    from dfm12.wave_release import release
    with pytest.raises(FileNotFoundError): release(tmp_path,'wikipedia-sl',False,'denoising')


def test_clear_only_own_hold():
    with pytest.raises(ValueError): s.prepare_entry({'quality_hold': {'scope':'other'}})
    assert s.prepare_entry({'quality_hold': {'scope':'exact_reviewed_id_successor_pending'}}) == {}
