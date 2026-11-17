import gzip
import json
from pathlib import Path
import importlib.util
import numpy as np
import pytest
from scripts import rebuild_dfm12_hf as recipe


def test_train_only_mapping_and_ambiguity():
    c={'name':'dfm12-dala-uk-correction','tokenized_parts':['x/dfm12-dala-uk-correction__train-00000.jsonl.gz']}
    p={'repo_id':'schneiderkamplab/dala-uk-audited','files':dict.fromkeys(['data/correction/train-00000.jsonl.gz','data/correction/test-00000.jsonl.gz','data/acceptability/train-00000.jsonl.gz'])}
    files,mode=recipe.source_files(c,p)
    assert files==['data/correction/train-00000.jsonl.gz']
    assert mode=='pair-order-50000'
    p['repo_id']='org/direct'
    with pytest.raises(ValueError,match='Ambiguous'):recipe.source_files(c,p)


def test_resharding_preserves_rows_and_boundaries(tmp_path,monkeypatch):
    monkeypatch.setattr(recipe,'WORK',tmp_path)
    src=tmp_path/'downloads/dala-xx-audited/data/correction/train-00000.jsonl.gz';src.parent.mkdir(parents=True)
    with gzip.open(src,'wt') as f:
        for i in reversed(range(50002)):f.write(json.dumps({'i':i,'text':'æ日本','metadata':{'pair_id':str(i//2),'variant':'clean' if i%2==0 else 'corrupted','split':'train'}})+'\n')
    c={'name':'dfm12-dala-xx-correction','mode':'pair-order-50000','repo_id':'org/dala-xx-audited','files':['data/correction/train-00000.jsonl.gz'],'rows':50002,'tokenized_parts':['dfm12-dala-xx-correction__train-00000.jsonl.gz','dfm12-dala-xx-correction__train-00001.jsonl.gz']}
    provenance=tmp_path/'downloads/dala-xx-audited/provenance/train.pairs.jsonl.gz';provenance.parent.mkdir()
    with gzip.open(provenance,'wt') as f:
        for i in range(25001):f.write(json.dumps({'pair_id':str(i)})+'\n')
    recipe.materialize_component(c)
    for part,count,start in [('00000',50000,0),('00001',2,50000)]:
        with gzip.open(tmp_path/'inputs'/c['name']/f'train-{part}.jsonl.gz','rt') as f:rows=[json.loads(x) for x in f]
        assert len(rows)==count and rows[0]['i']==start
    recipe.materialize_component(c)


def test_frozen_merge_offsets_and_permutation(tmp_path):
    path=recipe.WORK/'code/combine.py'
    spec=importlib.util.spec_from_file_location('dfm12.test_frozen_combine',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    for name,offset,n in [('base',0,3),('extra',0,2)]:
        d=tmp_path/name;d.mkdir()
        for field in recipe.FIELDS:
            np.save(d/(field+'.npy'),np.arange(n,dtype=np.uint64) if field.endswith('_start') else np.ones(n,dtype=np.uint64))
    report=m.merge_epoch(tmp_path/'base',tmp_path/'extra',tmp_path/'out',100,0)
    assert report['base_rows']==3 and report['added_rows']==2
    expected=np.array([0,1,2,100,101])[np.random.default_rng(0).permutation(5)]
    assert np.array_equal(np.load(tmp_path/'out/inst_start.npy'),expected)


def test_gate_rejects_partial_or_failed_dfm11(tmp_path,monkeypatch):
    monkeypatch.setattr(recipe,'require_dfm10',lambda q:{'test':True})
    monkeypatch.setattr(recipe,'ROOT',tmp_path)
    w=tmp_path/'dfm11';w.mkdir();cfg=tmp_path/'config/data/dfm11_hf_rebuild.json';cfg.parent.mkdir(parents=True);cfg.write_text('{}')
    (w/'inputs-verified.json').write_text(json.dumps({'config_sha256':recipe.sha(cfg),'predecessor':{'test':True}}))
    (w/'all-token-comparison.json').write_text(json.dumps({'status':'matched','tasks':290}))
    with pytest.raises(FileNotFoundError):recipe.require_dfm11(tmp_path)
    (w/'verified.json').write_text(json.dumps({'version':11,'status':'matched','verified_files':40,'input_policy':'HF-only plus lexdk/DBC'}))
    with pytest.raises(ValueError,match='gate'):recipe.require_dfm11(tmp_path)
    (w/'verified.json').write_text(json.dumps({'version':11,'status':'matched','verified_files':41,'input_policy':'HF-only plus lexdk/DBC'}))
    (w/'sampled').mkdir();(w/'sampled/metadata.json').write_text('{}')
    assert recipe.require_dfm11(tmp_path)['sampled']==str(w/'sampled')
