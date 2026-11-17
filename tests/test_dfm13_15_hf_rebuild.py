import json
from pathlib import Path
import pytest
from scripts import rebuild_dfm13_15_hf as r


def test_train_only_dala_selection():
 c={'name':'dfm13_dala_v2_compact_fa_recovery_correction'}
 p={'files':dict.fromkeys(['data/correction/train_representative.jsonl.gz','data/correction/test_challenge.jsonl.gz','data/acceptability/train_representative.jsonl.gz'])}
 assert r.files_for(13,c,p)==['data/correction/train_representative.jsonl.gz']


def test_dala_pool_and_shard_order(tmp_path,monkeypatch):
 monkeypatch.setattr(r,'Q',tmp_path)
 w=r.work(13);src=w/'downloads/org--dala/data/correction/train.jsonl';src.parent.mkdir(parents=True)
 rows=[{'id':i,'split':'train','publication_pool':pool,'messages':[]} for i,pool in enumerate(['baseline','recovery','recovery','baseline','recovery'])]
 src.write_text(''.join(json.dumps(x)+'\n' for x in rows))
 c={'name':'dfm13_dala_v2_compact_fa_recovery_correction','cap':4096,'part_rows':2,'files':['data/correction/train.jsonl'],'hf_repo_id':'org/dala','tasks':['one.jsonl','two.jsonl']}
 r.materialize_one(13,c)
 assert [json.loads(x)['id'] for x in (w/'inputs-capped/one.jsonl').read_text().splitlines()]==[1,2]
 assert json.loads((w/'inputs-capped/two.jsonl').read_text())['id']==4
 r.materialize_one(13,c)


def test_gate_requires_exact_chain(tmp_path,monkeypatch):
 monkeypatch.setattr(r,'Q',tmp_path);monkeypatch.setattr(r,'ROOT',tmp_path)
 monkeypatch.setattr(r.common,'require_dfm11',lambda:{'ok':True})
 w=r.work(12);w.mkdir();cfg=r.config(12);cfg.parent.mkdir(parents=True);cfg.write_text('{}')
 with pytest.raises(FileNotFoundError):r.require(12)
 receipt={'version':12,'status':'matched','verified_files':13,'input_policy':'HF-only plus lexdk/DBC','config_sha256':r.sha(cfg),'predecessor':{'ok':True}}
 (w/'verified.json').write_text(json.dumps(receipt));assert r.require(12)['sampled']==str(w/'sampled')
 receipt['predecessor']={};(w/'verified.json').write_text(json.dumps(receipt))
 with pytest.raises(ValueError):r.require(12)


def test_exported_nested_json_is_decoded(tmp_path,monkeypatch):
 monkeypatch.setattr(r,'Q',tmp_path)
 w=r.work(14);p=w/'downloads/org--sample/data/train.jsonl';p.parent.mkdir(parents=True)
 messages=[{'role':'user','content':'Hi'},{'role':'assistant','content':'Hello'}]
 p.write_text(json.dumps({'messages_json':json.dumps(messages),'tools_json':'[]'})+'\n')
 c={'name':'sample','cap':4096,'part_rows':None,'files':['data/train.jsonl'],'hf_repo_id':'org/sample','tasks':['sample__part-000000.jsonl']}
 r.materialize_one(14,c);out=json.loads((w/'inputs-capped'/c['tasks'][0]).read_text())
 assert out['messages']==messages and out['tools']==[] and out['target_message_index']==1


def test_tlpc_uses_full_history_and_2000_row_shards():
 for name in ('dfm13_tlpc_grounded_qa_fa','dfm13_tlpc_grounded_chat_fa'):
  assert r.tokenization_policy(13,name,set())==(None,2000)
 assert r.tokenization_policy(13,'dfm13_wave3_opus_fo_lv',set())==(4096,5000)
 assert r.tokenization_policy(13,'dfm13_dala_v2_compact_fa_recovery_correction',set())==(4096,25000)
 assert r.tokenization_policy(14,'dfm14-ar-denoising-r1',set())==(4096,None)
