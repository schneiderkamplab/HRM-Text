import os
import pytest
from scripts import dfm13_repo_bulk_interlude as watcher


@pytest.mark.parametrize('document,expected', [
    ({'status':'complete'}, False),
    ({'status':'complete','all_gpu_stages_terminal':True}, False),
    ({'status':'running','all_gpu_stages_terminal':True,'gpu_clients_stopped':True}, False),
    ({'status':'complete','all_gpu_stages_terminal':True,'gpu_clients_stopped':True}, True),
    ({'status':'failed','all_gpu_stages_terminal':True,'gpu_clients_stopped':True}, True),
    ({'status':'complete','all_gpu_stages_terminal':'true','gpu_clients_stopped':True}, False),
])
def test_all_gpu_stages_required(document,expected):
    assert watcher.terminal(document) is expected


def test_identity_matches_only_same_process():
    current=watcher.identity(os.getpid())
    assert watcher.same(current)
    assert not watcher.same(dict(current,start_ticks='wrong'))
    assert not watcher.same(dict(current,pid=999999999))
