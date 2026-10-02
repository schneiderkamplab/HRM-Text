import pytest
from scripts import dfm13_repochat_student25 as m


def tools(tmp_path):
    (tmp_path/'x.py').write_text('def greet():\n    return "hello"\n')
    receipt={'files':{'x.py':m.b.file_sha(tmp_path/'x.py')}}
    return m.Tools(tmp_path,receipt)


def test_complete_lines_and_exact_replay(tmp_path):
    runtime=tools(tmp_path)
    args={'path':'x.py','start_line':1,'line_count':1}
    value=runtime.execute('read_file',args)
    assert value['lines']==['1: def greet():'] and value['next_start_line']==2
    assert runtime.execute('read_file',args)==value


def test_schema_refuses_excess(tmp_path):
    with pytest.raises(Exception):
        tools(tmp_path).execute('read_file',{'path':'x.py','start_line':1,'line_count':31})


def test_no_orphan_results():
    with pytest.raises(ValueError):m.strict([{'role':'tool','tool_call_id':'bad','content':'{}'}])


def test_actual_student_masks_and_oversize():
    student=m.Student()
    messages=[{'role':'system','content':m.SYSTEM},{'role':'user','content':'What does greet do?'},
              {'role':'assistant','content':'','tool_calls':[{'id':'call1','type':'function','function':{'name':'read_file','arguments':'{"path":"x.py","start_line":1,"line_count":2}'}}]},
              {'role':'tool','tool_call_id':'call1','content':'{"path":"x.py","lines":["1: def greet():", "2: return hello"]}'},
              {'role':'assistant','content':'The function returns hello (x.py:2).'}]
    m.strict(messages)
    rendered=student.targets(messages)
    assert [x['target_message_index'] for x in rendered]==[2,4]
    assert all(x['prompt_masked'] and x['fits_student_context'] for x in rendered)
    messages[-1]['content']='long repeated output '*5000
    oversized=student.targets(messages)
    assert not oversized[-1]['fits_student_context']
    assert len(messages[-1]['content'])>10000


def test_selection_fresh_unique():
    inventory=m.b.load(m.INVENTORY/'inventory.json')['tasks']
    selected=[]
    for prefix in m.PREFIXES:
        matches=[x for x in inventory if x['id'].startswith(prefix)]
        assert len(matches)==1 and not matches[0]['previously_inventoried']
        selected.append(matches[0]['id'])
    assert len(set(selected))==len(selected)
