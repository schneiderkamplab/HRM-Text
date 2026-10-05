import pytest
from dfm12.io import write_json,load
from scripts.snapshot_completed_dala_groups import snapshot


def test_missing_language_not_partial_success(tmp_path):
    source=tmp_path/'source';write_json(source/'registry.json',dict(additions=[]))
    with pytest.raises(ValueError,match='not complete'):
        snapshot(source,tmp_path/'out',['en'])


def test_complete_selected_group_explicit_scope(tmp_path):
    source=tmp_path/'source';group=source/'groups/en-baseline'
    entries=[dict(language='en',task=t,rows=2,tokens=10,export_receipt=dict(path=str(group/'export.json')))
             for t in ['acceptability','correction']]
    write_json(group/'integration.json',dict(status='complete_train_only',components=entries))
    write_json(source/'registry.json',dict(additions=entries))
    snapshot(source,tmp_path/'out',['en'])
    assert 'NOT whole' in load(tmp_path/'out/complete.json')['scope']
    assert not (source/'complete.json').exists()
