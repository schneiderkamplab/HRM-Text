import copy
import pytest
from scripts.patch_dfm13_workspace import build, check_sync, digest, RUN, verify_remote
from types import SimpleNamespace
from scripts.patch_dfm13_workspace import check_raw_layout


def fixture():
    return {'section': {'runSets': [{'selected': ['keep']}], 'panelBankConfig': {'sections': [
        {'name': 'Headline Averages', '__id__': 's', 'panels': [
            {'__id__': 'p', 'config': {'metrics': ['headline_avg_v3/overall'], 'xAxis': 'old/epoch', 'smoothing': .2}}]},
        {'name':'Multilingual Headline Metrics','__id__':'combined','panels':[], 'collapsed':False}]}}}


def test_additions_preserve_all_existing_content():
    s=fixture();before=copy.deepcopy(s)
    p={'populations':[{'kind':'dfm13_new_languages','languages':['lt'],'required_tasks':{'lt':['la']},
        'metrics':{'lt':{'la':{'key':'dfm_eval/dala_lt/semantic_v1/macro_f1','suite':'dfm'}}}}]}
    r=build(s,p)
    assert s==before and r['section']['runSets']==s['section']['runSets']
    assert r['section']['panelBankConfig']['sections'][:1]==s['section']['panelBankConfig']['sections'][:1]
    assert len(r['section']['panelBankConfig']['sections'])==2
    assert len(r['section']['panelBankConfig']['sections'][1]['panels'])==1


def test_replacement_and_deferred_sync():
    m={'overall_weighting_preserved':True,'replacements':[{'panel_id':'p','old':'headline_avg_v3/overall','new':'new/overall','axis':'new/epoch'}]}
    r=build(fixture(),{},m)
    assert r['section']['panelBankConfig']['sections'][0]['panels'][0]['config']['smoothing']==.2
    proof={'run_id':RUN,'checkpoint_step':3200000,'remote_verified':True,'mapping_sha256':digest(m),'values':{'new/overall':.5}}
    check_sync(proof,m)
    for change in [{'checkpoint_step':3150000},{'values':{}},{'remote_verified':False}]:
        with pytest.raises(ValueError):check_sync(dict(proof,**change),m)


def test_changed_panel_fails_closed():
    with pytest.raises(ValueError):build(fixture(),{}, {'overall_weighting_preserved':True,
        'replacements':[{'panel_id':'p','old':'wrong','new':'new','axis':'x'}]})


def test_remote_historical_requires_all67_and_matches_values():
    key='headline_avg_talemaader_v2/overall'; axis='headline_avg_talemaader_v2/train_step'
    mapping={'replacements':[{'new':key}], 'evidence_policy':{'kind':'historical_67'}}
    rows=[{key:i/100,axis:i} for i in range(67)]
    prepared={'run_path':'peter-sk-sdu/DFM5/'+RUN,'points':[{'train_step':i} for i in range(67)],'rows':rows}
    api=SimpleNamespace(run=lambda path:SimpleNamespace(scan_history=lambda **kwargs:iter(rows)))
    assert verify_remote(mapping,prepared,api)['verified_history_points'][key]==67
    rows.pop()
    with pytest.raises(ValueError):verify_remote(mapping,prepared,api)


def test_population_needs_complete3150_not3200_only():
    key='avg_population/dfm13_multilingual_v1/score'
    mapping={'replacements':[],'append_panels':[{'key':key}], 'evidence_policy':{'kind':'population_baseline'}}
    row={key:.5,'avg_population/train_step':3200000,key.rsplit('/',1)[0]+'/complete':1}
    api=SimpleNamespace(run=lambda path:SimpleNamespace(scan_history=lambda **kwargs:iter([row])))
    with pytest.raises(ValueError):verify_remote(mapping,None,api)
    row['avg_population/train_step']=3150000
    assert verify_remote(mapping,None,api)['population_baseline_step']==3150000
    row[key.rsplit('/',1)[0]+'/complete']=0
    with pytest.raises(ValueError):verify_remote(mapping,None,api)


def test_new_pause_requires_matching_mapping():
    mapping={'sync_pause_step':3154500,'replacements':[{'new':'k'}]}
    receipt={'run_id':RUN,'checkpoint_step':3154500,'remote_verified':True,'mapping_sha256':digest(mapping),'values':{'k':.5}}
    check_sync(receipt,mapping)
    with pytest.raises(ValueError):check_sync(dict(receipt,checkpoint_step=3200000),mapping)


def test_raw_layout_registry_cannot_authorize_averages_or_replacements():
    langs='da en nb nn sv is fo nl pl de fr es it cs pt_pt fi et ca el ro uk'.split()
    registry=[{'name':prefix+lang} for lang in langs for prefix in ('dala_v2_','gec_dala_v2_')]
    mapping={'replacements':[], 'evidence_policy':{'kind':'additional_raw_metrics'},
             'append_panels':[{'key':f"dfm_eval/{t['name']}/"+('exact_match/mean' if t['name'].startswith('gec_') else 'semantic_v1/macro_f1')} for t in registry]}
    check_raw_layout(mapping,registry)
    with pytest.raises(ValueError):check_raw_layout(dict(mapping,replacements=[{'new':'x'}]),registry)
    bad=copy.deepcopy(mapping);bad['append_panels'][0]['key']='avg_population/x/score'
    with pytest.raises(ValueError):check_raw_layout(bad,registry)
    with pytest.raises(ValueError):check_raw_layout(mapping,registry[:-1])


def test_expanded_average_appends_to_existing_section_preserving_history():
    original=fixture()
    mapping={'overall_weighting_preserved':True,'replacements':[], 'append_panels':[
        {'key':'new/danish','title':'Expanded Danish','axis':'new/epoch','section':'Headline Averages'}]}
    result=build(original,{},mapping)
    sections=result['section']['panelBankConfig']['sections']
    assert sections[0]['panels'][0]==original['section']['panelBankConfig']['sections'][0]['panels'][0]
    assert len(sections[0]['panels'])==2 and sections[1]==original['section']['panelBankConfig']['sections'][1]
    mapping['append_panels'][0]['section']='Invented layout'
    with pytest.raises(ValueError):build(original,{},mapping)


def test_expanded_baseline_requires_definition_counts_and_exact_step():
    key='headline_avg_dala_v2/danish'
    checks={key+'/count':20,'headline_avg_dala_v2/definition_sha256':'sealed'}
    mapping={'replacements':[], 'append_panels':[{'key':key}],
             'evidence_policy':{'kind':'expanded_baseline','required_values':{key:checks}}}
    row={key:.5,'headline_avg_dala_v2/train_step':3150000,**checks}
    api=SimpleNamespace(run=lambda path:SimpleNamespace(scan_history=lambda **kwargs:iter([row])))
    assert verify_remote(mapping,None,api)['complete'][key]
    for field,value in [(key+'/count',18),('headline_avg_dala_v2/definition_sha256','old'),('headline_avg_dala_v2/train_step',3200000)]:
        saved=row[field];row[field]=value
        with pytest.raises(ValueError):verify_remote(mapping,None,api)
        row[field]=saved
