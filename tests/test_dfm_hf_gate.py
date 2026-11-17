import hashlib
import json
import pytest
from scripts.dfm_hf_gate import require_dfm10


def setup_gate(tmp_path):
    base=tmp_path/'dfm10-hf-v2'
    (base/'union').mkdir(parents=True)
    (base/'union/tokenizer_info.json').write_text('{}')
    cfg=base/'hf_recipe.json'
    cfg.write_text(json.dumps({'recipe':'dfm10-hf-v2'}))
    h=hashlib.sha256(cfg.read_bytes()).hexdigest()
    receipt={'version':10,'status':'matched','verified_files':41,'input_policy':'HF-only plus lexdk/DBC','config_sha256':h}
    (base/'verified.json').write_text(json.dumps(receipt))
    (base/'inputs-verified.json').write_text(json.dumps({'config_sha256':h}))
    (base/'all-token-comparison.json').write_text(json.dumps({'status':'matched','tasks':4351}))
    return base,receipt


def test_exact_gate(tmp_path):
    base,_=setup_gate(tmp_path)
    assert require_dfm10(tmp_path)['base_union']==str(base/'union')


def test_old_local_receipt_never_releases(tmp_path):
    old=tmp_path/'dfm10';old.mkdir()
    (old/'verified.json').write_text('{"status":"matched"}')
    with pytest.raises(FileNotFoundError):require_dfm10(tmp_path)


@pytest.mark.parametrize('key,value',[('verified_files',40),('status','mismatch'),('input_policy','local'),('config_sha256','wrong')])
def test_reject_incomplete_or_changed_gate(tmp_path,key,value):
    base,r=setup_gate(tmp_path);r[key]=value
    (base/'verified.json').write_text(json.dumps(r))
    with pytest.raises(ValueError):require_dfm10(tmp_path)


def test_scheduled_runner_does_not_launch_before_gate(tmp_path, monkeypatch):
    from scripts import schedule_dfm11_hf as scheduler
    from scripts.dfm_hf_gate import digest
    work=tmp_path/'dfm11';work.mkdir()
    config=tmp_path/'config.json';config.write_text('{}')
    (work/'schedule.json').write_text(json.dumps({'config_sha256':digest(config),'stages':['acquire']}))
    monkeypatch.setattr(scheduler.recipe,'QUEUE',tmp_path)
    monkeypatch.setattr(scheduler.recipe,'CONFIG',config)
    def forbidden(*args,**kwargs):
        pytest.fail('Launched reconstruction before exact verification')
    monkeypatch.setattr(scheduler.subprocess,'run',forbidden)
    class EndWait(BaseException): pass
    def stop_wait(seconds): raise EndWait()
    monkeypatch.setattr(scheduler.time,'sleep',stop_wait)
    with pytest.raises(EndWait): scheduler.run()
    state=json.loads((work/'scheduled-progress.json').read_text())
    assert state['status']=='waiting' and state['completed']==[]
