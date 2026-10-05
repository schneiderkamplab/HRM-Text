from dfm12 import latvian_p3_review_queue as m


def test_lexical_retrieval_uses_text_not_row_number():
    english=['Hank Baskett Philadelphia Eagles 2010','Andy Hallett Angel Lorne']
    a=list(m.lexical_candidates(english,['Andy Hallett Angel']))[0]
    b=list(m.lexical_candidates(english[::-1],['Andy Hallett Angel']))[0]
    assert english[a[0][0]]==english[::-1][b[0][0]]==english[1]


def test_fusion_never_verifies_positional_or_agreement():
    catalog={x:dict(candidate_id=x,question=x) for x in ['a','b','c']}
    fused=m.fuse(catalog,['a'],['a'],{'b'},'c')
    assert [r['candidate_id'] for r in fused]==['a','b','c']
    assert [r['pairing_verified'] for r in fused]==[False,False,True]
    assert fused[1]['retrieval_origins']==['positional_unverified']


def test_scores_bound_to_reference_ids_not_fused_positions():
    record=dict(english_candidates=[dict(candidate_id='b'),dict(candidate_id='a')],retrieval_scores=[.9,.8])
    assert m.semantic_scores(record)=={'b':.9,'a':.8}
