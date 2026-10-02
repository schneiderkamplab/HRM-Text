from dfm12.european_stage import StageQueue, adjust, metrics
import asyncio
import json
import httpx
from dfm12.european_stage import run


def test_metrics_and_capacity():
    sample=metrics('vllm:kv_cache_usage_perc{model="x"} 0.25\nvllm:num_requests_waiting 0\n')
    assert adjust(128,sample)==134
    assert adjust(512,{'kv':0.96})==461
    assert adjust(128,{'kv':0.9})==128
    assert adjust(1024,{'kv':0.1})==1024
    assert adjust(512,{'kv':0.6,'preemption_delta':1})==461
    assert adjust(512,{'kv':0.2,'waiting':100})==512
    assert adjust(128,{'kv':0.2,'inflight':40})==128


def test_claim_and_resume(tmp_path):
    q=StageQueue(tmp_path/'jobs.sqlite')
    a=q.add('audit',{'request':{'x':1}})
    b=q.add('audit',{'request':{'x':2}})
    rows=q.claim_batch('audit','first',1)
    assert len(rows)==1 and rows[0][0]==a
    assert q.claim_batch('audit','second',10)[0][0]==b
    q.finish(a,'wrong',1,{})
    assert q.db.execute('select status from jobs where id=?',(a,)).fetchone()[0]=='running'
    q.finish(a,'first',1,{'keep':True})
    q.db.execute('update jobs set lease=0 where id=?',(b,))
    assert q.claim_batch('audit','third',10)[0][0]==b
    assert q.claim_batch('audit','fourth',10)==[]
    q.finish(b,'third',2,{'keep':False})
    assert q.status()==[{'stage':'audit','status':'done','count':2}]
    q.close()


def test_release_only_own_running_jobs(tmp_path):
    q=StageQueue(tmp_path/'jobs.sqlite')
    for i in range(3):q.add('audit',{'i':i})
    a=q.claim_batch('audit','mine',2)
    q.claim_batch('audit','other',1)
    q.finish(a[0][0],'mine',1,{'keep':True})
    assert q.release('mine')==1
    assert q.db.execute('select status,attempts from jobs where id=?',(a[1][0],)).fetchone()==('pending',0)
    assert q.db.execute("select count(*) from jobs where owner='other' and status='running'").fetchone()[0]==1
    q.close()


def test_batch_completion_is_atomic_and_owned(tmp_path):
    q=StageQueue(tmp_path/'jobs.sqlite')
    for i in range(4):q.add('audit',{'i':i})
    rows=q.claim_batch('audit','a',4)
    q.finish_batch('wrong',[(rows[0][0],1,{},None)])
    assert q.db.execute('select count(*) from events').fetchone()[0]==0
    q.finish_batch('a',[(rows[0][0],1,{},None),(rows[1][0],1,None,'bad JSON')])
    assert q.db.execute('select count(*) from events').fetchone()[0]==2
    q.finish_batch('a',[(rows[0][0],1,{},None)])
    assert q.db.execute('select count(*) from events').fetchone()[0]==2
    assert q.release('a')==2
    q.close()


def test_async_dispatch_persists_all_results(tmp_path,monkeypatch):
    path=tmp_path/'jobs.sqlite'
    q=StageQueue(path)
    for i in range(20):q.add('audit',{'request':{'model':'test','seed':i}})
    q.close()
    real_client=httpx.AsyncClient
    def handle(request):
        if request.url.path=='/metrics':
            return httpx.Response(200,text='vllm:kv_cache_usage_perc 0.8\n')
        result=dict(keep=True,reason='valid',language_quality=5,coherence=5,usefulness=5)
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}]})
    configurations=[]
    def make_client(**kwargs):
        configurations.append(kwargs)
        return real_client(transport=httpx.MockTransport(handle),**kwargs)
    monkeypatch.setattr(httpx,'AsyncClient',make_client)
    output=tmp_path/'out';output.mkdir()
    asyncio.run(run(path,'audit',['http://test/v1','http://test2/v1'],output,initial=4,maximum=8))
    pools=[c for c in configurations if 'limits' in c]
    assert len(pools)==2
    assert all(c['limits'].max_connections==8 and c['limits'].keepalive_expiry==2 for c in pools)
    q=StageQueue(path)
    assert q.status()==[dict(stage='audit',status='done',count=20)]
    assert json.loads((output/'completion.json').read_text())['counts']['done']==20
    q.close()
