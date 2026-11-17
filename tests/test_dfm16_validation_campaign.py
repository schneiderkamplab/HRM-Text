import asyncio
import pytest
from dfm12.io import load,write_json
from scripts.dfm16_story_calibration import immutable_rows
from scripts import dfm16_validation_source_review as source
from scripts import dfm16_validation_generate_batch as generation
from scripts import dfm16_validation_audit as audit
from dfm12.io import file_hash


def test_source_rejection_is_retained_without_generation(tmp_path,monkeypatch):
    monkeypatch.setattr(source,'verify_freeze',lambda *a:None)
    path=tmp_path/'en/validation/families.jsonl'
    immutable_rows(path,[dict(family='f',task='qa',text='A source.',provenance={})])
    source.record(tmp_path,'en',[dict(index=0,status='rejected',reason='Unintelligible referent.')])
    result=load(tmp_path/'en/validation/source-review/0000.json')
    assert result['family']=='f' and 'generation_input' not in result
    assert result['assessment']['reason']=='Unintelligible referent.'


def test_source_question_requires_exact_support(tmp_path,monkeypatch):
    monkeypatch.setattr(source,'verify_freeze',lambda *a:None)
    immutable_rows(tmp_path/'en/validation/families.jsonl',[
        dict(family='f',task='qa',text='Mia found a blue stone.',provenance={})])
    annotation=dict(index=0,status='clear',reason='Read.',question='What did Mia find?',
        reference_answer='A red stone.',answer_support='a red stone')
    with pytest.raises(ValueError,match='source-supported'):source.record(tmp_path,'en',[annotation])
    assert not (tmp_path/'en/validation/source-review/0000.json').exists()


def test_overlapping_batch_cannot_regenerate(tmp_path,monkeypatch):
    monkeypatch.setattr(generation,'verify_freeze',lambda *a:None)
    write_json(tmp_path/'protocol.json',dict(software={}))
    job=dict(id='en-0000')
    write_json(tmp_path/'en/validation/source-review/0000.json',dict(generation_input=job))
    immutable_rows(tmp_path/'en/validation/generation/earlier/inputs.jsonl',[job])
    with pytest.raises(ValueError,match='overlapping'):
        asyncio.run(generation.generate(tmp_path,'en',0,1))


def test_validation_audit_requires_all_blinded_labels(tmp_path):
    immutable_rows(tmp_path/'blind-packet.jsonl',[dict(id=str(i)) for i in range(800)])
    immutable_rows(tmp_path/'manual-labels.jsonl',[dict(id=str(i)) for i in range(799)])
    write_json(tmp_path/'label-receipt.json',dict(
        packet_sha256=file_hash(tmp_path/'blind-packet.jsonl'),
        labels_sha256=file_hash(tmp_path/'manual-labels.jsonl'),judge_votes_exposed=False))
    with pytest.raises(ValueError,match='800 blinded labels'):
        audit.require_sealed_labels(tmp_path)


def test_validation_audit_rejects_tampered_labels(tmp_path):
    immutable_rows(tmp_path/'blind-packet.jsonl',[dict(id=str(i)) for i in range(800)])
    immutable_rows(tmp_path/'manual-labels.jsonl',[dict(id=str(i)) for i in range(800)])
    write_json(tmp_path/'label-receipt.json',dict(
        packet_sha256=file_hash(tmp_path/'blind-packet.jsonl'),
        labels_sha256='changed',judge_votes_exposed=False))
    with pytest.raises(ValueError,match='sealed labeling evidence changed'):
        audit.require_sealed_labels(tmp_path)


def test_required_missing_verdict_prevents_admission():
    assert audit.whole_vote(['accept','accept'])=='accept'
    assert audit.whole_vote(['accept','reject'])=='reject'
    assert audit.whole_vote(['reject','unresolved'])=='unresolved'
    assert audit.whole_vote([])=='unresolved'


def test_revision_view_keeps_edit_and_selective_undo_visible():
    from scripts.dfm16_validation_review_view import compact
    messages=[dict(role='assistant',content='A\n\nB\n\nC'),
              dict(role='user',content='Change B'),
              dict(role='assistant',content='A\n\nB2\n\nC'),
              dict(role='assistant',content='A\n\nB2\n\nC2'),
              dict(role='assistant',content='A\n\nB\n\nC2')]
    view=compact(messages)
    assert view[0]==messages[0] and view[1]==messages[1]
    assert view[2]['changes']=={1:'B2'}
    assert view[3]['changes']=={2:'C2'}
    assert view[4]['changes']=={1:'B'} and view[4]['unchanged']==[0,2]


def test_report_retains_intake_failures_and_correction_lineage():
    from scripts.dfm16_validation_report import assemble
    packet=[dict(id='a',task='qa',status='source_rejected',stages={}),
            dict(id='b',task='revision',status='generated',stages={'edit':{'attempts':[{'findings':['length']},{}]}})]
    labels=[dict(id='a',first_label='unresolved',final_label='unresolved',note='Source invalid'),
            dict(id='b',first_label='bad',final_label='clear',note='Corrected length')]
    private=[dict(id='a',family='fa',index=0),dict(id='b',family='fb',index=1)]
    votes=[dict(id='a',votes={},decision='reject',deterministic_pass=False),
           dict(id='b',votes={},decision='accept',deterministic_pass=True)]
    result=assemble(packet,labels,private,votes)
    assert len(result)==2 and result[0]['label']=='unresolved'
    assert result[1]['corrected'] and result[1]['first_label']=='bad'
    packet[1]['stages']['edit']['attempts']=[{'error':'transport'},{}]
    assert not assemble(packet,labels,private,votes)[1]['corrected']
    with pytest.raises(ValueError,match='coverage mismatch'):
        assemble(packet,labels,private,votes[:1])
    votes[0]['deterministic_pass']=True
    with pytest.raises(ValueError,match='deterministic admission'):
        assemble(packet,labels,private,votes)


def test_report_usage_counts_every_response_once():
    from scripts.dfm16_validation_report import usage
    assert usage([{'response':{'usage':{'prompt_tokens':10,'completion_tokens':3}}},
                  {'error':'transport'}, {'response':{}}])==dict(
        attempts=3,responses=2,missing_usage=1,prompt_tokens=10,completion_tokens=3)


def test_report_does_not_charge_code_assembled_undo():
    from scripts.dfm16_validation_report import generation_attempts_from
    attempt={'response':{'usage':{'completion_tokens':10}}}
    assert generation_attempts_from({'stages':{
        'story':{'attempts':[attempt]}, 'undo':{'status':'complete','text':'restored'}}})==[attempt]
