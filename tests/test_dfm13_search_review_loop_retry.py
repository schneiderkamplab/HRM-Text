import pytest
from scripts.dfm13_search_review_loop_retry import changed_request

def response(tokens=18000,tail=' \\n'*200):
    return dict(usage=dict(prompt_tokens=tokens),choices=[dict(finish_reason='length',message=dict(content=tail))])

def test_changed_request_preserves_input():
    original=dict(messages=[dict(role='user',content='same evidence')],max_tokens=2048)
    changed=changed_request(original,response())
    assert changed['messages']==original['messages']
    assert changed['frequency_penalty']==0.5 and changed['max_tokens']==3072
    assert original['max_tokens']==2048

def test_reject_context_overflow():
    with pytest.raises(ValueError):changed_request({},response(31000))

def test_nonloop_not_blindly_retried():
    with pytest.raises(ValueError):changed_request({},response(tail='actual substantive text '*100))
