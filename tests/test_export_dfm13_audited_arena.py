import copy
import json
from pathlib import Path

import pytest

from scripts import export_dfm13_audited_arena as m


def row():
    return dict(id='id', metadata=dict(source='repo', revision='revision', license='cc-by-4.0'),
                messages=[dict(role='user', content='q'), dict(role='assistant', content='a'),
                          dict(role='tool', content='result'), dict(role='assistant', content='final')],
                target_message_index=3, tools=[dict(type='function', function=dict(name='lookup'))],
                chat_template_kwargs=dict(enable_thinking=False))


def test_dedup_preserves_target_tools_and_template():
    original = row()
    same = copy.deepcopy(original)
    same['id'] = 'another'
    same['metadata']['source'] = 'another-repo'
    assert m.identity(original) == m.identity(same)
    for key, value in [('target_message_index', 1), ('tools', []), ('chat_template_kwargs', {})]:
        other = copy.deepcopy(original)
        other[key] = value
        assert m.identity(original) != m.identity(other)


def test_no_truncation_or_native_rewriting():
    original = row()
    original['messages'][3]['content'] = 'word ' * 20000
    original['messages'][1]['tool_calls'] = [dict(id='call', type='function', function=dict(name='lookup', arguments={'q':'x'}))]
    before = copy.deepcopy(original)
    m.identity(original)
    assert original == before


@pytest.mark.parametrize('target', [True, -1, 4, 2, '3'])
def test_bad_targets_fail(target):
    value = row()
    value['target_message_index'] = target
    with pytest.raises(ValueError):
        m.identity(value)


def test_missing_license_fails():
    value = row()
    del value['metadata']['license']
    with pytest.raises(ValueError):
        m.identity(value)


def test_authorize_requires_exact_membership(tmp_path, monkeypatch):
    package = tmp_path/'dfm13-test'
    package.mkdir()
    proof = dict(origin_ledger='/ledger',seq=1,candidate_sha256='exact')
    (package/'provenance.jsonl').write_text(json.dumps(proof)+'\n')
    m.write_json(tmp_path/'manifest.json',dict(packages=[dict(name=package.name)]))
    selection = tmp_path/'selection.json'
    m.write_json(selection,dict(candidates=[dict(seq=1,candidate_sha256='exact')]))
    release = tmp_path/'release.json'
    m.write_json(release,{})
    monkeypatch.setattr(m,'validate',lambda _: dict(inventory_sha256='inventory'))
    monkeypatch.setattr(m,'validate_release',lambda _: dict(selections=[dict(ledger='/ledger',selection=str(selection))]))
    m.authorize(tmp_path,release)
    assert m.load(tmp_path/'private/publication-ready.json')['quality_certified'] is False
    proof['candidate_sha256']='changed'
    (package/'provenance.jsonl').write_text(json.dumps(proof)+'\n')
    with pytest.raises(ValueError,match='absent'):
        m.authorize(tmp_path,release)


def test_unknown_component_fails():
    with pytest.raises(ValueError,match='Unapproved'):
        m.source_component(dict(name='prism'))


def test_upload_requires_readiness(tmp_path, monkeypatch):
    mapping = tmp_path/'destinations.json'
    m.write_json(mapping,{})
    monkeypatch.setattr(m,'validate',lambda _: {})
    with pytest.raises(FileNotFoundError):
        m.upload(tmp_path,mapping)


def test_upload_replaces_existing_data_atomically(tmp_path, monkeypatch):
    import huggingface_hub as hf
    from types import SimpleNamespace
    folder = tmp_path/'dfm13-test'
    (folder/'data').mkdir(parents=True)
    m.write_json(folder/'manifest.json',dict(component='component'))
    files = ['README.md','manifest.json','data/train.jsonl','provenance.jsonl','duplicates.jsonl']
    for name in files:
        if name != 'manifest.json': (folder/name).write_text('test')
    package = dict(name=folder.name,rows=1,manifest_sha256=m.file_hash(folder/'manifest.json'))
    m.write_json(tmp_path/'manifest.json',dict(packages=[package]))
    release = tmp_path/'release.json'
    m.write_json(release,{})
    m.write_json(tmp_path/'private/publication-ready.json',dict(inventory_sha256='inventory',
        publication_checks_passed=True,release_path=str(release),release_sha256=m.file_hash(release)))
    mapping=tmp_path/'destinations.json'
    m.write_json(mapping,{'component':dict(repo_id='schneiderkamplab/dfm13-test',expected_revision='before')})
    monkeypatch.setattr(m,'validate',lambda _:dict(inventory_sha256='inventory'))
    monkeypatch.setattr(m,'validate_release',lambda _: {})
    calls=[]
    class API:
        def whoami(self): return {}
        def repo_info(self,*args,**kwargs): return SimpleNamespace(sha='before')
        def list_repo_files(self,*args,**kwargs):
            return files+['.gitattributes'] if kwargs.get('revision') else ['data/old.parquet','README.md','.gitattributes']
        def create_repo(self,*args,**kwargs): pass
        def create_commit(self,*args,**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(oid='after')
    monkeypatch.setattr(hf,'HfApi',API)
    monkeypatch.setattr(hf,'hf_hub_download',lambda repo,name,**kwargs:str(folder/name))
    result=m.upload(tmp_path,mapping)
    assert result['schneiderkamplab/dfm13-test']['status']=='verified'
    assert calls[0]['parent_commit']=='before'
    ops=calls[0]['operations']
    assert {o.path_in_repo for o in ops if isinstance(o,hf.CommitOperationDelete)}=={'data/old.parquet'}
    assert {o.path_in_repo for o in ops if isinstance(o,hf.CommitOperationAdd)}==set(files)


def test_native_tool_arguments_change_dedup_key():
    a=row()
    a['messages'][1]['tool_calls']=[dict(function=dict(name='lookup',arguments={'id':1}))]
    b=copy.deepcopy(a)
    b['messages'][1]['tool_calls'][0]['function']['arguments']['id']=2
    assert m.identity(a)!=m.identity(b)
