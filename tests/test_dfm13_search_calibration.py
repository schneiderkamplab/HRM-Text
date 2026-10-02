import asyncio
import json
import socket
from types import SimpleNamespace

import pytest

from scripts import dfm13_search_calibration as c


@pytest.mark.parametrize('url', [
    'file:///etc/passwd','http://127.0.0.1/','http://[::1]/','http://169.254.169.254/',
    'http://10.0.0.2/','http://192.168.1.1/','http://localhost/',
    'https://example.com:8443/','https://user:pass@example.com/','http://host.internal/',
    'http://[::ffff:127.0.0.1]/'])
def test_ssrf_url(url):
    with pytest.raises(ValueError):
        c.public_url(url)


def test_public_url():
    assert c.public_url('https://docs.python.org/3/')=='https://docs.python.org/3/'


def test_native_wire_arguments_are_strings_without_mutating_template_input():
    messages=[dict(role='assistant',tool_calls=[dict(id='c',type='function',
        function=dict(name='search',arguments={'query':'real query'}))])]
    wire=c.wire_messages(messages)
    assert json.loads(wire[0]['tool_calls'][0]['function']['arguments'])=={'query':'real query'}
    assert messages[0]['tool_calls'][0]['function']['arguments']=={'query':'real query'}


def test_dns_checks_actual_connector_addresses(monkeypatch):
    async def go():
        async def addresses(*args, **kwargs):
            return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))]
        monkeypatch.setattr(asyncio.get_running_loop(),'getaddrinfo',addresses)
        with pytest.raises(ValueError, match='nonpublic'):
            await c.PublicResolver().resolve('looks-public.example',443)
    asyncio.run(go())


def test_redirect_rechecked_before_socket():
    class Response:
        status=302
        headers={'Location':'http://169.254.169.254/latest/meta-data/'}
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
    class Session:
        count=0
        def get(self,*args,**kwargs):
            self.count+=1
            return Response()
    web=c.Web()
    web.session=Session()
    with pytest.raises(ValueError,match='nonpublic'):
        asyncio.run(web.fetch('https://example.org/'))
    assert web.session.count==1


@pytest.mark.parametrize('raw',['{"a":1,"a":2}','{"a":NaN}'])
def test_strict_json(raw):
    with pytest.raises(ValueError): c.strict_json(raw)


@pytest.mark.parametrize('action',[
    {'action':'search','text':True}, {'action':'execute','text':'hello'},
    {'action':'search','text':' '}, {'action':'search','text':'query','extra':1},
])
def test_invalid_action(action):
    with pytest.raises(ValueError): c.check_action(action)


def test_eligibility_withholds_answers():
    row=dict(turn=1,timestamp='2025-03-18',messages_a=[dict(role='user',content='What does the Python asyncio library do?'),
        dict(role='assistant',content='OLD SECRET ANSWER')])
    row['messages_b']=[row['messages_a'][0],dict(role='assistant',content='OTHER OLD ANSWER')]
    prompt,reason=c.eligible(row)
    assert reason is None and 'ANSWER' not in prompt
    row['turn']=2
    assert c.eligible(row)[0] is None


def test_review_exact_evidence():
    pages={'https://example.org':{'body':'The real saved passage.'}}
    review=dict(verdict='keep',reason='Supported',evidence=[dict(url='https://example.org',quote='real saved',claim='Answer')])
    answer='Answer with [citation](https://example.org)'
    assert c.check_review(review,pages,answer)==review
    review['evidence'][0]['quote']='fabricated passage'
    with pytest.raises(ValueError): c.check_review(review,pages,answer)
    review['evidence']=[]
    with pytest.raises(ValueError): c.check_review(review,pages,answer)


@pytest.mark.parametrize('answer',[
    '[source](https://trusted.example/article-fabricated)',
    'https://trusted.example/article-fabricated',
    '[real](https://trusted.example/article) [fake](https://other.example/article)',
    '[query](https://trusted.example/article?invented=1)',
    '[fragment](https://trusted.example/article#invented)',
    '[source][ref]\n\n[ref]: https://trusted.example/article-fabricated',
    '<a href="https://trusted.example/article-fabricated">source</a>',
    '![source](https://trusted.example/article-fabricated)',
    '[source](https://trusted.example.evil.invalid/article)',
])
def test_all_citations_require_exact_opened_urls(answer):
    with pytest.raises(ValueError):
        c.check_citations(answer,{'https://trusted.example/article':{}})


@pytest.mark.parametrize('answer',[
    '[source](https://trusted.example/article)',
    '<https://trusted.example/article>',
    'Source: https://trusted.example/article.',
    '[source][ref]\n\n[ref]: https://trusted.example/article',
])
def test_exact_citations_pass(answer):
    assert c.check_citations(answer,{'https://trusted.example/article':{}})


def test_real_execution_before_review(tmp_path):
    class Model:
        calls=0
        async def ask(self,messages,schema,tools,directory,stage):
            self.calls+=1
            if stage=='review':
                assert 'original_timestamp' in messages[-1]['content']
                return dict(verdict='keep',reason='Supported',evidence=[dict(url='https://example.org/',quote='Documented fact',claim='Documented fact')])
            if self.calls==3:
                return dict(action='final',text='Documented fact [source](https://example.org/).')
            name='search' if self.calls==1 else 'open_page'
            text='test query' if name=='search' else 'https://example.org/'
            key='query' if name=='search' else 'url'
            return dict(action=name,text=text,assistant_message=dict(role='assistant',content='',tool_calls=[dict(id=str(self.calls),type='function',function=dict(name=name,arguments={key:text}))]))
    class Web:
        async def search(self,query): return dict(results=[dict(url='https://example.org/')])
        async def open_page(self,url): return dict(url=url,body='Documented fact from actual mocked fetch.')
    sample=dict(id='x',prompt='Find a documented fact.',original_timestamp='2025-03-18',date_policy='Original date preserved.')
    result=asyncio.run(c.trajectory(sample,Model(),Web(),tmp_path,8))
    assert result['verdict']=='keep'
    candidate=json.loads((tmp_path/'candidate.json').read_text())
    assert candidate['target_message_indices']==[2,4,6]
    assert candidate['admission_authorized'] is False
    assert [m['role'] for m in candidate['messages']]==['system','user','assistant','tool','assistant','tool','assistant']
    assert (tmp_path/'tool-00.json').exists() and (tmp_path/'review.json').exists()


def test_final_without_search_fails(tmp_path):
    class Model:
        async def ask(self,*args): return dict(action='final',text='Ungrounded final answer')
    sample=dict(id='x',prompt='Question',original_timestamp='2025',date_policy='Original date')
    with pytest.raises(ValueError,match='without_successful'):
        asyncio.run(c.trajectory(sample,Model(),None,tmp_path,8))


def test_pins_detect_edit(tmp_path):
    source=tmp_path/'source'
    source.write_text('original')
    c.atomic(tmp_path/'samples.json',[])
    c.atomic(tmp_path/'manifest.json',dict(pins={str(source):c.file_hash(source)},samples_sha256=c.file_hash(tmp_path/'samples.json')))
    c.verify(tmp_path)
    source.write_text('changed')
    with pytest.raises(ValueError,match='pin mismatch'): c.verify(tmp_path)


def test_irrelevant_provider_results_fail_preflight(tmp_path):
    class Web:
        provider='fake'
        async def search(self,query):
            return dict(results=[dict(title='Dentist Copenhagen',snippet='Unrelated',url='https://example.org/')])
    assert not asyncio.run(c.provider_preflight(Web(),tmp_path/'probe.json'))
    assert json.loads((tmp_path/'probe.json').read_text())['passed'] is False


def test_provider_canaries_are_not_general_quality_certification(tmp_path):
    class Web:
        provider='fake'
        async def search(self,query):
            return dict(results=[dict(title=query,snippet='Relevant lexical canary',url='https://example.org/')])
    assert asyncio.run(c.provider_preflight(Web(),tmp_path/'probe.json'))


def test_brave_missing_key_no_fallback(monkeypatch):
    monkeypatch.delenv('BRAVE_SEARCH_API_KEY',raising=False)
    with pytest.raises(ValueError,match='missing; no provider fallback'):
        asyncio.run(c.Web('brave').search('query'))


def test_jina_missing_key_no_fallback(monkeypatch):
    monkeypatch.delenv('JINA_API_KEY',raising=False)
    with pytest.raises(ValueError,match='JINA_API_KEY missing; no provider fallback'):
        asyncio.run(c.Web('jina').search('query'))


def test_jina_real_query_json_headers_snapshot_no_secret(monkeypatch,tmp_path):
    monkeypatch.setenv('JINA_API_KEY','test-secret-not-real')
    web=c.Web('jina',tmp_path)
    web.budget=c.SearchBudget(tmp_path/'campaign')
    async def fetch(url,headers=None):
        assert url=='https://s.jina.ai/?q=actual+query+%26+details'
        assert headers=={'Authorization':'Bearer test-secret-not-real','Accept':'application/json'}
        body=dict(code=200,status=20000,data=[dict(title='Actual title',url='https://example.org/page',
            description='Actual provider snippet',content='Actual long source text')])
        raw=json.dumps(body).encode()
        return raw,dict(requested_url=url,url=url,response_sha256=c.hashlib.sha256(raw).hexdigest(),retrieved_at='test')
    monkeypatch.setattr(web,'fetch',fetch)
    result=asyncio.run(web.search('actual query & details',owner='sample1'))
    assert result['results'][0]['snippet']=='Actual provider snippet'
    assert result['provider']=='jina'
    assert result['query']=='actual query & details'
    saved=next(tmp_path.glob('*.json')).read_text()
    assert 'Actual long source text' in saved
    assert 'test-secret-not-real' not in saved and 'Authorization' not in saved


def test_jina_malformed_response_fails(monkeypatch,tmp_path):
    monkeypatch.setenv('JINA_API_KEY','test-key')
    web=c.Web('jina')
    web.budget=c.SearchBudget(tmp_path)
    async def fetch(*args,**kwargs): return b'{"code":200,"data":"not results"}',{}
    monkeypatch.setattr(web,'fetch',fetch)
    with pytest.raises(ValueError,match='Jina search response'):
        asyncio.run(web.search('query',owner='sample1'))


def test_durable_campaign_cap_counts_crashes_and_full_cache(tmp_path):
    budget=c.SearchBudget(tmp_path)
    key,cached=budget.reserve('query0','owner0')
    assert cached is None
    raw=b'{"full":"untruncated page body"}'
    budget.complete(key,raw,{'retrieved_at':'original'})
    for i in range(1,100):
        budget.reserve(f'query{i}',f'owner{i}')
    budget.db.close()
    reopened=c.SearchBudget(tmp_path)
    assert reopened.reserve('query0','other-owner')[1]==(raw,{'retrieved_at':'original'})
    with pytest.raises(ValueError,match='exhausted'):
        reopened.reserve('query100','owner100')
    with pytest.raises(ValueError,match='unresolved'):
        reopened.reserve('query1','owner1')
    assert reopened.db.execute('SELECT COUNT(*) FROM searches').fetchone()[0]==100


def test_one_new_paid_query_per_sample(tmp_path):
    budget=c.SearchBudget(tmp_path)
    budget.reserve('first','same-owner')
    with pytest.raises(ValueError,match='one new paid'):
        budget.reserve('second','same-owner')


def test_bundled_content_used_without_page_network(monkeypatch,tmp_path):
    monkeypatch.setenv('JINA_API_KEY','test-key')
    web=c.Web('jina')
    web.budget=c.SearchBudget(tmp_path)
    calls=[]
    async def fetch(url,headers=None):
        calls.append(url)
        return json.dumps(dict(code=200,data=[dict(title='Source',url='https://example.org/',content='Full body. '*1000)])).encode(),{}
    monkeypatch.setattr(web,'fetch',fetch)
    async def exercise():
        await web.search('real query',owner='sample')
        page=await web.open_page('https://example.org/')
        await web.search('real query',owner='sample2')
        return page
    page=asyncio.run(exercise())
    assert len(calls)==1
    assert page['body']==('Full body. '*1000)[:10000]
    assert page['truncated'] is True
    cached=json.loads(web.budget.db.execute('SELECT raw FROM searches').fetchone()[0])
    assert cached['data'][0]['content']=='Full body. '*1000


def test_all_generation_uses_auto_native_tools(tmp_path):
    class Tokenizer:
        def apply_chat_template(self,*args,**kwargs): return [1,2,3]
    class Response:
        status=200
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def text(self):
            return json.dumps({'choices':[{'finish_reason':'tool_calls','message':{'content':None,
                'tool_calls':[{'id':'call1','type':'function','function':{'name':'search','arguments':'{"query":"real query"}'}}]}}]})
    class Session:
        requests=[]
        def post(self,url,json,**kwargs):
            self.requests.append(json)
            return Response()
    session=Session()
    model=c.Model(session,Tokenizer(),{'model':'test','context_tokens':32768},'http://localhost',10)
    messages=[dict(role='user',content='Question')]
    for stage in ('generate-00','generate-01','generate-01-citation-retry'):
        result=asyncio.run(model.ask(messages,None,c.TOOLS,tmp_path,stage))
        assert result['assistant_message']['tool_calls'][0]['function']['arguments']=={'query':'real query'}
    assert session.requests[0]['tool_choice']=='auto'
    assert session.requests[1]['tool_choice']=='auto'
    assert session.requests[2]['tool_choice']=='none'


@pytest.mark.parametrize('prompt',['Original question','Use search.\n\nOriginal question','Please keep the words Use search.'])
def test_steering_never_strips_user_prefix(prompt):
    messages=[dict(role='system',content='System'),dict(role='user',content=prompt)]
    steered=c.generation_messages(messages,True)
    assert steered[1]['content']=='Use search.\n\n'+prompt
    assert messages[1]['content']==prompt
    assert c.generation_messages(messages)[1]['content']==prompt
    cited=c.generation_messages(messages,True,cite=True)
    assert cited[1]['content']=='Cite sources with exact URLs.\n\nUse search.\n\n'+prompt
    assert messages[1]['content']==prompt


def test_no_search_retry_once_and_receipt(tmp_path):
    class Model:
        requests=[]
        async def ask(self,messages,schema,tools,directory,stage):
            self.requests.append((stage,messages))
            c.atomic(directory/(stage+'-request.json'),dict(messages=messages))
            return dict(action='final',text='No search answer')
    model=Model()
    sample=dict(id='x',prompt='Use search.\n\nMy original question',original_timestamp='2025',date_policy='Original date')
    with pytest.raises(ValueError,match='final_without'):
        asyncio.run(c.trajectory(sample,model,None,tmp_path,8))
    assert len(model.requests)==2
    assert model.requests[0][1][1]['content']==sample['prompt']
    assert model.requests[1][1][1]['content']=='Use search.\n\n'+sample['prompt']
    actual=json.loads((tmp_path/'generate-00-search-retry-request.json').read_text())
    assert actual['messages'][1]['content']=='Use search.\n\n'+sample['prompt']
    assert not (tmp_path/'candidate.json').exists()


def test_retry_success_preserves_original_candidate(tmp_path):
    prompt='Use search.\n\nFind a documented fact.'
    class Model:
        calls=0
        async def ask(self,messages,schema,tools,directory,stage):
            self.calls+=1
            c.atomic(directory/(stage+'-request.json'),dict(messages=messages))
            if stage=='review':
                assert json.loads(messages[-1]['content'])['prompt']['prompt']==prompt
                return dict(verdict='keep',reason='Supported',evidence=[dict(url='https://example.org/',quote='Documented fact',claim='Documented fact')])
            if self.calls==1:
                return dict(action='final',text='DISCARDED initial answer')
            assert messages[1]['content']=='Use search.\n\n'+prompt
            assert all('DISCARDED' not in m.get('content','') for m in messages)
            if self.calls==4:
                return dict(action='final',text='Documented fact [source](https://example.org/).')
            name='search' if self.calls==2 else 'open_page'
            text='test query' if name=='search' else 'https://example.org/'
            return dict(action=name,text=text,assistant_message=dict(role='assistant',content='',tool_calls=[dict(id=str(self.calls),type='function',function=dict(name=name,arguments={'query' if name=='search' else 'url':text}))]))
    class Web:
        async def search(self,query): return dict(results=[dict(url='https://example.org/')])
        async def open_page(self,url): return dict(url=url,body='Documented fact from saved page.')
    sample=dict(id='x',prompt=prompt,original_timestamp='2025',date_policy='Original date')
    result=asyncio.run(c.trajectory(sample,Model(),Web(),tmp_path,8))
    assert result['status']=='reviewed'
    candidate=json.loads((tmp_path/'candidate.json').read_text())
    assert candidate['messages'][1]['content']==prompt
    assert candidate['generation_steering_used'] is True
    assert 'DISCARDED' not in json.dumps(candidate)


@pytest.mark.parametrize('bad_span',[False,True])
@pytest.mark.parametrize('missing_citation',[False,True])
def test_search_delivered_page_needs_no_open_and_bad_spans_are_reviewable(tmp_path,bad_span,missing_citation):
    class Model:
        calls=0
        async def ask(self,messages,schema,tools,directory,stage):
            self.calls+=1
            if stage=='review':
                evidence=json.loads(messages[-1]['content'])['pages']
                assert evidence['https://example.org/']['body']=='Documented fact. '*10
                return dict(verdict='keep',reason='Supported',evidence=[dict(url='https://example.org/',
                    quote='Wrong literal span' if bad_span else 'Documented fact',claim='Documented fact')])
            if self.calls==2 or stage.endswith('-citation-retry'):
                assert 'Documented fact.' in messages[-1]['content']
                return dict(action='final',text='Documented fact.' if missing_citation else 'Documented fact [source](https://example.org/).')
            return dict(action='search',text='actual query',assistant_message=dict(role='assistant',content='',
                tool_calls=[dict(id='c',type='function',function=dict(name='search',arguments={'query':'actual query'}))]))
    class Web:
        async def search(self,query):
            return dict(results=[dict(title='Source',url='https://example.org/',content='Documented fact. '*10)])
        async def open_page(self,url): raise AssertionError('No extra retrieval needed')
    sample=dict(id='x',prompt='Question',original_timestamp='2025',date_policy='Original date')
    outcome=asyncio.run(c.trajectory(sample,Model(),Web(),tmp_path,8))
    assert outcome['verdict']==('needs_verification' if bad_span or missing_citation else 'keep')
    candidate=json.loads((tmp_path/'candidate.json').read_text())
    assert bool(candidate['citation_validation_errors'])==missing_citation
    assert outcome['search_count']==1 and outcome['pages']==1
    assert not (tmp_path/'tool-01.json').exists()


def test_unshown_cached_content_never_grounds_answer():
    assert c.delivered_pages({'results':[{'title':'Source','url':'https://example.org/','snippet':'Short snippet'}]})=={}


def test_prior_native_search_replayed_without_new_paid_query(tmp_path):
    prior=tmp_path/'prior'
    call=dict(role='assistant',content='',tool_calls=[dict(id='original-call',type='function',
        function=dict(name='search',arguments={'query':'original real query'}))])
    c.atomic(prior/'records/x/trajectory.json',[dict(role='user',content='Question'),call])
    budget=c.SearchBudget(tmp_path/'campaign')
    key,_=budget.reserve('original real query','x')
    budget.complete(key,b'{}',{})
    class Model:
        manifest={'reuse_root':str(prior)}
        async def ask(self,messages,schema,tools,directory,stage):
            if stage=='review':
                return dict(verdict='keep',reason='Supported',evidence=[dict(url='https://example.org/',quote='Documented fact',claim='Documented fact')])
            assert stage=='generate-01'
            assert messages[2]==call
            assert messages[3]['tool_call_id']=='original-call'
            return dict(action='final',text='Documented fact [source](https://example.org/).')
    class Web:
        async def search(self,query,owner):
            assert query=='original real query' and owner=='x'
            return dict(results=[dict(title='Source',url='https://example.org/',content='Documented fact. '*10)])
    web=Web()
    web.budget=budget
    sample=dict(id='x',prompt='Question',original_timestamp='2025',date_policy='Original date')
    result=asyncio.run(c.trajectory(sample,Model(),web,tmp_path/'new',8))
    assert result['verdict']=='keep'
    assert budget.db.execute('SELECT COUNT(*) FROM searches').fetchone()[0]==1
    assert (tmp_path/'new/replayed-search.json').exists()
