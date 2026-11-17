import asyncio
import json
from pathlib import Path
import pytest
from scripts.dfm16_staged_stories import (LANGUAGES,TASKS,TEMPLATES,StagedGenerate,
    initial_request,band,count,edit_request,replace,findings,payload,assembly_request)
from scripts.dfm16_story_calibration import sha
from scripts.dfm16_experiment_transport import Budget
from scripts.dfm16_language_qualification import policy_vote,supplementary_needed
from scripts.dfm16_staged_audit import checks,StagedAudit


def row(lang='en',task='rewrite'):
    text='Mia opened the red door. Leo stayed in the garden.'
    return dict(id='test',audit_id='test',language=lang,task=task,variant=0,
        source=dict(text=text,language=lang,review='clear',reviewer='assistant-manual',
                    facts=['Mia opened the door'],sha256=sha(text),narration='past',translation_of='seed'),
        slots_reviewed=True,topic='friendship',question='Who opened the door?',
        reference_answer='Mia',answer_support='Mia opened',changes=['add a description','add a description'])


@pytest.mark.parametrize('lang',LANGUAGES)
@pytest.mark.parametrize('task',TASKS)
def test_native_templates_source_and_variants(lang,task):
    r=row(lang,task)
    texts=[]
    for i in range(3):
        r['variant']=i;text=initial_request(r);texts.append(text)
        assert ('\n\n'+r['source']['text'] in text)==(task in ('summary','qa','rewrite'))
    assert len(set(texts))==3


def test_source_preconditions():
    r=row();r['source']['narration']='present'
    with pytest.raises(ValueError,match='past-tense'):initial_request(r)
    r=row();r['source']['language']='da'
    with pytest.raises(ValueError,match='target language'):initial_request(r)
    r=row(task='qa');r['answer_support']='not in source'
    with pytest.raises(ValueError):initial_request(r)
    r=row();r['source']['text']='changed'
    with pytest.raises(ValueError,match='changed'):initial_request(r)


def test_unicode_and_sentence_boundary():
    assert count('किताब अच्छी है।','hi')==3
    assert count('赤い 鍵。\n猫','ja')==5
    assert count('e\u0301','ja')==2  # documented Unicode code points, not graphemes
    assert not findings('Dr. Lee said "yes..."', 'en') # sentence boundaries semantic
    assert band('one two three four five','en')==(4,6)


def test_plain_content_envelopes_and_unambiguous_paragraph_limits():
    for text in ('{\n "text": "物語"\n}', '["a story"]', '  ```text\nstory\n```'):
        assert any('plain prose' in issue for issue in findings(text, 'ja'))
    assert not findings('The sign read {hello}.', 'en')
    request, _ = edit_request(row(task='revision'), ['one two', 'three four', 'five six'], 0)
    visible = assembly_request(request, 'en')
    assert 'The edited paragraph must contain' in visible
    assert 'Its length' not in visible
    request, _ = edit_request(row('hi', 'revision'), ['एक दो', 'तीन चार', 'पाँच छह'], 0)
    assert 'बदले गए अनुच्छेद की लंबाई' in assembly_request(request, 'hi')


def test_exact_assembly_and_undo_budget():
    r=row(task='revision')
    original=['one two three','four five six','seven eight nine']
    parts=replace(original,0,'one two three four')
    assert parts[1:]==original[1:]
    req,limits=edit_request(r,parts,2,original)
    assert limits==(2,5)
    assert 'Return the complete story' in assembly_request(req,'en')
    final=replace(parts,2,'seven eight')
    undo=[original[0],final[1],final[2]]
    assert undo[0]==original[0] and undo[1:]==final[1:]
    with pytest.raises(ValueError):replace(parts,0,'a\n\nb')


def test_odin_protocol_and_no_self_review():
    p=payload('odin-2-large',[])
    assert p['max_completion_tokens']==6144 and p['temperature']==.3
    assert p['reasoning_effort']=='none' and p['include_reasoning'] is False
    assert 'max_tokens' not in p and 'response_format' not in p
    with pytest.raises(ValueError):policy_vote({'flash':'accept'},'flash','flash')
    assert policy_vote({'flash':'accept','odin':'reject','qwen27b':'accept'},'flash','both')=='reject'
    assert policy_vote({'odin':'accept'},'flash','either')=='unresolved'


def test_shared_rate_budget_restart_and_boundary(tmp_path):
    one=Budget(tmp_path/'budget.sqlite');two=Budget(tmp_path/'budget.sqlite')
    for n in range(100):assert (one if n%2 else two).reserve(100)[0] is not None
    assert two.reserve(159.999)[0] is None
    assert one.reserve(160)[0] is not None
    assert Budget(tmp_path/'budget.sqlite').summary()['actual_send_reservations']==101
    with pytest.raises(ValueError):Budget(tmp_path/'budget.sqlite',101)


def test_stage_resume_integrity_and_ambiguous_dispatch(tmp_path):
    a=StagedGenerate(tmp_path,tmp_path/'out','http://unused');a.model='test';r=row()
    assert a.begin(r,'initial',0,{'x':1}) is None
    assert a.begin(r,'initial',0,{'x':1})['error']=='interrupted_dispatch_unresolved'
    a.finish_stage(r,'initial',0,{'x':1},{'response':{'value':1}})
    assert a.begin(r,'initial',0,{'x':1})['response']=={'value':1}
    with pytest.raises(ValueError):a.begin(r,'initial',0,{'x':2})


class Offload:
    async def call(self,fn,*args):return fn(*args)


class HTTP:
    def __init__(self,responses):self.responses=iter(responses);self.calls=0
    async def post(self,request):
        self.calls+=1
        v=next(self.responses)
        if isinstance(v,Exception):raise v
        return dict(choices=[dict(finish_reason='stop',message=dict(content=v))],usage={'prompt_tokens':1})


def test_bounded_objective_correction_and_replay(tmp_path):
    async def run():
        a=StagedGenerate(tmp_path,tmp_path/'out','http://unused');a.model='test';r=row()
        http=HTTP(['short','one two three four five six seven eight nine ten'])
        args=(r,'initial',[{'role':'user','content':'test'}],(8,12),1,http,Offload(),Offload())
        result=await a.generate_stage(*args)
        assert result['corrected'] and len(result['attempts'])==2 and result['attempts'][0]['findings']
        again=await a.generate_stage(*args)
        assert again['text']==result['text'] and http.calls==2
    asyncio.run(run())


def test_scoped_evidence_and_plain_verdict(tmp_path):
    r=row();r.update(background_seed='different provenance',messages=[dict(role='user',content=initial_request(r)),dict(role='assistant',content='answer')])
    c=list(checks(r))
    assert c[0]['evidence']['target']['field']=='authoritative_source'
    assert c[0]['evidence']['background_seed'] != c[0]['evidence']['authoritative_source']
    adapter=StagedAudit(tmp_path,tmp_path/'out','http://unused');adapter.model='odin-2-large'
    p=adapter.prepare(c[0]);assert p['max_completion_tokens']==32
    with pytest.raises(ValueError):adapter.parse_review({'choices':[{'finish_reason':'stop','message':{'content':'accept.'}}]})


def test_supplementary_blind_counts_only():
    labels=[dict(id=str(i),label='clear' if i<750 else 'bad') for i in range(800)]
    assert supplementary_needed(labels)
    labels[0]['decision']='accept'
    with pytest.raises(ValueError):supplementary_needed(labels)


def test_frozen_controls_complete_and_scoped():
    from scripts.dfm16_staged_controls import controls
    from collections import Counter
    bank=list(controls())
    assert len(bank)==320 and len({r['id'] for r in bank})==320
    assert Counter(r['language'] for r in bank)==Counter({l:80 for l in LANGUAGES})
    assert len({r['pair'] for r in bank})==160
    for r in bank:
        assert len(r['messages'])%2==0
        for c in checks(r):
            p=StagedAudit(Path('.'),Path('/tmp/unused'),'http://unused').prepare(c)
            assert 'provisional' not in p['messages'][1]['content']
            assert '"label"' not in p['messages'][1]['content']


def test_shared_budget_concurrent_connections(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    a=Budget(tmp_path/'shared.sqlite')
    b=Budget(tmp_path/'shared.sqlite')
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda i:(a if i%2 else b).reserve(100),range(200)))
    assert sum(identifier is not None for identifier,_ in results)==100


def test_context_overflow_no_retry_or_repair(tmp_path):
    import httpx
    async def run():
        a=StagedGenerate(tmp_path,tmp_path/'out','http://unused');a.model='test'
        request=httpx.Request('POST','http://unused')
        response=httpx.Response(400,request=request)
        http=HTTP([httpx.HTTPStatusError('context overflow',request=request,response=response)])
        result=await a.generate_stage(row(),'initial',[],None,None,http,Offload(),Offload())
        assert result['status']=='unresolved' and http.calls==1
        assert len(result['attempts'])==1
    asyncio.run(run())


def test_one_correction_budget(tmp_path):
    async def run():
        a=StagedGenerate(tmp_path,tmp_path/'out','http://unused');a.model='test'
        http=HTTP(['too short'])
        result=await a.generate_stage(row(),'ending',[],(8,12),1,http,Offload(),Offload(),allow_correction=False)
        assert result['status']=='deterministic_failure' and http.calls==1
    asyncio.run(run())


def test_generator_thresholds_and_no_pooling():
    from scripts.dfm16_language_qualification import select_generator
    records=[]
    for arm in ('legacy','flash','qwen27b','odin'):
        for i in range(20):
            records.append(dict(id=f'{arm}-{i}',family=str(i),language='en',task=TASKS[i//4],arm=arm,
                label='bad' if arm=='legacy' or i%4==0 else 'clear',deterministic_pass=True,cost=1,seconds=1))
    assert select_generator(records)=='flash' # Exploratory threshold is now 10/20.
    for r in records:
        if r['arm']!='legacy':r['label']='clear' if int(r['family'])<9 else 'bad'
    assert select_generator(records) is None
    for r in records:
        if r['arm']=='flash' and r['family']=='9':r['label']='clear'
    assert select_generator(records)=='flash'
    records[0]['language']='hi'
    with pytest.raises(ValueError):select_generator(records)


def test_reported_reasoning_tokens_do_not_reject_usable_content():
    from scripts.dfm16_staged_stories import decode
    body={'choices':[{'finish_reason':'stop','message':{'content':'accept'}}],
          'usage':{'completion_tokens':2,'completion_tokens_details':{'reasoning_tokens':1}}}
    assert decode(body)=='accept'
    assert StagedAudit.parse_review(body)['decision']=='accept'


def test_precision_checks_keep_context_without_leaking_labels():
    from scripts.dfm16_staged_precision import supplemental_checks,PrecisionAudit
    r=row(task='rewrite')
    r.update(label='bad',note='secret manual defect',messages=[
        {'role':'user','content':'Change the past to present. Mia opens the door.'},
        {'role':'assistant','content':'Mia opens the door.\n\nLeo waits.'}])
    items=list(supplemental_checks(r))
    assert len(items)==5
    for c in items:
        assert 'secret manual defect' not in json.dumps(c)
        assert c['evidence']['authoritative_source']==r['source']['text']
        assert c['parent_id']==r['id']
    request=next(c for c in items if c['criterion']=='request_preconditions')
    assert request['evidence']['target_text']==r['messages'][0]['content']
    grammar=[c for c in items if c['criterion']=='paragraph_grammar']
    assert [c['evidence']['target_text'] for c in grammar]==['Mia opens the door.','Leo waits.']


def test_native_review_spans_preserve_reference_context():
    from scripts.dfm16_staged_native_precision import native_checks,NativePrecisionAudit
    r=row('hi','summary')
    r['messages']=[{'role':'user','content':'सारांश लिखें।'},
                   {'role':'assistant','content':'मीरा आई। वह रुकी।'}]
    items=list(native_checks(r))
    assert len(items)==4
    assert len({c['id'] for c in items})==4
    for c in items:
        assert c['evidence']['conversation']==r['messages']
        assert c['evidence']['authoritative_source']==r['source']['text']


def test_validation_strict_upper_bound_and_task_hold():
    from scripts.dfm16_language_qualification import validation_report
    records=[]
    for i in range(800):
        records.append(dict(id=str(i),family=str(i),language='en',task=TASKS[i//160],cohort='validation',
            label='bad' if i%4==0 else 'clear',decision='reject' if i%4==0 else 'accept',deterministic_pass=True))
    assert validation_report(records)['qualified']
    # Three false accepts in one task: pooled upper bound can pass, task 7.5% fails.
    for i in (0,4,8):records[i]['decision']='accept'
    report=validation_report(records)
    assert report['demonstrated'] and not report['qualified']
    records.append(dict(records[0]))
    with pytest.raises(ValueError):validation_report(records)


def test_revision_full_conversation_assembly_and_undo(tmp_path):
    async def run():
        a=StagedGenerate(tmp_path,tmp_path/'out','http://unused');a.model='test'
        r=row(task='revision')
        # Nine to thirteen words, three separate paragraphs.
        initial='Mia found something.\n\nLeo watched quietly.\n\nBoth went home.'
        http=HTTP([initial,'Young Mia found something.','Both walked home.'])
        results=[]
        a.commit=lambda item,result:results.append(result)
        await a.process(('job',r),http,Offload(),Offload())
        result=results[0]
        assert result['status']=='generated'
        messages=result['candidate']['messages']
        assert len(messages)==8
        first=messages[1]['content'].split('\n\n')
        edited=messages[3]['content'].split('\n\n')
        ending=messages[5]['content'].split('\n\n')
        undo=messages[7]['content'].split('\n\n')
        assert edited[1:]==first[1:]
        assert ending[:2]==edited[:2]
        assert undo[0]==first[0] and undo[1:]==ending[1:]
        assert http.calls==3
        assert 'complete story' in messages[2]['content']
    asyncio.run(run())


def test_review_invalid_retry_kept_and_reused(tmp_path):
    async def run():
        a=StagedAudit(tmp_path,tmp_path/'out','http://unused');a.model='test'
        r=dict(id='review',audit_id='review',criterion='answer_language',evidence={'target':'text'})
        http=HTTP(['accept.','reject'])
        results=[];a.commit=lambda item,result:results.append(result)
        await a.process(('job',r),http,Offload(),Offload())
        assert results[0]['review']['decision']=='reject' and len(results[0]['attempts'])==2
        await a.process(('job',r),http,Offload(),Offload())
        assert http.calls==2
    asyncio.run(run())


def test_runtime_receipt_resume_and_stage_corruption(tmp_path, monkeypatch):
    # This receipt test does not render/tokenize; avoid depending on production data.
    import scripts.prepare_dfm16_stories_v2 as preparation
    original_load = preparation.load
    monkeypatch.setattr(preparation, "load", lambda path: {"tokenizer_info": {}}
                        if str(path) == "data/dfm15/native-reasoning-v2/sampled_dfm15/metadata.json"
                        else original_load(path))
    import httpx
    from audit_pipeline.runtime import run
    from scripts.queue_dfm16_stories_qwen import prepare_stage
    from dfm12.io import load
    async def execute():
        stage=tmp_path/'input';out=tmp_path/'output'
        prepare_stage(stage,[row()],'staged_test')
        sent=[]
        def handler(request):
            if request.method=='GET':return httpx.Response(200,json={'data':[{'id':'test'}]})
            sent.append(request)
            return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'Mia opens the red door. Leo stays in the garden.'}}]})
        for _ in range(2):
            a=StagedGenerate(stage,out,'http://127.0.0.1:9999/v1');a.model='test'
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
            await run(a,a.endpoint,2,client=client,signals=False,prefetch=1)
        assert len(sent)==1
        job=load(stage/'manifest.json')['chunks'][0]
        a.verify_receipt(job,out/job['job_id'])
        path=next((out/'stages').rglob('initial-0.json'))
        path.write_text(path.read_text()+' ')
        with pytest.raises(ValueError,match='stage artifact'):a.verify_receipt(job,out/job['job_id'])
    asyncio.run(execute())


def test_controls_have_no_repeated_whole_examples():
    from scripts.dfm16_staged_controls import controls
    bank=list(controls())
    for lang in LANGUAGES:
        assert len({sha([r['source'],r['messages']]) for r in bank if r['language']==lang})==80


@pytest.mark.parametrize('task',['creative','revision'])
def test_hindi_nominative_slots_do_not_require_hidden_case_inflection(task):
    r=row('hi',task);r['topic']='वर्चुअल जिम में अभ्यास करने वाला एक लड़का'
    for variant in range(3):
        r['variant']=variant
        rendered=initial_request(r)
        assert rendered.startswith('विषय: '+r['topic']+'\n')
        assert 'लड़का के' not in rendered and 'लड़का पर' not in rendered


def test_legacy_arm_uses_only_matched_constraints(tmp_path):
    from scripts.dfm16_staged_experiment import LegacyGenerate
    a=LegacyGenerate(tmp_path,tmp_path/'out','http://unused');a.model='test'
    for task in TASKS:
        r=row(task=task)
        request=a.prepare(r)
        spec=json.loads(request['messages'][1]['content'])['sampled_constraints']
        assert not set(spec)&{'audience','genre','tone','viewpoint','ending','setting','question_type','summary_constraint'}
        assert request['temperature']==.3 and request['max_tokens']==6144
        if task=='rewrite':assert spec['operation'].startswith('change past narration to present')
        if task=='revision':assert spec['paragraph_changes']==r['changes']
