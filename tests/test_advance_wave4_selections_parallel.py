from concurrent.futures import ThreadPoolExecutor
import threading
import time
import pytest
from dfm12.io import load,write_json
from scripts import advance_wave4_selections_parallel as m


def fixture(tmp_path):
    pairs=[['en',str(i)] for i in range(8)]
    write_json(tmp_path/'translations/config.json',{'requested_pairs':pairs})
    manifest=tmp_path/'manifest.json'
    write_json(manifest,{'components':[{'component':'direct-'+'-'.join(p)} for p in pairs]})
    return manifest


def test_bounded_once_per_pair_and_single_status_writer(tmp_path,monkeypatch):
    manifest=fixture(tmp_path);seen=[];active=0;peak=0;guard=threading.Lock()
    def work(root,pair,path):
        nonlocal active,peak
        with guard:seen.append(pair);active+=1;peak=max(peak,active)
        time.sleep(.01)
        with guard:active-=1
        return 'ready'
    monkeypatch.setattr(m,'select_one',work)
    result=m.cycle(tmp_path,manifest,4,threading.Event(),lambda:ThreadPoolExecutor(max_workers=4))
    assert len(seen)==len(set(seen))==8 and 1<peak<=4
    assert all(v=='ready' for v in result.values())
    status=load(tmp_path/'translation-release/selection-status.json')
    assert status['cycle_complete'] and not status['inflight']


def test_drain_does_not_dispatch_more_pairs(tmp_path,monkeypatch):
    manifest=fixture(tmp_path);stop=threading.Event();seen=[]
    def work(root,pair,path):seen.append(pair);stop.set();return 'ready'
    monkeypatch.setattr(m,'select_one',work)
    m.cycle(tmp_path,manifest,1,stop,lambda:ThreadPoolExecutor(max_workers=1))
    assert len(seen)==1
    assert load(tmp_path/'translation-release/selection-status.json')['draining']


def test_duplicate_pairs_fail_before_workers(tmp_path):
    manifest=fixture(tmp_path)
    write_json(tmp_path/'translations/config.json',{'requested_pairs':[['en','x'],['en','x']]})
    with pytest.raises(ValueError,match='Duplicate'):m.cycle(tmp_path,manifest,4,threading.Event())


def test_errors_remain_errors_not_ready(tmp_path,monkeypatch):
    manifest=fixture(tmp_path)
    def work(*args):raise ValueError('drift')
    monkeypatch.setattr(m,'select_one',work)
    result=m.cycle(tmp_path,manifest,2,threading.Event(),lambda:ThreadPoolExecutor(max_workers=2))
    assert all('error' in value for value in result.values())


def test_existing_controller_lock_prevents_second_owner(tmp_path,monkeypatch):
    from dfm12.io import lock
    import sys
    monkeypatch.setattr(sys,'argv',['selector','--root',str(tmp_path),'--workers','4'])
    monkeypatch.setattr(m.signal,'signal',lambda *args:None)
    monkeypatch.setattr(m,'freeze',lambda *args:pytest.fail('Second owner must not reach freeze'))
    with lock(tmp_path/'translation-release/selection-advance.lock'):
        with pytest.raises(BlockingIOError):m.main()
