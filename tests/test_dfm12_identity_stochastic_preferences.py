import copy
import json

import pytest
import yaml

from dfm12.io import load
from scripts import prepare_dfm12_identity_stochastic_preferences as corpus


def bindings():
    prompt = [{'role':'user','content':'Which organization?'}]
    base = dict(id='base', messages=prompt+[{'role':'assistant','content':'Danish Foundation Models.'}],
                provenance=dict(case_id='original',review=dict(case=12,facts=['organization'])))
    case = dict(source_case_id='original')
    turn = dict(turn=1,user=prompt[0]['content'],prompt_messages=prompt)
    review = dict(case=12,sample=0,turn=1,verdict='wrong',reuse_chosen=True,reason='Invented organization')
    return review,base,case,turn


def test_explicit_first_turn_reuse_records_approved_origin():
    review,base,case,turn = bindings()
    resolved = corpus.resolve_review(review,base,case,turn)
    assert resolved['chosen'] == base['messages'][-1]['content']
    assert resolved['chosen_source_id'] == 'base'
    assert 'chosen' not in review


@pytest.mark.parametrize('change', ['followup','history','question','source','positive','both','no_chosen','reason'])
def test_reuse_fails_closed_for_different_history_or_missing_review(change):
    review,base,case,turn = bindings()
    if change=='followup': turn['turn']=2
    if change=='history': turn['prompt_messages']=[{'role':'assistant','content':'other history'}]+turn['prompt_messages']
    if change=='question': turn['user']='Other question'
    if change=='source': case['source_case_id']='other'
    if change=='positive': review['verdict']='verified_correct'
    if change=='both': review['chosen']='other'
    if change=='no_chosen': review.pop('reuse_chosen')
    if change=='reason': review['reason']=''
    with pytest.raises(ValueError): corpus.resolve_review(review,base,case,turn)


def test_authored_followup_keeps_specific_correction_not_gold_substitution():
    review,base,case,turn = bindings()
    turn['turn']=2
    review.pop('reuse_chosen')
    review['chosen']='My prior organization claim was incorrect. Danish Foundation Models.'
    resolved=corpus.resolve_review(review,base,case,turn)
    assert resolved['chosen']==review['chosen']
    assert 'chosen_source_id' not in resolved


def supervised(identifier='x', kind='factual_correction', split='train', case=4):
    row=dict(id=identifier,split=split,preference_kind=kind,
             provenance=dict(turn=1,family='origin',language='da'))
    row=corpus.annotate_ambiguity(row,case)
    tokens=dict(id=identifier,split=split,preference_kind=kind,input_ids=[1,2,3],labels=[-100,-100,3],
                prompt_token_count=2,attention_mask=[1,1,1])
    return row,tokens


def test_targeted_selection_masks_ambiguity_and_deduplicates_exact_supervision():
    pairs=[supervised('a'),supervised('b'),supervised('c',case=0),supervised('d',kind='style')]
    rows=corpus.targeted_rows([r for r,t in pairs],[t for r,t in pairs])
    assert len(rows)==1 and rows[0]['source_row_ids']==['a','b']
    assert corpus.token_counts(rows)==dict(rows=1,rendered_tokens=3,target_tokens=1,max_sequence_tokens=3)
    assert not pairs[2][0]['identity_deficit_evidence_eligible']


def test_deduplication_does_not_bridge_splits():
    a,at=supervised('a'); b,bt=supervised('b',split='validation')
    with pytest.raises(ValueError): corpus.targeted_rows([a,b],[at,bt])


def test_packer_adapter_scope_is_export_only_not_all_raw_sources(tmp_path):
    _,a=supervised('a'); _,b=supervised('b',split='validation')
    corpus.packer_subset(tmp_path,[a,b],{'test':'binding'},420,'review-sha')
    m=load(tmp_path/'manifest.json')
    assert m['review_complete'] and m['unreviewed_turns']==0
    assert m['excluded_unreviewed_source_turns']==420 and 'NOT every source' in m['review_scope']
    assert m['split_counts']==dict(train=dict(sft=1),validation=dict(sft=1))
    assert m['prior_assistant_loss'] is False


def test_recipe_preserves_authorized_resume_state_and_10000_updates():
    _,row=supervised()
    recipe=corpus.recipe([row])
    assert recipe['data']['target_tokens']==1
    assert recipe['optimizer_updates']==10000
    assert recipe['mixture']['identity_fraction']==0.05
    assert recipe['mixture']['dfm11_fraction']==0.95
    assert recipe['ema']['old_weight_fraction']['100']==pytest.approx(0.9900493387)
    assert recipe['ema']['old_weight_fraction']['1000']==pytest.approx(0.9048328936)
    assert recipe['ema']['old_weight_fraction']['10000']==pytest.approx(0.3678610464)
    assert recipe['ema']['decay']==0.9999
    assert recipe['ema']['state']=='preserve_existing_unchanged'
    assert recipe['ema']['reset'] is False
    assert recipe['ema']['initialize_training_from_ema'] is False
    assert recipe['ema']['evaluation_and_export']=='EMA_ONLY'
    assert 'normal training checkpoint weights plus optimizer' in recipe['initialization']
    assert recipe['status']=='user_authorized_plan_parent_owned_not_launched'
    assert recipe['warmup_updates']==0 and recipe['lr_schedule']=='constant_no_decay'
    assert recipe['lr']==1e-5 and recipe['lr_auto'] is True
    assert 'proposed_exposure_cap' not in recipe
    assert 'decision_required' not in recipe['ema']
    assert recipe['sealed_holdout']['status']=='not_created'
    assert recipe['exposure_accounting']['identity_rendered_token_budget']==131072000


def review_paths():
    return [corpus.ROOT/'configs/dfm12'/name for name in [
        'identity-ema-stochastic-20260927-reviewed.yaml',
        *[f'identity-ema-stochastic-20260927-sample{i}-reviewed.yaml' for i in (1,2,3)]]]


def test_merge_preserves_all_original_reviews_and_provenance():
    paths=review_paths()
    merged=corpus.merge_review_ledgers(paths)
    assert len(merged['reviews'])==560 and len(merged['source_ledgers'])==4
    index={(r['case'],r['sample'],r['turn']):r for r in merged['reviews']}
    for path in paths:
        original=yaml.safe_load(path.read_text())
        for entry in original['reviews']:
            result=copy.deepcopy(index[(entry['case'],entry['sample'],entry['turn'])])
            source=result.pop('review_ledger_source')
            assert result==entry
            assert source['sha256']==corpus.file_hash(path)
            assert source['reviewer']==original['reviewer']


@pytest.mark.parametrize('change', ['missing_sample','duplicate_sample','missing_turn','bad_pin'])
def test_merge_rejects_incomplete_or_unpinned_review(change,tmp_path):
    paths=review_paths()
    if change=='missing_sample': paths=paths[:-1]
    elif change=='duplicate_sample': paths[-1]=paths[0]
    else:
        ledger=yaml.safe_load(paths[0].read_text())
        if change=='missing_turn': ledger['reviews'].pop()
        else: ledger['source_sha256']='bad'
        path=tmp_path/'invalid.yaml'
        path.write_text(yaml.safe_dump(ledger))
        paths[0]=path
    with pytest.raises(ValueError): corpus.merge_review_ledgers(paths)


def test_ledger_partial_batch_is_declared_not_heuristically_selected():
    ledger=yaml.safe_load((corpus.ROOT/'configs/dfm12/identity-ema-stochastic-20260927-reviewed.yaml').read_text())
    rows=ledger['reviews']
    assert len(rows)==140
    assert {(r['case'],r['sample'],r['turn']) for r in rows}=={
        (i,0,t) for i in range(100) for t in range(1,3 if i<40 else 2)}
    assert all(r['reason'] for r in rows)
    assert all(r['turn']==1 for r in rows if r.get('reuse_chosen'))
    assert next(r for r in rows if r['case']==0 and r['turn']==1)['prompt_ambiguity']


def test_underspecified_depth_is_completeness_not_factual_contradiction():
    rows=yaml.safe_load((corpus.ROOT/'configs/dfm12/identity-ema-stochastic-20260927-reviewed.yaml').read_text())['reviews']
    entry=next(r for r in rows if (r['case'],r['sample'],r['turn'])==(62,0,1))
    assert entry['verdict']=='partial' and entry['preference_kind']=='completeness'
    row,tokens=supervised(kind=entry['preference_kind'],case=62)
    assert corpus.targeted_rows([row],[tokens])==[]
