from collections import Counter

from scripts import dfm12_error_composition as m
from scripts import recover_dfm11_error_provenance as recovery
import json
import gzip
import numpy as np
import pytest


def pair():
    return dict(original='We are here.',corrupted='We is here.',edits=[dict(
        start=3,end=6,original='are',replacement='is',corrupted_start=3,corrupted_end=5,
        rule_id='agreement',corruption_type='subject_verb_agreement')])


def test_annotation_requires_explicit_reconstructable_edits():
    p=pair()
    assert m.annotation(p)==(('agreement','subject_verb_agreement','are','is'),)
    p['edits'][0]['corrupted_end']=6
    assert m.annotation(p) is None


def test_no_edit_distance_inference():
    assert m.annotation(dict(original='cat',corrupted='dog')) is None
    assert m.pair_key(' cat','dog')!=m.pair_key('cat','dog')


def test_conflicting_annotations_stay_unknown():
    d={};key=b'key'
    m.insert_lookup(d,key,('one',));m.insert_lookup(d,key,('two',));m.insert_lookup(d,key,('one',))
    assert d[key] is None


def test_sampled_multiplicity_tokens_and_distinct_edit_pairs():
    s=m.empty_language();rules=set();pairs=set();types=Counter()
    edits=m.annotation(pair())
    m.add_row(s,edits,3,42,rules,pairs,types)
    m.add_row(s,edits,2,27,rules,pairs,types)
    assert s['correction_rows']==5 and s['correction_tokens']==69
    assert s['mistake_count_rows']['1']==5
    assert rules=={'agreement'} and pairs=={('are','is')}
    assert types['subject_verb_agreement']==5


def test_clean_and_unknown_are_different():
    s=m.empty_language();rules=set();pairs=set();types=Counter()
    m.add_row(s,(),2,20,rules,pairs,types)
    m.add_row(s,None,3,30,rules,pairs,types)
    assert s['mistake_count_rows']['0']==2
    assert s['mistake_count_rows']['unknown']==3


def test_four_plus_and_zero_sample_weight():
    s=m.empty_language();rules=set();pairs=set();types=Counter()
    edits=m.annotation(pair())*5
    m.add_row(s,edits,1,50,rules,pairs,types)
    m.add_row(s,None,0,0,rules,pairs,types)
    assert s['mistake_count_rows']['4+']==1 and s['correction_rows']==1
    assert len(pairs)==1


def test_schema_has_21_languages_and_requested_bins():
    assert len(m.LANGUAGES)==21
    assert set(m.empty_language()['mistake_count_rows'])=={'0','1','2','3','4+','unknown'}


def test_inherited_denoising_and_coedit_not_inferred_grammar():
    for name in ('common-pile-denoising__x','posttrain_coedit__x'):
        assert m.inherited_observation(name,{})==('en', 'denoising' if 'denoising' in name else 'CoEdit editing',None,'unclassified',None,None)


def test_folketing_declared_counts_are_not_spelling_labels():
    obs=m.inherited_observation('dfm11-folketingets-dokumenter-error-correction__x',
        {'metadata':{'dfm11_repair':{'declared_ocr_edits':3}}})
    assert obs[2:]==(3,'unclassified',None,None)


def test_mixed_summary_source_does_not_all_become_correction():
    name='dfm8-synthetic-danish-summarization-rewrite-controls__x'
    assert m.inherited_observation(name,{'user_prefix':'Opsummer teksten'}) is None
    assert m.inherited_observation(name,{'user_prefix':'Omskriv teksten'})[2] is None


def test_tv2_pair_requires_exact_declared_substitution():
    raw={'direction':'Correct','samples':[{'content':'a cot','response':'a cat',
        'affected_token_1':'cat','affected_token_2':'cot'}]}
    row=recovery.compact({'messages':[{'role':'user','content':'Correct\n\na cot'},
        {'role':'assistant','content':'a cat'}],'row_id':'source:test:0','corruption_type':'corrupt_spelling'},0)
    obs=m.inherited_observation('giannor_tv2r_instruction__giannor_gec_dala_tv2r_it__test.jsonl',row,raw)
    assert obs[2:]==(1,'spelling','corrupt_spelling',('cat','cot'))
    raw['samples'][0]['affected_token_1']='wrong'
    assert m.inherited_observation('giannor_tv2r_instruction__giannor_gec_dala_tv2r_it__test.jsonl',row,raw)[-1] is None


def test_tv2_clean_controls_with_multparagraph_instruction():
    raw={'direction':'Correct\n\nRules','samples':[{'content':'a cat','response':'a cat'}]}
    row=recovery.compact({'messages':[{'role':'user','content':'Correct\n\nRules\n\na cat'},
        {'role':'assistant','content':'a cat'}],'row_id':'source:validation:0'},0)
    assert row['target_equals_input_sentence'] is False
    assert m.inherited_observation('giannor_tv2r_instruction__giannor_gec_dala_tv2r_it__validation.jsonl',row,raw)[2]==0


def test_recovery_reads_parquet_structurally(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    p=tmp_path/'source.parquet'
    pq.write_table(pa.Table.from_pylist([{'condition':'direct','instruction':'a','response':'b'}]),p)
    assert list(recovery.records(p))[0]['response']=='b'


def test_unknown_edit_count_and_declared_ocr_count_are_separate():
    stats=m.empty_language();rules=set();pairs=set()
    cr={c:set() for c in m.CATEGORIES};cp={c:set() for c in m.CATEGORIES}
    m.add_inherited_observation(stats,('da','OCR correction',3,'unclassified',None,None),2,40,rules,pairs,cr,cp)
    m.add_inherited_observation(stats,('da','denoising',None,'unclassified',None,None),1,20,rules,pairs,cr,cp)
    assert stats['mistake_count_rows']['3']==2 and stats['mistake_count_rows']['unknown']==1
    assert stats['categories']['grammar']['rows']==0 and stats['categories']['unclassified']['rows']==3


def test_compact_preserves_original_metadata_and_nonempty_targets():
    r={'messages':[{'role':'system','content':'system'}, {'role':'user','content':'Rewrite this'},
                   {'role':'assistant','content':' '}], 'corruption_type':'source-rule'}
    result=recovery.compact(r,7)
    assert result['ordinal']==7 and result['assistant_messages']==1
    assert result['nonempty_assistant_messages']==0 and result['user_prefix']=='Rewrite this'
    assert result['corruption_type']=='source-rule' and 'messages' not in result


def test_augmentation_uniform_task_keeps_exposure_but_not_shifted_annotations(tmp_path):
    component='dfm11-folketingets-dokumenter-error-correction__data__x.jsonl.gz'
    folder=tmp_path/'error_metadata';folder.mkdir()
    p=folder/'rows.jsonl.gz'
    with gzip.open(p,'wt') as f:
        for i in range(2):
            f.write(json.dumps({'ordinal':i,'assistant_messages':1,'metadata':{'dfm11_repair':{'declared_ocr_edits':2}}})+'\n')
    (folder/'manifest.json').write_text(json.dumps({'sources':[dict(component=component,metadata=p.name,
        metadata_sha256=m.file_hash(p),source='remote',source_sha256='raw-pin',rows=2)],'missing':[]}))
    sampled=tmp_path/'sampled_error_rows';sampled.mkdir()
    a=sampled/(component+'.npz')
    np.savez(a,tokenized_ordinal=np.array([0]),sampled_multiplicity=np.array([3]),rendered_tokens=np.array([45]))
    source_map=tmp_path/'source-map.json';source_map.write_text('{}')
    receipt=dict(schema='dfm11-sampled-error-row-counts-v1',
        status='complete_tokenized_ordinal_counts_raw_source_alignment_not_claimed',
        sampled_start_and_length_checks=True,selected_epoch='data/sampled_dfm11/epoch_0',
        source_map_sha256=m.file_hash(source_map),outputs=[dict(component=component,sha256=m.file_hash(a))])
    (sampled/'receipt.json').write_text(json.dumps(receipt))
    report=dict(languages={'da':m.empty_language()},evidence=[],completed_languages=[],missing_coverage=[],definitions={},
        denominators={'sampled_rows':100,'sampled_tokens':1000})
    result=m.augment_inherited(report,tmp_path)
    assert result['languages']['da']['correction_rows']==3
    assert result['languages']['da']['mistake_count_rows']['unknown']==3
    assert result['languages']['da']['mistake_count_rows']['2']==0
    assert result['languages']['da']['categories']['unclassified']['pct_all_training_tokens']==4.5
    assert result['inherited_recovery']['missing']
    with pytest.raises(ValueError,match='Already augmented'):m.augment_inherited(report,tmp_path)


def test_inherited_receipt_is_fail_closed(tmp_path):
    (tmp_path/'sampled_error_rows').mkdir()
    (tmp_path/'sampled_error_rows/receipt.json').write_text('{}')
    with pytest.raises(ValueError,match='Missing or invalid'):m.augment_inherited({},tmp_path)


def test_category_rows_not_edit_occurrences_and_mixed_overlap():
    s=m.empty_language();rules=set();pairs=set();types=Counter()
    cr={c:set() for c in m.CATEGORIES};cp={c:set() for c in m.CATEGORIES}
    edits=(('spell1','spelling','cat','cta'),('spell2','spelling','here','heer'),
           ('grammar1','subject_verb_agreement','are','is'))
    m.add_row(s,edits,3,99,rules,pairs,types,cr,cp)
    assert s['categories']['spelling']['rows']==3
    assert s['categories']['spelling']['tokens']==99
    assert s['categories']['grammar']['rows']==3
    assert len(cp['spelling'])==2 and len(cp['grammar'])==1
    assert cr['spelling']=={'spell1','spell2'}


def test_unrecognized_type_not_silently_grammar():
    assert m.category_of('word_swap')=='unclassified'
    assert m.category_of('spelling')=='spelling'
    assert m.category_of('adjective_case')=='grammar'
