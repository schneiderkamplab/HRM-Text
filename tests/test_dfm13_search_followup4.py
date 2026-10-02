from scripts import dfm13_search_followup4 as client


def test_four_targeted_instructions_no_blind_reviewer_correction():
    assert len(client.NOTES)==4
    assert 'blindly copy a prior reviewer correction' in client.NOTES['b0d5dab9']
    assert 'exact drive times without evidence' in client.NOTES['f526f25f']


def test_actual_request_preserves_input_and_has_final_only_controls(tmp_path):
    class Session:
        def post(self,*args,**kwargs):return kwargs['json']
    request=dict(messages=[dict(role='system',content='original')])
    got=client.FollowupSession(Session(),tmp_path/'122a56ccsuffix'/'generation').post('unused',json=request)
    assert request['messages'][0]['content']=='original'
    assert got['tool_choice']=='none'
    assert got['temperature']==0.35
    assert got['max_tokens']==1536
