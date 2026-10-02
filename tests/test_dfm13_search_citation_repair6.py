from scripts import dfm13_search_citation_repair6 as repair


def test_repair_scope_not_automatic_citation_insertion():
    assert len(repair.NOTES)==6
    assert 'not a source actually retrieved' in repair.NOTES['6b416b17']
    assert 'Do not relabel base-model results as Instruct' in repair.NOTES['64b59e0d']
    assert 'Do not transfer Vivo X100 or Meizu 21 Pro' in repair.NOTES['99fe14a8']
    assert 'Do not invent mandatory standards' in repair.NOTES['247e1f93']


def test_teacher_instruction_does_not_mutate_input(tmp_path):
    class Session:
        def post(self,*args,**kwargs):return kwargs['json']
    folder=tmp_path/'6b416b17suffix'/'generation'
    request=dict(messages=[dict(role='system',content='original')])
    result=repair.RepairSession(Session(),folder).post('unused',json=request)
    assert request['messages'][0]['content']=='original'
    assert 'Scoped evidence repair:' in result['messages'][0]['content']
    assert result['tool_choice']=='none'
