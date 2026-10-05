import importlib.util
from pathlib import Path
from types import SimpleNamespace

from dfm12 import wave4_group_runtime as runtime
from dfm12.io import load,write_json


def test_full_execute_group_successor(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('shard_fixture',Path(__file__).with_name('test_wave4_shard_runtime.py'))
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    def controller(owner,root,claims):
        value=load(root/'ownership.json');value['runnable_groups']=[['lt','tool-dialogue']]
        write_json(root/'ownership.json',value)
        return runtime.controller(owner,root,claims)
    fixture.runtime=SimpleNamespace(Owner=runtime.previous.Owner,GlobalClaims=runtime.previous.GlobalClaims,controller=controller)
    fixture.test_full_execute_mock_http_real_ledger(tmp_path,monkeypatch)


def test_blocked_group_excluded(tmp_path):
    from dfm12.multilingual_quarter import Ledger
    write_json(tmp_path/'ownership.json',dict(endpoint='http://127.0.0.1:8800/v1',runnable_groups=[['lt','tool-dialogue']]))
    base=Ledger(tmp_path/'jobs.sqlite')
    base.initialize([dict(language='lt',family='tool-dialogue',accepted_target=3)])
    base.db.execute("UPDATE groups SET blocked='seed_shortage'");base.close()
    owner=runtime.previous.Owner()
    try:
        c=runtime.controller(owner,tmp_path,runtime.previous.GlobalClaims(tmp_path/'registry.sqlite'))
        ledger=c.Ledger(tmp_path/'jobs.sqlite')
        try:
            assert ledger.remaining_groups()==[]
            assert owner.remaining_hint is False
            assert ledger.reserve(None,ValueError,tmp_path) is None
        finally:ledger.close()
    finally:owner.close()
