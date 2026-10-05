import pytest
from dfm12 import dala_compact_upload_queue as q


def test_exact_authorized_scope():
    assert list(q.SCOPE)==['en','de','fr','es','it','pt-PT','cs','nl','fa']
    assert {k for k,v in q.SCOPE.items() if v=='recovery'}=={'nl','fa'}
    assert 'sk' not in q.SCOPE


def test_incomplete_integration_refused(tmp_path):
    group=tmp_path/'groups/en-baseline'
    q.write_json(group/'integration.json',dict(status='exported_not_tokenized',contract=q.CONTRACT))
    with pytest.raises(ValueError,match='Incomplete'):
        q.prepare_item(tmp_path,'en','baseline')


def test_queue_has_no_implicit_upload_or_central_write(tmp_path,monkeypatch):
    def item(root,lang,pool):
        return dict(language=lang,subset=pool,uploaded=False,
                    train_components=[dict(rows=3,tokens=10),dict(rows=3,tokens=12)])
    monkeypatch.setattr(q,'prepare_item',item)
    output=tmp_path/'queue'
    result=q.prepare(tmp_path,output)
    assert not result['uploaded'] and len(result['items'])==9
    handoff=q.load(output/'integration-handoff.json')
    assert handoff['training_rows']==54 and handoff['tokens']==198
    assert not handoff['combined_integration_performed'] and not handoff['central_registry_modified']
    assert q.load(output/'seal.json')['queue']==q.pinned(output/'queue.json')
    with pytest.raises(FileExistsError):q.prepare(tmp_path,output)
