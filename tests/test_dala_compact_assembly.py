import pytest
from dfm12.dala_compact_assembly import unready, CONTRACT, prepare
from dfm12.io import write_json


def entry():
    return dict(audit_contract=CONTRACT, status='accepted_local_tokenized', split='train',
        uploaded=False, producer_v2_audit_equivalent=False, task='correction', output='train', tokenized_path='tokens')


def test_explicit_local_contract():
    assert unready(entry()) is None


@pytest.mark.parametrize('key,value', [('split','test'),('uploaded',True),('producer_v2_audit_equivalent',True),('task','other')])
def test_false_equivalence_and_heldout_blocked(key,value):
    e=entry();e[key]=value
    assert unready(e) == 'invalid_dala_compact_contract'


def test_incomplete_finalization_blocks(tmp_path):
    write_json(tmp_path/'complete.json',dict(success=False))
    with pytest.raises(ValueError,match='incomplete'):
        prepare(tmp_path,tmp_path/'view')
