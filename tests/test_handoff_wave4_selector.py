from types import SimpleNamespace
from dfm12.io import write_json
from scripts import handoff_wave4_selector as m
import pytest


@pytest.mark.parametrize('active,age,complete,expected',[
    (False,10,True,True),(True,10,True,False),(False,121,True,False),(False,10,False,False)])
def test_idle_requires_complete_recent_pass_no_active_locks(tmp_path,monkeypatch,active,age,complete,expected):
    pin=dict(pid=123,start_ticks='1',session_id=123,cmdline=['selector'],create_time=1)
    monkeypatch.setattr(m,'identity',lambda pid:pin)
    monkeypatch.setattr(m.time,'time',lambda:1000)
    write_json(tmp_path/'translations/config.json',{'requested_pairs':[['en','da']]})
    write_json(tmp_path/'translation-release/selection-status.json',dict(time=1000-age,pairs={'en-da':'ready'} if complete else {}))
    files=[SimpleNamespace(path=str((tmp_path/'translation-release/selection-advance.lock').resolve()))]
    if active:files.append(SimpleNamespace(path=str(tmp_path/'translation-release/en-da/.lock')))
    monkeypatch.setattr(m.psutil,'Process',lambda pid:SimpleNamespace(open_files=lambda:files))
    original=m.Path.read_text
    monkeypatch.setattr(m.Path,'read_text',lambda self,*a,**k:'hrtimer_nanosleep' if str(self)=='/proc/123/wchan' else original(self,*a,**k))
    assert (m.idle_evidence(tmp_path,pin) is not None)==expected


def test_identity_change_fails_closed(tmp_path,monkeypatch):
    pin=dict(pid=1,start_ticks='old',session_id=1,cmdline=['old'])
    monkeypatch.setattr(m,'identity',lambda pid:{**pin,'start_ticks':'new'})
    with pytest.raises(ValueError,match='identity'):m.idle_evidence(tmp_path,pin)
