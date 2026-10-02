import copy
import os
from pathlib import Path

import pytest

from dfm12.io import file_hash, load, write_json
from scripts import evaluate_dfm12_identity_compositions as adapter


def test_pinned_real_holdout_ingestion_does_not_modify_source():
    before = file_hash(adapter.HOLDOUT/'manifest.json')
    cases,rubric,assets,pins = adapter.load_holdout(adapter.HOLDOUT)
    assert len(cases)==40 and sum(len(c['users']) for c in cases)==80
    assert {c['language'] for c in cases}=={'da','en'}
    assert all(c['expected_targets']==c['criteria'] for c in cases)
    assert all(len(c['requests'])==2 and c['training_allowed'] is False for c in cases)
    assert rubric['scoring'].startswith('Semantic')
    assert set(assets)=={'template','tokenizer'} and len(pins)>10
    assert file_hash(adapter.HOLDOUT/'manifest.json')==before
    assert 'expected_targets' not in load(adapter.HOLDOUT/'cases.json')[0]


def test_manifest_drift_fails_before_ingestion(tmp_path):
    write_json(tmp_path/'manifest.json',{})
    with pytest.raises(ValueError,match='manifest changed'):
        adapter.load_holdout(tmp_path)


def test_case_and_rubric_drift_fails(tmp_path,monkeypatch):
    manifest=load(adapter.HOLDOUT/'manifest.json')
    write_json(tmp_path/'manifest.json',manifest)
    for name in ('cases.json','rubric.json'):
        (tmp_path/name).write_bytes((adapter.HOLDOUT/name).read_bytes())
    monkeypatch.setattr(adapter,'HOLDOUT_SHA',file_hash(tmp_path/'manifest.json'))
    write_json(tmp_path/'rubric.json',{'scoring':'pass all'})
    with pytest.raises(ValueError,match='evidence drift'):
        adapter.load_holdout(tmp_path)


def test_no_criteria_or_gold_in_generated_followup():
    case=dict(id='a',suite='sealed_identity_compositions',language='en',family='f',
              users=['question1','question2'],expected_targets=['SECRET1','SECRET2'],
              requests=[['name'],['name']])
    seen=[]
    def generate(messages):
        seen.append(copy.deepcopy(messages))
        return dict(response=f'actual{len(seen)}')
    result=adapter.evaluation.historical.run_conversation(case,generate)
    assert seen==[[{'role':'user','content':'question1'}],
                  [{'role':'user','content':'question1'},
                   {'role':'assistant','content':'actual1'},
                   {'role':'user','content':'question2'}]]
    assert result['turns'][1]['expected_target']=='SECRET2'


def release_files(tmp_path):
    training=tmp_path/'training.json'
    release=tmp_path/'release.json'
    checkpoint=tmp_path/'checkpoint'
    write_json(training,dict(step=2897261,output=str(checkpoint),evaluation_export='EMA_ONLY'))
    write_json(release,dict(campaign='identity-composition-evaluation',step=2897261,
                           all_owned_gpu_work_released=True,owned_pids=[2**30]))
    return checkpoint,training,release


def test_release_binds_completed_step_and_dead_owned_work(tmp_path):
    checkpoint,training,release=release_files(tmp_path)
    assert len(adapter.verify_release(checkpoint,training,release))==2
    row=load(release)
    row['owned_pids']=[os.getpid()]
    write_json(release,row)
    with pytest.raises(ValueError,match='still alive'):
        adapter.verify_release(checkpoint,training,release)


@pytest.mark.parametrize('field,value', [('step',2887261),('evaluation_export','non-EMA'),('output','/other')])
def test_wrong_training_completion_rejected(tmp_path,field,value):
    checkpoint,training,release=release_files(tmp_path)
    row=load(training); row[field]=value; write_json(training,row)
    with pytest.raises(ValueError,match='training receipt'):
        adapter.verify_release(checkpoint,training,release)


@pytest.mark.parametrize('field,value', [('step',2887261),('all_owned_gpu_work_released',False),
                                      ('owned_pids',[]),('owned_pids',['123']),('campaign','other')])
def test_missing_release_authority_rejected(tmp_path,field,value):
    checkpoint,training,release=release_files(tmp_path)
    row=load(release); row[field]=value; write_json(release,row)
    with pytest.raises(ValueError,match='release receipt'):
        adapter.verify_release(checkpoint,training,release)


def test_memory_policy_caps_below_half_and_fails_closed():
    report=dict(ema=True,**adapter.memory.CO_RESIDENT_POLICY)
    snapshot=dict(total_mib=183359,free_mib=100000,own_used_mib=80000)
    ceiling=adapter.memory.check_co_resident(report,snapshot,loading=True)
    assert ceiling <= snapshot['total_mib']*.5
    with pytest.raises(RuntimeError,match='footprint'):
        adapter.memory.check_co_resident(report,dict(snapshot,own_used_mib=ceiling+1))
    with pytest.raises(ValueError,match='Unsafe'):
        adapter.memory.check_co_resident(report,dict(snapshot,total_mib=100000))
    with pytest.raises(RuntimeError,match='headroom'):
        adapter.memory.check_co_resident(report,dict(snapshot,free_mib=90000),loading=True)


def test_smaller_memory_budget_preserves_reserves():
    assert adapter.memory_policy(80) == adapter.memory.CO_RESIDENT_POLICY
    policy = adapter.memory_policy(64)
    assert policy['required_free_mib'] == 76 * 1024
    report = dict(ema=True, **policy)
    snapshot = dict(total_mib=183359, free_mib=90000, own_used_mib=0)
    assert adapter.memory.check_co_resident(report,snapshot,loading=True) == 68 * 1024
    with pytest.raises(RuntimeError,match='headroom'):
        adapter.memory.check_co_resident(report,dict(snapshot,free_mib=75000),loading=True)
    for value in (0,15,81,100):
        with pytest.raises(ValueError,match='Allocator budget'):
            adapter.memory_policy(value)


def test_summary_never_lexical_or_semantic_pass(tmp_path):
    turn=dict(user='q',response='a',expected_target='criterion',turn=1,
              finish_reason='length',generated_token_count=512,truncated=True,
              heuristics={'anchor_recall':1})
    report=dict(status='complete_with_length_stops',runs=[dict(conversations=[
        dict(id='x',language='en',turns=[turn])])])
    adapter.save(tmp_path,report)
    summary=load(tmp_path/'summary.json')
    assert summary['semantic_pass'] is None and summary['training_allowed'] is False
    assert summary['export_authorized'] is False and summary['length_stops']==1
    assert report['identity_positive'] is None and 'heuristics' not in turn


def test_cpu_preflight_never_probes_gpu_or_loads_checkpoint(tmp_path,monkeypatch):
    def forbidden(*args,**kwargs):
        raise AssertionError('GPU/checkpoint runtime path called during CPU preflight')
    monkeypatch.setattr(adapter.memory,'real_memory',forbidden)
    monkeypatch.setattr(adapter.evaluation,'ema_source',forbidden)
    monkeypatch.setattr(adapter.evaluation,'run_phase',forbidden)
    monkeypatch.setattr(adapter.evaluation,'checkpoint_pins',forbidden)
    monkeypatch.setattr(adapter,'cpu_prompt_preflight',lambda *args: {})
    output=tmp_path/'preflight'
    assert adapter.main(['--preflight-only','--output',str(output)])==0
    report=load(output/'responses.json')
    assert report['ema'] is True and report['non_ema'] is False
    assert report['runs'][0]['tag']=='step_2897261'
    assert report['runs'][0]['conversations']==[]
    assert not (output/'completion.json').exists()


def test_runtime_requires_release_before_any_preparation(tmp_path,monkeypatch):
    monkeypatch.setattr(adapter,'verify_helpers',lambda: pytest.fail('must reject arguments first'))
    with pytest.raises(SystemExit):
        adapter.main(['--output',str(tmp_path/'run')])


@pytest.mark.parametrize('flag,value',[('--max-new-tokens','513'),('--max-seconds','7201')])
def test_limits_are_not_overridable(tmp_path,flag,value):
    with pytest.raises(SystemExit):
        adapter.main(['--preflight-only','--output',str(tmp_path/'run'),flag,value])


def test_prompt_budget_counts_mapping_input_ids_not_mapping_keys(tmp_path,monkeypatch):
    import transformers
    class Tokenizer:
        def apply_chat_template(self,*args,**kwargs):
            return {'input_ids':list(range(100)), 'attention_mask':[1]*100}
    monkeypatch.setattr(transformers,'PreTrainedTokenizerFast',lambda **kwargs: Tokenizer())
    template=tmp_path/'template'; template.write_text('unused')
    assets={'tokenizer':{'path':'unused'},'template':{'path':str(template)}}
    result=adapter.cpu_prompt_preflight([{'id':'x','users':['q1','q2']}],assets,512)
    assert result['x']['conservative_total_tokens']==1156
