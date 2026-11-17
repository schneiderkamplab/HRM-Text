import hashlib,json
from types import SimpleNamespace as S
import pytest
import scripts.log_danish_semantic_headline as module


def fixture(tmp_path,monkeypatch):
    rows=[];logs={};root=tmp_path/'model';data=tmp_path/'data';data.mkdir()
    for i,family in enumerate(module.FAMILIES):
        samples=[]
        for n in range(i+1):
            sid=f'{family}-{n}';row={'id':sid,'family':family,'subset':'danwic_poly_selection','input':'prompt '+sid,'target':'ja','labels':['ja','nej']};rows.append(row)
            samples.append(S(id=sid,input=row['input'],target='ja',error=None,output=S(completion='ja' if i==0 else 'nej')))
        p=root/family/'inspect'/'test.eval';p.parent.mkdir(parents=True);p.write_text('test')
        logs[str(p)]=S(status='success',eval=S(task_args={'family':family}),samples=samples)
    raw=''.join(json.dumps(r)+'\n' for r in rows).encode();(data/'records.jsonl').write_bytes(raw)
    monkeypatch.setattr(module,'read_eval_log',lambda p:logs[str(p)])
    return {'result_root':str(root)},{'data_dir':str(data),'records_sha256':hashlib.sha256(raw).hexdigest()},logs


def test_headline_equal_family_not_sample_weighted(tmp_path,monkeypatch):
    model,manifest,_=fixture(tmp_path,monkeypatch);metrics,_=module.aggregate(model,manifest)
    assert metrics[module.PREFIX+'/overall']==pytest.approx(1/7)
    assert metrics[module.PREFIX+'/sample_count']==28


@pytest.mark.parametrize('failure',['duplicate','error','wrong_prompt','incomplete'])
def test_no_headline_from_incomplete_or_wrong_population(tmp_path,monkeypatch,failure):
    model,manifest,logs=fixture(tmp_path,monkeypatch);l=list(logs.values())[-1]
    if failure=='duplicate':l.samples[-1]=l.samples[0]
    if failure=='error':l.samples[0].error='transport failure'
    if failure=='wrong_prompt':l.samples[0].input='different'
    if failure=='incomplete':l.samples.pop()
    with pytest.raises(AssertionError):module.aggregate(model,manifest)
