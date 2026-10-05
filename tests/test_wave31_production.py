from copy import deepcopy
from pathlib import Path
import pytest
import yaml
from dfm12 import wave31_production as p


def config(wave):
    base,_=p.modules(wave)
    c=yaml.safe_load(Path(base.CONFIG).read_text())
    c.update(wave=wave,generator=p.MODEL,auditor=p.MODEL)
    return c


def test_full_objective():
    q=p.quotas(config('wave4'))+p.quotas(config('baltic'))
    assert len(q)==78 and sum(x['accepted_target'] for x in q)==910000
    for language in {x['language'] for x in q}:
        assert sum(x['accepted_target'] for x in q if x['language']==language)==70000


@pytest.mark.parametrize('mutation',['model','language','family'])
def test_no_cuts(mutation):
    c=config('wave4')
    if mutation=='model':c['generator']='google/gemma-4-26B-A4B-it'
    elif mutation=='language':c['languages'].pop('lb')
    else:c['families']['openhermes']['full_priority_rows']=1000
    with pytest.raises(ValueError):p.quotas(c)


def test_new_ledger_no_inherited_accepts(tmp_path):
    c=p.controller('baltic',tmp_path)
    ledger=c.Ledger(tmp_path/'jobs.sqlite')
    try:
        ledger.initialize(p.quotas(config('baltic')))
        assert ledger.db.execute('SELECT sum(target),sum(accepted) FROM groups').fetchone()[:]==(140000,0)
        assert ledger.db.execute('SELECT count(*) FROM jobs').fetchone()[0]==0
        ledger.db.execute("UPDATE groups SET blocked='seed_shortage: fixture'")
        assert ledger.remaining_groups()==[]
        assert ledger.db.execute('SELECT sum(target) FROM groups').fetchone()[0]==140000
    finally:ledger.close()


def test_missing_second_audit_fails(tmp_path):
    with pytest.raises(FileNotFoundError):p.second_valid(tmp_path,'fixture',{'effective_keep':True})


def test_model_adapters_isolated(tmp_path):
    from dfm12 import wave_synthetic_runtime as live
    before=live.MODEL
    c=p.controller('baltic',tmp_path)
    assert live.MODEL==before and before!=p.MODEL
    assert c.v6.Budget.measure.__globals__['MODEL']==p.MODEL


def test_first_review_alone_cannot_increment_quota(tmp_path):
    c=p.controller('baltic',tmp_path);ledger=c.Ledger(tmp_path/'jobs.sqlite')
    try:
        ledger.initialize(p.quotas(config('baltic')))
        ledger.db.execute("INSERT INTO jobs(id,language,family,slot,status,origin,workdir) VALUES(?,?,?,?,?,?,?)",
            ('fixture','lv','grounded-instruct',100000,'running','production',str(tmp_path)))
        with pytest.raises(FileNotFoundError):ledger.finish('fixture',{'effective_keep':True})
        assert ledger.db.execute('SELECT sum(accepted) FROM groups').fetchone()[0]==0
    finally:ledger.close()


def test_missing_approval_blocks(tmp_path,monkeypatch):
    monkeypatch.setattr(p,'verify',lambda root:{'revision':'pinned'})
    with pytest.raises(FileNotFoundError):p.approved(tmp_path)


def test_production_snapshot_gate(tmp_path):
    c=p.controller('baltic',tmp_path)
    doc={'data':[{'id':p.MODEL,'max_model_len':32768,'root':str(tmp_path)}]}
    assert c.v6.endpoint_limit(doc)==32768
    doc['data'][0]['root']=str(tmp_path/'other')
    with pytest.raises(ValueError,match='snapshot mismatch'):c.v6.endpoint_limit(doc)


def test_no_fresh_comparison_dependency():
    source=Path(p.__file__).read_text()
    assert 'wave4_gemma31_fresh' not in source
