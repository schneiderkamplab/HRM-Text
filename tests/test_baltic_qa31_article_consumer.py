import json
import sqlite3
from pathlib import Path

import pytest

from dfm12 import baltic_qa31_article_consumer as c
from dfm12.io import digest,write_json


def example():
    record=dict(id='test',language='lv',component='baltic_lv_qa',messages=[
        dict(role='user',content='Question'),dict(role='assistant',content='Target')],
        target_message_index=1,provenance={},tools=[])
    p=dict(candidate=record,candidate_sha256=digest(record),upstream_record={'answer':'old'},binding={})
    side=dict(source_packet_sha256=digest(p),original_generation_source_verified=False,
        review_verdicts_included=False,admission_authorized=False,upstream_record=p['upstream_record'],
        candidate_articles=[],**{k:record[k] for k in ('messages','language','target_message_index','provenance')})
    return p,side


def test_no_hit_preserved_and_new_request():
    p,s=example();result=c.article_packet(p,s,[])
    assert result['candidate']==p['candidate']
    assert result['candidate_articles']==[]
    assert result['audit_request']['messages'][0]['content']==c.adapter.REVIEW_POLICY
    assert json.loads(result['audit_request']['messages'][1]['content'])['exact_generation_source_verified'] is False


@pytest.mark.parametrize('field',['messages','language','target_message_index','provenance','upstream_record'])
def test_original_binding_fail_closed(field):
    p,s=example();s[field]='changed'
    with pytest.raises(ValueError):c.article_packet(p,s,[])


def test_full_article_not_truncated():
    p,s=example();s['candidate_articles']=[{'id':'a'}]
    article={k:'test' for k in c.adapter.ARTICLE_FIELDS}
    article.update(language='lv',text='Long full article. '*20000)
    result=c.article_packet(p,s,[article])
    assert result['candidate_articles'][0]['text']==article['text']
    assert json.loads(result['audit_request']['messages'][1]['content'])['candidate_articles'][0]['text']==article['text']


def test_context_gate_keeps_all_rows_and_resumes(tmp_path):
    db=sqlite3.connect(tmp_path/'catalog.sqlite');c.catalog_schema(db)
    for key,fits in [('fits',True),('oversize',False),('nohit',True)]:
        db.execute('INSERT INTO catalog VALUES(?,?,?,?)',(key,'{}','{}','test'))
        db.execute('INSERT INTO budgets VALUES(?,?,?)',(key,json.dumps(dict(fits=fits,total_tokens=100 if fits else 50000)),0))
    db.commit()
    stats=c.inventory(db);db.close()
    assert stats['count']==3 and stats['dispatchable']==2 and stats['unresolved_context']==1
    engine=c.engine();runtime=engine.database(tmp_path)
    assert dict(runtime.execute('SELECT id,state FROM jobs'))==dict(fits='pending_review',oversize='needs_review_context',nohit='pending_review')
    runtime.execute("UPDATE jobs SET state='provisional_unchanged_keep' WHERE id='fits'")
    runtime.close();runtime=engine.database(tmp_path)
    assert runtime.execute("SELECT state FROM jobs WHERE id='fits'").fetchone()[0]=='provisional_unchanged_keep'
    runtime.close()


def test_article_engine_all_stages():
    engine=c.engine()
    assert engine.p.repair_request is c.adapter.repair_request
    assert engine.p.fresh_reaudit_request is c.adapter.fresh_reaudit_request
    assert c.base.engine().p.repair_request is c.base.repair_request


def test_old_calibration_rejected_even_if_base_gate_passes(tmp_path,monkeypatch):
    approval=tmp_path/'approval.json';write_json(approval,dict(diagnostic_root=str(tmp_path)))
    monkeypatch.setattr(c.base,'check_calibration',lambda *args:None)
    monkeypatch.setattr(c.common,'verify',lambda _:dict(schema='old-no-articles'))
    with pytest.raises(ValueError,match='article-aware'):
        c.check_calibration(dict(diagnostic_only=False,schema=c.SCHEMA,policy_sha256='new',evidence_sha256='e'),
                            dict(calibration_approval=str(approval)))


def test_token_budget_counts_entire_request_and_reserve():
    p,s=example();request=c.article_packet(p,s,[])['audit_request']
    class Tokenizer:
        def apply_chat_template(self,messages,**kwargs):
            assert messages==request['messages']
            assert kwargs['enable_thinking'] is True
            return [1]*25000
    result=c.budget.measure_request(request,Tokenizer(),32768)
    assert result['total_tokens']==33192 and not result['fits'] and not result['truncated']
