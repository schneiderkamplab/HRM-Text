import json

import pytest

from dfm12 import export_identity_multilingual as e
from dfm12.io import digest,file_hash,write_json


def row():
    return dict(id='one',messages=[dict(role='user',content='Who are you?'),dict(role='assistant',content='Mimir.')],
                language='da',task='identity',direction='native',parent_pair_id=None)


def test_counts_schema_language_and_duplicates():
    e.validate_records([row()],'da',1)
    for records,lang,count in [([row()],'da',2),([row()],'en',1),([row(),row()],'da',2),
                              ([dict(row(),provenance='not training')],'da',1)]:
        with pytest.raises(ValueError):e.validate_records(records,lang,count)


def package(tmp_path,kind='corrected_v4_local_curated'):
    (tmp_path/'metadata').mkdir();(tmp_path/'data').mkdir()
    r=row();e.write_rows(tmp_path/'data/train-00000.jsonl.gz',[r])
    e.write_rows(tmp_path/'metadata/provenance.jsonl.gz',[dict(id=r['id'],training_row_sha256=digest(r),kind=kind)])
    write_json(tmp_path/'metadata/manifest.json',dict(language='da',rows=1,files={
        'data/train-00000.jsonl.gz':file_hash(tmp_path/'data/train-00000.jsonl.gz'),
        'metadata/provenance.jsonl.gz':file_hash(tmp_path/'metadata/provenance.jsonl.gz')}))


def test_curated_not_fabricated_teacher_audit(tmp_path):
    package(tmp_path)
    assert e.validate(tmp_path)['kinds']=={'corrected_v4_local_curated':1}


def test_unknown_admission_rejected(tmp_path):
    package(tmp_path,'unaudited_generation')
    with pytest.raises(ValueError,match='Unknown'):e.validate(tmp_path)


def test_hash_drift_rejected(tmp_path):
    package(tmp_path)
    (tmp_path/'data/train-00000.jsonl.gz').write_bytes(b'changed')
    with pytest.raises(ValueError,match='hash'):e.validate(tmp_path)


def test_remote_license_preserved(tmp_path):
    package(tmp_path)
    (tmp_path/'README.md').write_text('---\nlanguage:\n- da\n---\nNew card')
    e.preserve_license(tmp_path,'---\nlicense: cc-by-4.0\nlicense_link: https://example.test/license\n---\nOld card')
    assert 'license: cc-by-4.0' in (tmp_path/'README.md').read_text()
    assert 'New card' in (tmp_path/'README.md').read_text()
    assert e.validate(tmp_path)['rows']==1


def test_new_audit_receipt_reconstructed():
    recipe=e.queue.recipe();payload=e.queue.request('da',100000,recipe)
    generation={'messages':row()['messages']}
    candidate=dict(payload['record'],messages=generation['messages'],component='identity-xl-full-bp',rendered_tokens=12)
    audit=dict(keep=True,reason='fixture',language_quality=5,coherence=5,usefulness=5)
    job=dict(id=payload['record']['id'],language='da',slot=100000,state='accepted',payload=json.dumps(payload),
             candidate=json.dumps(candidate),generation_result=json.dumps(generation),audit_result=json.dumps(audit),
             audit_payload=json.dumps(e.audit_payload(candidate,e.queue.MODEL)))
    assert e.accepted_record(job,recipe,job['id'])[0]==candidate
    with pytest.raises(ValueError):e.accepted_record(job,recipe,'other')
    audit['keep']=False;job['audit_result']=json.dumps(audit)
    with pytest.raises(ValueError):e.accepted_record(job,recipe,job['id'])
