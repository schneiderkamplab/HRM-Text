import pytest
from scripts import dfm13_repochat_student12_retry as m


def runtime(tmp_path):
    files={'.gitignore':'ignored','README.md':'Overview','src/main.py':'answer = 42','src/nested/a.py':'other'}
    for name,text in files.items():
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    return m.Tools(tmp_path,{'files':{name:m.b.file_sha(tmp_path/name) for name in files}})


def test_root_alias_and_directories(tmp_path):
    tools=runtime(tmp_path);a=tools.execute('list_files',{'prefix':'.','after':'.'})
    assert a==tools.execute('list_files',{'prefix':'','after':''})
    assert a['directories']==['src/'] and 'src/main.py' not in a['paths']
    assert tools.execute('search_repository',{'prefix':'.','query':'answer'})['matches'][0]['path']=='src/main.py'


def test_no_read_limit_weakening(tmp_path):
    with pytest.raises(Exception):runtime(tmp_path).execute('read_file',{'path':'README.md','start_line':1,'line_count':50})


def test_original_successes_not_selected(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path)
    ready=m.prepare()
    assert len(ready['records'])==12 and ready['attempts_per_case']==1
    assert ready['buckets']=={'context_absence_response_without_tools':3,'root_prefix_or_path_misunderstanding':4,'tool_round_exhaustion':2,'student_context_exhaustion':1,'read_count_schema_error':2}
    for r in ready['records']:
        assert m.b.load(m.old.ROOT/'trajectories'/r['task']['id']/'outcome.json')['status']=='failed'
