import pytest
from scripts.queue_dfm13_fo_instruct_successor import source_entry,require_included,include_source
from dfm12.io import write_json


def entry():
    return dict(name='setur_fo',source_repo='Setur/fo-instruct',repeat=10,output='source',tokenized_path='tokens')


def test_waits_for_registration():
    assert source_entry({'additions':[]}) is None


def test_restart_predecessor_may_already_include_identical_fo_source():
    config = {'additions': []}
    include_source(config, entry())
    include_source(config, entry())
    assert config['additions'] == [entry()]
    with pytest.raises(ValueError, match='conflicting'):
        include_source(config, dict(entry(), repeat=1))


def test_registered_repo_id_schema():
    e=entry();e['repo_id']=e.pop('source_repo')
    assert source_entry({'additions':[e]})==e


def test_exact_repeat_and_unique_source():
    e=entry();assert source_entry({'additions':[e]})==e
    with pytest.raises(ValueError):source_entry({'additions':[e,e]})
    with pytest.raises(ValueError):source_entry({'additions':[dict(e,repeat=1)]})


def test_snapshot_not_enough_requires_verified_admission(tmp_path):
    write_json(tmp_path/'registry.snapshot.json',{'additions':[entry()]})
    write_json(tmp_path/'assembly.json',{'ready_additions':[]})
    with pytest.raises(ValueError):require_included(tmp_path)
    write_json(tmp_path/'assembly.json',{'ready_additions':[dict(name='setur_fo',repeat=10)]})
    assert require_included(tmp_path)==entry()
