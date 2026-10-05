import json
from pathlib import Path
import pytest
from dfm12 import wave4_finished_release as release
from dfm12.io import digest,file_hash,write_json


def test_private_w4_validation_does_not_mutate_baltic():
    from dfm12.baltic_finished_release import validate
    from dfm12.wave4_synthetic_specs import audit_record
    assert release.validate_original.__globals__ is not validate.__globals__
    assert release.validate_original.__globals__['audit_record'] is audit_record
    assert validate.__globals__['audit_record'] is not audit_record


def test_supplement_full_conversation_and_tools_preserved(tmp_path):
    row=dict(language='lb',family='tool-dialogue',messages=[dict(role='user',content='q'),
        dict(role='assistant',tool_calls=[dict(id='call',type='function',function=dict(name='lookup',arguments='{}'))]),
        dict(role='tool',tool_call_id='call',content='result'),dict(role='assistant',content='answer')],tools=[{'type':'function'}],provenance={'source':{'id':'original'}})
    fp=digest({k:row[k] for k in ('messages','tools')})
    write_json(tmp_path/'accepted/j.json',row);write_json(tmp_path/'receipts/j.json',dict(fingerprint=fp))
    args=(tmp_path,'j',fp,file_hash(tmp_path/'receipts/j.json'),file_hash(tmp_path/'accepted/j.json'))
    result=release.recovered_row(args)
    assert result[2]==row and result[-1]=='technical_recovery'
    write_json(tmp_path/'accepted/j.json',dict(row,messages=[]))
    with pytest.raises(ValueError,match='drift'):release.recovered_row(args)


def test_card_no_false_upload_or_human_claim(tmp_path):
    release.card(tmp_path,'name','lb','math-code',2,3,{}, {})
    text=(tmp_path/'README.md').read_text()
    assert 'HF upload is pending' in text
    assert 'not human or native-speaker certification' in text
