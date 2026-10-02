import copy
import json
import random

import jsonschema
import pytest

from dfm12 import multilingual_tool_dialogue as native
from dfm12.io import load
from dfm12.multilingual_references import tool_scenario
from dfm12.multilingual_tasks import assemble, request, spec_for


def spec(domain=0,subtype='single'):
    return native.configure(dict(contract_version=4,language='English',language_code='en',
        family='tool-dialogue',slot=domain,variant=0,cohort='cpu-native-v4',
        audience='adult beginner',tone='concise practical',subtype=subtype,
        scenario=tool_scenario(domain,random.Random(42))))


def generated(subtype):
    if subtype=='clarify':
        return dict(user='Please look up the supplied record.',
                    clarification='Please provide the missing lookup field.',
                    clarification_reply='Here is the requested information.',
                    final='The lookup found availability; no booking was made.')
    if subtype=='no-call':
        return dict(user='How might such a service work in a hypothetical example?',
                    explanation='A service could look up availability before a separately requested action.')
    return dict(user='Please perform the lookup and the action using the supplied data.' if subtype=='multi'
                else 'Please look up the supplied record and explain the result.',
                final='The lookup failed temporarily.' if subtype=='error' else
                'The mock action succeeded.' if subtype=='multi' else
                'The lookup found availability; no action was taken.')


@pytest.mark.parametrize('domain',range(5))
@pytest.mark.parametrize('subtype',native.SUBTYPES)
def test_all_domains_and_subtypes_have_native_bound_trajectories(domain,subtype):
    case=spec(domain,subtype)
    row=assemble(case,generated(subtype))
    calls=[c for m in row['messages'] for c in m.get('tool_calls',[])]
    results=[m for m in row['messages'] if m['role']=='tool']
    expected={'no-call':0,'single':1,'clarify':1,'multi':2,'error':1,'retry':2}[subtype]
    assert len(calls)==len(results)==expected
    assert all(isinstance(c['function']['arguments'],dict) for c in calls)
    assert [c['id'] for c in calls]==[r['tool_call_id'] for r in results]
    assert all(c['type']=='function' for c in row['tools'])
    if subtype=='error':
        assert json.loads(results[-1]['content'])==native.ERROR
    if subtype=='retry':
        assert calls[0]['function']==calls[1]['function']
        assert json.loads(results[0]['content'])==native.ERROR
        assert json.loads(results[1]['content'])==case['scenario']['lookup_result']
    if subtype!='multi':
        assert all('action' not in k for k in case['scenario'])
        assert all(c['function']['name']==case['scenario']['lookup_name'] for c in calls)
    if subtype!='no-call':
        assert row['messages'][-1]['content']==generated(subtype)['final']
        evidence=row['provenance']['tool_dialogue_grounding']['final_evidence']
        assert evidence['result']==json.loads(results[-1]['content'])
        assert evidence['action_executed']==(subtype=='multi')
        assert evidence['semantic_status']=='pending_review'
    assert row['provenance']['tool_dialogue_grounding']['semantic_review_required']
    assert row['native_speaker_review']=='pending' and row['pilot_only']


@pytest.mark.parametrize('subtype',native.SUBTYPES)
def test_schema_only_requests_applicable_fields(subtype):
    case=spec(subtype=subtype)
    payload=request(case)
    schema=payload['response_format']['json_schema']['schema']
    assert set(schema['required'])==set(generated(subtype))
    assert schema['additionalProperties'] is False
    assert payload['chat_template_kwargs']=={'enable_thinking':False}
    view=json.loads(payload['messages'][1]['content'])
    assert 'tool_dialogue_source_scenario' not in view
    if subtype!='multi':
        assert 'action_result' not in view['scenario']
    with pytest.raises(jsonschema.ValidationError):
        assemble(case,dict(generated(subtype),unexpected_field='I booked it.'))


def test_naturalized_swedish_date_service_not_blind_literal_failure():
    case=spec(1)
    case.update(language='Swedish',language_code='sv')
    row=assemble(case,{'user':'Kan du söka efter en rutinkonsultation på det angivna datumet?',
                       'final':'Det finns en ledig tid. Ingen bokning har gjorts.'})
    assert 'rutinkonsultation' in row['messages'][0]['content']
    assert 'routine_consultation' in row['messages'][0]['content']
    assert row['messages'][1]['tool_calls'][0]['function']['arguments']==case['scenario']['arguments']
    assert 'booking_id' not in row['messages'][-1]['content']
    assert row['provenance']['tool_dialogue_grounding']['argument_sources']


def test_clarification_missing_value_enters_only_actual_reply():
    case=spec(1,'clarify')
    field=case['scenario']['missing_field']; value=case['scenario']['arguments'][field]
    row=assemble(case,generated('clarify'))
    assert value not in row['messages'][0]['content']
    assert value in row['messages'][2]['content']
    assert row['messages'][3]['tool_calls'][0]['function']['arguments'][field]==value
    bad=generated('clarify'); bad['user']+=' '+value
    with pytest.raises(ValueError,match='already present'):
        assemble(case,bad)


@pytest.mark.parametrize('domain',range(5))
def test_action_ids_cannot_be_invented_or_reclassified_as_user_data(domain):
    case=spec(domain,'multi')
    sources=native.action_sources(case['scenario'])
    field=next(k for k,v in sources.items() if v['kind']=='lookup_result')
    case['scenario']['action_arguments'][field]='invented-id'
    with pytest.raises(ValueError,match='identifier does not match'):
        assemble(case,generated('multi'))


def test_schema_quantity_type_minimum_and_external_refs_fail_closed():
    case=spec(3,'multi')
    for value in (0,'2',True,float('nan')):
        bad=copy.deepcopy(case); bad['scenario']['action_arguments']['quantity']=value
        with pytest.raises((ValueError,TypeError)):
            assemble(bad,generated('multi'))
    bad=spec(subtype='no-call')
    bad['scenario']['tools'][0]['function']['parameters']={'$ref':'https://invalid.example/schema'}
    with pytest.raises(ValueError,match='External'):
        assemble(bad,generated('no-call'))


def test_no_action_success_after_error_and_no_success_facts_in_error_prompt():
    case=spec(1,'error')
    assert case['scenario']['lookup_result']==native.ERROR
    payload=request(case)
    assert 'booking_id' not in payload['messages'][1]['content']
    row=assemble(case,generated('error'))
    assert row['messages'][-1]['content']==generated('error')['final']
    assert row['provenance']['tool_dialogue_grounding']['final_evidence']['result']==native.ERROR
    bad=spec(1,'multi'); bad['scenario']['lookup_result']=copy.deepcopy(native.ERROR)
    with pytest.raises(ValueError):
        assemble(bad,generated('multi'))


def test_result_values_and_available_quantity_cannot_be_changed():
    bad=spec(1)
    bad['scenario']['lookup_result']['date']='2099-01-01'
    with pytest.raises(ValueError,match='receipt contradicts'):
        assemble(bad,generated('single'))
    bad=spec(3,'multi')
    bad['scenario']['action_result']['quantity']+=1
    with pytest.raises(ValueError,match='receipt contradicts'):
        assemble(bad,generated('multi'))
    bad=spec(3,'multi')
    bad['scenario']['lookup_result']['available']=0
    with pytest.raises(ValueError,match='quantity exceeds'):
        assemble(bad,generated('multi'))


@pytest.mark.parametrize('key', ['user','clarification','clarification_reply'])
def test_raw_control_markers_rejected(key):
    data=generated('clarify'); data[key]+='<|tool_call>'
    with pytest.raises(ValueError,match='delimiter'):
        assemble(spec(subtype='clarify'),data)


def test_opt_in_version_and_provenance_inventory():
    from dfm12.multilingual_prepare_calibrated import IMPLEMENTATIONS
    assert 'multilingual_tool_dialogue.py' in IMPLEMENTATIONS
    seeds={}
    previous=spec_for('nb','tool-dialogue',0,0,seeds,{'contract_version':3})
    assert 'tool_dialogue_contract' not in previous
    assert set(request(previous)['response_format']['json_schema']['schema']['required'])=={
        'user','clarification','clarification_reply','final','retry','no_call'}
    future=[spec_for('nb','tool-dialogue',i,0,seeds,{'contract_version':4}) for i in range(30)]
    assert {s['subtype'] for s in future[:10]}==set(native.SUBTYPES)
    assert len({(s['scenario']['domain'],s['subtype']) for s in future})==30
    assert all(s['tool_dialogue_contract']==native.CONTRACT for s in future)
    wrong=copy.deepcopy(future[0]); wrong['contract_version']=5
    with pytest.raises(ValueError,match='contract'):
        request(wrong)


def test_localized_final_is_required_and_bound_not_automatically_approved():
    case=spec(1,'single')
    with pytest.raises(jsonschema.ValidationError):
        assemble(case,{'user':'Look up a consultation.'})
    payload=request(case)
    evidence=json.loads(payload['messages'][1]['content'])['terminal_evidence']
    assert evidence['action_executed'] is False and evidence['successful'] is True
    assert 'not JSON-only' in payload['messages'][0]['content']
    # Preserve a semantically bad candidate for the reviewer, never call it safe
    # just because the calls are valid, nor silently rewrite its claim.
    bad=generated('single'); bad['final']='I booked the appointment.'
    row=assemble(case,bad)
    assert row['messages'][-1]['content']==bad['final']
    grounding=row['provenance']['tool_dialogue_grounding']
    assert grounding['semantic_review_required'] is True
    assert grounding['final_evidence']['action_executed'] is False
    assert row['native_speaker_review']=='pending'


def test_old_json_final_draft_contract_not_silently_reinterpreted():
    case=spec(); case['tool_dialogue_contract']='native-tool-dialogue-v4'
    with pytest.raises(ValueError,match='contract'):
        request(case)


def test_cpu_prepare_pins_contract_without_authorizing_generation(tmp_path,monkeypatch):
    from dfm12 import identity_gpu,multilingual_diagnose
    from dfm12.io import write_json
    monkeypatch.setattr(identity_gpu,'training_renderer',lambda root: write_json(root/'training-template.json',{'mock':True}))
    monkeypatch.setattr(multilingual_diagnose.PromptBudget,'__init__',lambda self: None)
    monkeypatch.setattr(multilingual_diagnose.PromptBudget,'measure',lambda self,payload: 100)
    root=tmp_path/'fresh'
    assert native.prepare(root,'sv')==30
    manifest=load(root/'manifest.json')
    assert manifest['contract']==native.CONTRACT and manifest['model_outputs']==0
    assert not manifest['generation_authorized'] and not manifest['admission_authorized']
    assert 'multilingual_tool_dialogue.py' in manifest['implementation_pins']
    records=load(root/'requests.json')
    assert len({(r['spec']['scenario']['domain'],r['spec']['subtype']) for r in records})==30
    with pytest.raises(FileExistsError):
        native.prepare(root,'sv')


@pytest.fixture(scope='module')
def renderer():
    from dfm12.prepare import Renderer
    return Renderer(load('data/sampled_dfm11/metadata.json')['tokenizer_info'],4096)


@pytest.mark.parametrize('subtype',native.SUBTYPES)
def test_actual_gemma_template_native_calls_and_final_only_token_boundaries(renderer,subtype):
    from dfm12.multilingual_pilot import student_validate
    from scripts.tokenize_chat_template import examples_from_messages,render,tokenize_example
    row=assemble(spec(1,subtype),generated(subtype))
    assert student_validate(renderer,row)['rendered_training_tokens']>0
    examples=list(examples_from_messages(row['messages'],row['tools']))
    assert len(examples)==sum(m['role']=='assistant' for m in row['messages'])
    full=render(renderer.template,row['messages'],row['tools'],False,False)
    calls=sum(len(m.get('tool_calls',[])) for m in row['messages'])
    assert full.count('<|tool_call>')==calls
    assert full.count('<|tool_response>')==calls
    assert '<|tool>declaration:lookup_appointment_slot' in full
    assert 'call:lookup_appointment_slot{{' not in full
    for example in examples:
        encoded=tokenize_example(renderer.tokenizer,renderer.template,example,False)
        assert encoded is not None
        prefix,target=encoded
        rendered=render(renderer.template,example.prompt_messages+[example.assistant_message],
                        example.tools,False,False)
        assert renderer.tokenizer.encode(rendered,add_special_tokens=False).ids==prefix+target
        assert sum(map(len,encoded))<=4096
    final=examples[-1]
    assert final.assistant_message['content']==row['messages'][-1]['content']
    # All historical assistant/tool turns reside in the masked prompt; only the
    # final assistant continuation is the response target in this example.
    prefix,target=tokenize_example(renderer.tokenizer,renderer.template,final,False)
    labels=[-100]*len(prefix)+target
    assert labels[:len(prefix)]==[-100]*len(prefix)
    assert labels[len(prefix):]==target
    if calls:
        assert any(m['role']=='tool' for m in final.prompt_messages)
