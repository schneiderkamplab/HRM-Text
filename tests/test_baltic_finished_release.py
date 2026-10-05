import pytest
from dfm12.baltic_finished_release import validate
from dfm12.baltic_finished_assembly import unready,CONTRACT


def test_nonaccepted_not_exported(tmp_path):
    with pytest.raises(ValueError,match='Nonaccepted'):
        validate('id','hash',dict(effective_keep=False,terminal=True),tmp_path)


def test_local_contract_does_not_fake_publication():
    e=dict(publication_contract=CONTRACT,status='accepted_local_tokenized',uploaded=False,
           tokenization_performed=True,export_manifest_sha256='sha')
    assert unready(e) is None
    e['uploaded']=True
    assert unready(e)=='invalid_baltic_local_contract'
