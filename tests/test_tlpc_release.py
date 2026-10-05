from dfm12.tlpc_release import units
from dfm12.records import chat_fingerprint
from dfm12.scandi_overlap import text_hash


def test_overlap_uses_source_free_questions_and_full_source():
    text='long source '*30
    row=dict(messages=[dict(role='user',content='SOURCE\n\nپرسش:\nquestion'),
        dict(role='assistant',content='answer')],source=dict(text=text,elements=[{'text':text}]))
    chats,texts=units(row)
    assert chat_fingerprint([{'role':'user','content':'question'},{'role':'assistant','content':'answer'}]) in chats
    assert text_hash(text) in texts


def test_scoped_assembly_is_fail_closed():
    from dfm12.tlpc_assembly import unready
    from scripts.assemble_dfm13_additions import unready_reason
    row=dict(name='dfm13_tlpc_grounded_qa_fa',publication_contract='tlpc-grounded-audited-v1',repeat=1)
    assert unready_reason(row)=='tlpc_publication_not_verified'
    row.update(uploaded=True,status='accepted_uploaded',publication_status='verified',hf_revision='abc')
    assert unready(row)=='tlpc_tokenization_not_complete'
    row['tokenization_performed']=True
    assert unready(row) is None
    row['name']='foreign_source'
    assert unready(row)=='unsupported_tlpc_source'


def test_publication_needs_explicit_scoped_authority(tmp_path):
    import pytest
    from dfm12.io import write_json
    from dfm12.tlpc_publish import publish
    write_json(tmp_path/'packages.json',{'packages':[]})
    write_json(tmp_path/'authorization.json',{'upload_and_register':True})
    with pytest.raises(ValueError,match='scoped-coverage'):
        publish(tmp_path,tmp_path/'authorization.json')
