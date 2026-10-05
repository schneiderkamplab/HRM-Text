from copy import deepcopy
from pathlib import Path
import pytest
from dfm12 import wave31_capacity as c
from dfm12.lb_seed_capacity import nonoverlap


def fixture(tmp_path,monkeypatch):
    ready=tmp_path/'ready.json';c.write_json(ready,{'revision':'test-only'})
    monkeypatch.setattr(c,'DOWNLOAD',tmp_path)
    measurement=tmp_path/'measurement.json'
    m={'model':c.MODEL,'revision':'test-only','duration_seconds':300,
       'servers':{str(p):{'aggregate_concurrency':32,'max_num_seqs':64,'completed':10,
           'kv_high_water':.8,'preemptions_delta':0,'request_errors_delta':0,
           'oom_count':0,'p95_seconds':30} for p in range(8800,8808)}}
    c.write_json(measurement,m)
    profile={'model':c.MODEL,'revision':'test-only','aggregate_client_concurrency_per_server':32,
      'server_max_num_seqs':64,'client_allocations':{'wave4':24,'baltic':8},
      'measurements':[{'path':str(measurement),'sha256':c.file_hash(measurement)}],
      'selected_after_ramp_review':True,'reviewer':'unit-test fixture, not real capacity evidence'}
    return profile,m,measurement


def test_measured_above_eight(tmp_path,monkeypatch):
    p,_,_=fixture(tmp_path,monkeypatch)
    assert c.validate(p)==(32,64)


@pytest.mark.parametrize('field,value',[('kv_high_water',.96),('preemptions_delta',1),('request_errors_delta',1),('completed',0)])
def test_unstable_rejected(tmp_path,monkeypatch,field,value):
    p,m,path=fixture(tmp_path,monkeypatch);m['servers']['8800'][field]=value
    c.write_json(path,m);p['measurements'][0]['sha256']=c.file_hash(path)
    with pytest.raises(ValueError):c.validate(p)


def test_aggregate_and_missing_evidence(tmp_path,monkeypatch):
    p,_,_=fixture(tmp_path,monkeypatch);p['client_allocations']['baltic']=32
    with pytest.raises(ValueError):c.validate(p)
    p['client_allocations']['baltic']=8;p['measurements']=[]
    with pytest.raises(ValueError):c.validate(p)


def test_nonoverlap():
    assert nonoverlap((0,500),(500,1000))
    assert not nonoverlap((0,500),(499,1000))
