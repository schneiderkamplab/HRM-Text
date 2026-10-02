import copy
import json
from types import SimpleNamespace

import pytest

from dfm12 import export_multilingual_completed as e
from dfm12.io import digest,write_json


def candidate():
    return dict(id='old',language='de',family='tool-dialogue',provenance={},tools=[{'type':'function','function':{'name':'find','parameters':{'type':'object','properties':{'n':{'type':'integer'}}}}}],
        messages=[{'role':'user','content':'Find item 3'},
                  {'role':'assistant','content':'','tool_calls':[{'id':'call_1','type':'function','function':{'name':'find','arguments':{'n':3}}}]},
                  {'role':'tool','content':'{"found":true}','tool_call_id':'call_1'},
                  {'role':'assistant','content':'Found.'}])


def test_native_tool_structures_are_copied_without_loss():
    original=candidate();fp=digest({k:original[k] for k in ('messages','tools')})
    exported=e.training_record(original,'campaign',fp)
    assert exported['messages']==original['messages'] and exported['tools']==original['tools']
    assert exported['messages'][1]['tool_calls'][0]['function']['arguments']=={'n':3}
    assert exported['messages'][2]['tool_call_id']=='call_1'
    exported['messages'][1]['tool_calls'][0]['function']['arguments']['n']=99
    assert original['messages'][1]['tool_calls'][0]['function']['arguments']['n']==3


def test_fingerprint_tampering_fails():
    with pytest.raises(ValueError,match='fingerprint'):e.training_record(candidate(),'campaign','wrong')


def test_fixed_thirteen_language_scope():
    assert len(e.LANGUAGES)==13
    assert sum(70000 if l in ('nb','nn') else 35000 for l in e.LANGUAGES)==525000
    assert not {'ca','cs','et','fo','is','pt_pt'} & set(e.LANGUAGES)


def test_explicit_final_cohort():
    assert e.cohort(e.FINAL_LANGUAGES)[1]==350000
    assert e.cohort(e.ALL_LANGUAGES)[1]==875000
    assert e.cohort(e.LANGUAGES)[1]==525000
    assert e.language_target('pt_pt')==35000
    for bad in [[],['ca','ca'],['xx']]:
        with pytest.raises(ValueError):e.cohort(bad)


def fixture(tmp_path,origin='production'):
    row=candidate();spec=dict(language_code='de',family='tool-dialogue',slot=1)
    row['provenance']=spec.copy();fp=digest({k:row[k] for k in ('messages','tools')});key='job'
    outcome=dict(id=key,terminal=True,status='valid',effective_keep=True,fingerprint=fp,spec_sha256=digest(spec))
    payload={'record':row,'temperature':0,'frequency_penalty':.5};schema={'type':'object','properties':{'keep':{'const':True}},'required':['keep']}
    request=dict(request=payload,schema=schema)
    state=dict(status='complete',raw={'finish_reason':'stop','content':'{"keep":true}'},output={'keep':True},request_sha256=digest(payload))
    for folder,value in [('outcomes',outcome),('candidates',row)]:write_json(tmp_path/folder/f'{key}.json',value)
    write_json(tmp_path/'stages'/f'{key}-generate.json',state)
    write_json(tmp_path/'stages'/f'{key}-review.json',state)
    write_json(tmp_path/'requests'/f'{key}-review.json',request)
    if origin!='pilot':write_json(tmp_path/'accepted'/f'{key}.json',dict(row,id=e.quarter.candidate_id('campaign',fp)))
    job=dict(id=key,status='accepted',language='de',family='tool-dialogue',slot=1,origin=origin,
             workdir=str(tmp_path),fingerprint=fp,outcome_json=json.dumps(outcome),spec_json=json.dumps(spec))
    v6=SimpleNamespace(strict_json=json.loads,audit_record=lambda c:c,
        generation_assemble=lambda *args:copy.deepcopy(row),
        review_request=lambda record,review:{'record':record},compact_request=lambda payload:(payload,schema),
        review_result=lambda *args:dict(effective_keep=True,deterministic_checks=[]))
    return job,{'manifest':{'campaign':'campaign'}},SimpleNamespace(v6=v6)


@pytest.mark.parametrize('origin',['production','pilot'])
def test_production_and_unmaterialized_pilot(tmp_path,origin):
    job,source,controller=fixture(tmp_path,origin)
    row,receipt=e.validate_job(job,source,None,controller,(None,None))
    assert row['family']=='tool-dialogue' and receipt['origin']==origin


def test_materialized_drift_fails(tmp_path):
    job,source,controller=fixture(tmp_path)
    write_json(tmp_path/'accepted'/'job.json',{})
    with pytest.raises(ValueError,match='Materialized'):e.validate_job(job,source,None,controller,(None,None))


def test_incomplete_raw_audit_fails(tmp_path):
    job,source,controller=fixture(tmp_path)
    path=tmp_path/'stages'/'job-review.json';state=json.loads(path.read_text());state['raw']['finish_reason']='length';write_json(path,state)
    with pytest.raises(ValueError,match='Incomplete independent'):e.validate_job(job,source,None,controller,(None,None))


@pytest.mark.parametrize('origin',['production','pilot'])
def test_generation_reconstruction_drift_fails(tmp_path,origin):
    job,source,controller=fixture(tmp_path,origin)
    controller.v6.generation_assemble=lambda *args: {}
    with pytest.raises(ValueError,match='Generation assembly'):e.validate_job(job,source,None,controller,(None,None))


def test_snapshot_verified_and_drift_rejected(tmp_path):
    from dfm12.io import file_hash
    path=tmp_path/'private/accepted.sqlite';path.parent.mkdir();path.write_bytes(b'fixture')
    write_json(tmp_path/'private/sources.json',{'original':{}})
    write_json(tmp_path/'snapshot.json',dict(rows=525000,languages=e.LANGUAGES,
        sources={'original':{}},sqlite_sha256=file_hash(path)))
    e.verify_snapshot(tmp_path)
    path.write_bytes(b'drift')
    with pytest.raises(ValueError,match='database hash'):e.verify_snapshot(tmp_path)
    write_json(tmp_path/'private/sources.json',{})
    with pytest.raises(ValueError,match='sources mismatch'):e.verify_snapshot(tmp_path)


def test_archive_preserves_snapshot_and_partial_outputs(tmp_path):
    folder=tmp_path/'dfm12-multilingual-synthetic-de';folder.mkdir();(folder/'partial').write_text('old')
    (tmp_path/'private').mkdir();(tmp_path/'private/accepted.sqlite').write_bytes(b'unchanged')
    e.archive_partial(tmp_path)
    assert not folder.exists()
    assert list((tmp_path/'interrupted').glob('*/dfm12-multilingual-synthetic-de/partial'))
    assert (tmp_path/'private/accepted.sqlite').read_bytes()==b'unchanged'
