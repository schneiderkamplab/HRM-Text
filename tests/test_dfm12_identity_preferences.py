import copy
import json
from pathlib import Path

import pytest

from dfm12.io import file_hash, write_json
from scripts import prepare_dfm12_identity_preferences as corpus
from scripts import queue_dfm12_identity_ema_samples as sampling


def example():
    case = dict(id='source-case', suite='heldout', family='origin', language='en')
    prompt = [{'role':'user','content':'First question'}, {'role':'assistant','content':'Wrong past answer'},
              {'role':'user','content':'Explain the origin'}]
    turn = dict(prompt_messages=prompt, user=prompt[-1]['content'], response='Wrong ancestry',
                turn=2, truncated=False, rendered_prompt='exact', prompt_token_ids=[1,2],
                generated_token_ids=[3,4], finish_reason='eos')
    review = dict(case=0, turn=2, verdict='wrong', reason='Contradicts source facts',
                  facts=['tokenizer'], chosen='Originally trained from scratch.')
    return case, turn, review


def test_identical_history_dpo_and_final_only_sft():
    case, turn, review = example()
    original = copy.deepcopy(turn)
    sft, dpo = corpus.make_example(case, turn, review, 'train', 'source-sha')
    assert dpo['chosen_messages'][:-1] == dpo['rejected_messages'][:-1] == turn['prompt_messages']
    assert sft['messages'][:-1] == turn['prompt_messages']
    assert sft['message_loss_mask'] == [0,0,0,1]
    assert sft['provenance']['current_use'] == 'development_identity_preferences'
    assert dpo['rejected_completion_messages'][0]['content'] == turn['response']
    assert turn == original


@pytest.mark.parametrize('failure',['system','unreviewed','identical','empty','length_positive','facts'])
def test_preference_rejects_unsafe_rows(failure):
    case, turn, review = example()
    if failure == 'system': turn['prompt_messages'].insert(0,{'role':'system','content':'Identity facts'})
    if failure == 'unreviewed': review['verdict'] = 'unreviewed'
    if failure == 'identical': review['chosen'] = turn['response']
    if failure == 'empty': review['chosen'] = ''
    if failure == 'length_positive': review['verdict']='verified_correct'; turn['truncated']=True
    if failure == 'facts': review['facts']=[]
    with pytest.raises(ValueError): corpus.make_example(case,turn,review,'train','sha')


def test_good_output_not_given_fabricated_rejection():
    case, turn, review = example(); review['verdict']='verified_correct'
    sft,pair=corpus.make_example(case,turn,review,'train','sha')
    assert pair is None and sft['messages'][-1]['content']==turn['response']


@pytest.mark.parametrize('verdict,override,expected', [
    ('wrong', None, 'factual_correction'),
    ('partial', None, 'completeness'),
    ('partial', 'precision', 'precision'),
    ('partial', 'style', 'style'),
    ('verified_correct', None, 'verified_positive'),
])
def test_preference_kind_is_filterable_without_hallucination_claim(verdict, override, expected):
    case, turn, review = example()
    review['verdict'] = verdict
    if override:
        review['preference_kind'] = override
    sft, pair = corpus.make_example(case, turn, review, 'train', 'sha')
    assert sft['preference_kind'] == sft['provenance']['preference_kind'] == expected
    if pair:
        assert pair['preference_kind'] == expected
    else:
        assert expected == 'verified_positive'


@pytest.mark.parametrize('kind', ['hallucinated', 'verified_positive'])
def test_invalid_preference_kind_fails(kind):
    case, turn, review = example()
    review['preference_kind'] = kind
    with pytest.raises(ValueError):
        corpus.make_example(case, turn, review, 'train', 'sha')


class Tokenizer:
    def apply_chat_template(self, messages, **kwargs):
        text=''.join(m['role']+':'+m['content']+';' for m in messages)
        return text+'assistant:' if kwargs['add_generation_prompt'] else text
    def encode(self,text,**kwargs): return list(text.encode())


def test_token_mask_masks_all_prior_assistant_tokens():
    tok=Tokenizer(); _,turn,_=example(); p=turn['prompt_messages']
    rendered=tok.apply_chat_template(p,add_generation_prompt=True)
    ids=tok.encode(rendered)
    result=corpus.tokenize_final(tok,p,'correct',rendered,ids)
    assert result['labels'][:len(ids)]==[-100]*len(ids)
    assert result['labels'][len(ids):]==result['input_ids'][len(ids):]
    with pytest.raises(ValueError): corpus.tokenize_final(tok,p,'correct','changed',ids)


def test_family_split_precedes_augmentation_and_keeps_languages():
    cases=[dict(id=f'{f}-{l}',family=f'family-{f}',users=[f'question-{f}-{l}'],
                language=l,suite='development_identity_preferences') for f in range(25) for l in ['da','en']]
    assignments=corpus.split_families(cases)
    assert sum(s=='validation' for s in assignments.values())==5
    for c in cases: c['split']=assignments[c['family']]
    expanded=sampling.expand_cases(cases)
    assert len(expanded)==200 and len({c['id'] for c in expanded})==200
    for c in expanded: assert c['split']==assignments[c['family']]
    assert expanded==sampling.expand_cases(cases)
    assert all('source_case_id' not in c for c in cases)


def test_family_split_refuses_duplicate_prompt_leak():
    cases=[dict(family=f'f{i}',users=[str(i)]) for i in range(5)]
    split=corpus.split_families(cases)
    val=next(c for c in cases if split[c['family']]=='validation')
    train=next(c for c in cases if split[c['family']]=='train')
    train['users']=val['users']
    with pytest.raises(ValueError): corpus.split_families(cases)


def test_top_p_cpu_support_and_seed():
    import torch
    logits=torch.tensor([[8.,1.,-2.]])
    assert sampling.nucleus_sample(logits,0,0.9).item()==0
    assert all(sampling.nucleus_sample(logits,0.7,0.9).item()==0 for _ in range(20))
    torch.manual_seed(7); a=sampling.nucleus_sample(torch.zeros(20,5),0.7,0.9)
    torch.manual_seed(7); b=sampling.nucleus_sample(torch.zeros(20,5),0.7,0.9)
    assert torch.equal(a,b)
    with pytest.raises(ValueError): sampling.nucleus_sample(logits,0.7,0)


def release_fixture(tmp_path):
    pilot=tmp_path/'pilot'; pilot.mkdir()
    spec={'created':100.,'pilot_root':str(pilot),'dependency_receipt':str(tmp_path/'handoff.json')}
    completion=pilot/'completion.json'; release=pilot/'servers-released.json'
    write_json(completion,dict(status='completed',gpu_released=True,time=110.))
    write_json(release,dict(only_owned_servers=True,time=120.))
    handoff=dict(schema='identity-ema-after-pilot-release-v1',queue_spec_sha256='spec-sha',producer='poincare',
                 purpose='second_pilot_completed_and_gpu_released',authorized=True,time=121.,pilot_root=str(pilot),
                 completion=dict(path=str(completion),sha256=file_hash(completion)),
                 release=dict(path=str(release),sha256=file_hash(release)))
    write_json(Path(spec['dependency_receipt']),handoff)
    return spec,handoff


def test_release_requires_completed_pilot_and_released_gpu(tmp_path):
    spec,handoff=release_fixture(tmp_path)
    assert sampling.released(spec,'spec-sha')[0]
    write_json(Path(spec['pilot_root'])/'completion.json',dict(status='blocked',gpu_released=False,time=110.))
    assert not sampling.released(spec,'spec-sha')[0]
    write_json(Path(spec['pilot_root'])/'completion.json',dict(status='completed',gpu_released=False,time=110.))
    assert not sampling.released(spec,'spec-sha')[0]


@pytest.mark.parametrize('field',['queue','stale','hash','purpose','authorized','pilot'])
def test_unrelated_or_stale_handoff_rejected(tmp_path,field):
    spec,handoff=release_fixture(tmp_path)
    if field=='queue': handoff['queue_spec_sha256']='other'
    if field=='stale': handoff['time']=99.
    if field=='hash': handoff['release']['sha256']='wrong'
    if field=='purpose': handoff['purpose']='audit_only_released'
    if field=='authorized': handoff['authorized']=False
    if field=='pilot': handoff['pilot_root']=str(tmp_path/'other')
    write_json(Path(spec['dependency_receipt']),handoff)
    with pytest.raises(ValueError): sampling.released(spec,'spec-sha')


def test_wait_missing_handoff_never_probes_gpu(tmp_path,monkeypatch):
    spec,_=release_fixture(tmp_path)
    Path(spec['dependency_receipt']).unlink()
    spec['max_wait_seconds']=1
    path=tmp_path/'spec.json'; write_json(path,spec)
    monkeypatch.setattr(sampling.evaluation,'gpu_status',lambda *a: pytest.fail('GPU probe before dependency'))
    monkeypatch.setattr(sampling.time,'sleep',lambda _: (_ for _ in ()).throw(InterruptedError('test ends wait')))
    with pytest.raises(InterruptedError): sampling.watch(path,file_hash(path))
    assert not (tmp_path/'launch.json').exists()
    assert json.loads((tmp_path/'watch-status.json').read_text())['ready'] is False


def test_blocked_pilot_never_probes_or_launches_gpu(tmp_path, monkeypatch):
    spec, _ = release_fixture(tmp_path)
    write_json(Path(spec['pilot_root'])/'completion.json', dict(status='blocked', gpu_released=False))
    spec['max_wait_seconds'] = 1
    path = tmp_path/'spec.json'; write_json(path, spec)
    monkeypatch.setattr(sampling.evaluation, 'gpu_status', lambda *a: pytest.fail('Blocked pilot GPU probe'))
    monkeypatch.setattr(sampling.subprocess, 'Popen', lambda *a, **k: pytest.fail('Blocked pilot launch'))
    monkeypatch.setattr(sampling.time, 'sleep', lambda _: (_ for _ in ()).throw(InterruptedError()))
    with pytest.raises(InterruptedError):
        sampling.watch(path, file_hash(path))
    assert 'blocked' in json.loads((tmp_path/'watch-status.json').read_text())['reason']


def test_review_ledger_covers_every_turn_and_precision_is_not_factual_repair():
    import yaml
    rows = yaml.safe_load((corpus.ROOT/'configs/dfm12/identity-ema-preferences-20260927-reviewed.yaml').read_text())['reviews']
    expected = {(i, t) for i in range(100) for t in range(1, 3 if i < 40 else 2)}
    assert len(rows) == 140
    assert {(r['case'], r['turn']) for r in rows} == expected
    assert next(r for r in rows if r['case'] == 98)['preference_kind'] == 'precision'


def test_default_free_memory_preserved_and_override_guarded():
    assert sampling.evaluation.required_free_mib({'ema': True}) == 104*1024
    assert sampling.evaluation.required_free_mib({'ema': False}) == 32768
    report = dict(sampling.CO_RESIDENT_POLICY, ema=True)
    assert sampling.evaluation.required_free_mib(report, 183359) == 92*1024
    for change in ({'ema': False}, {'resource_mode': 'exclusive'},
                   {'required_free_mib': 1}, {'non_torch_reserve_mib': 0},
                   {'allocator_limit_gib_per_worker': 96}):
        with pytest.raises(ValueError):
            sampling.evaluation.required_free_mib(dict(report, **change), 183359)
    with pytest.raises(ValueError):
        sampling.evaluation.required_free_mib(report, 160000)


def test_co_resident_real_headroom_and_total_process_footprint():
    report = dict(sampling.CO_RESIDENT_POLICY, ema=True)
    snapshot = dict(total_mib=183359, free_mib=96634, own_used_mib=0)
    assert sampling.check_co_resident(report, snapshot, loading=True) == 84*1024
    with pytest.raises(RuntimeError):
        sampling.check_co_resident(report, dict(snapshot, free_mib=90000), loading=True)
    with pytest.raises(RuntimeError):
        sampling.check_co_resident(report, dict(snapshot, own_used_mib=84*1024+1))
    with pytest.raises(RuntimeError):
        sampling.check_co_resident(report, dict(snapshot, free_mib=8191))


def test_real_memory_does_not_hide_audit_processes(monkeypatch):
    def query(command, **kwargs):
        return '183359, 96634\n' if '--query-gpu=memory.total,memory.free' in command else '123, 85000\n456, 30000\n'
    monkeypatch.setattr(sampling.subprocess, 'check_output', query)
    result = sampling.real_memory(7, 456)
    assert result['own_used_mib'] == 30000
    assert result['compute_memory_mib'] == {123: 85000, 456: 30000}
    assert result['free_mib'] == 96634


def test_evaluator_occupancy_override_preserves_real_pids_and_default(monkeypatch):
    from types import SimpleNamespace
    def query(command, **kwargs):
        output = '7, 96634, 100' if '--query-gpu=index,memory.free,utilization.gpu' in command else '123456789'
        return SimpleNamespace(stdout=output)
    monkeypatch.setattr(sampling.evaluation.subprocess, 'run', query)
    with pytest.raises(RuntimeError, match='occupied'):
        sampling.evaluation.gpu_status(7)
    result = sampling.evaluation.gpu_status(7, allow_occupied=True)
    assert result['free_mib'] == 96634 and result['compute_pids'] == [123456789]
    with pytest.raises(RuntimeError):
        sampling.evaluation.gpu_status(6, allow_occupied=True)
