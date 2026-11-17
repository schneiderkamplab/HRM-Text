from scripts.dfm16_english_production_combined import aggregate


def test_self_review_cannot_admit_missing_independent_judge():
    req=[{'id':'p/check','parent_id':'p'}]
    assert aggregate('p',req,{'flash':{'p/check':'accept'},'qwen27b':{}},{'p':'accept'})=='unresolved'


def test_independent_rejection_vetoes_accepting_specialist():
    req=[{'id':'p/check','parent_id':'p'}]
    assert aggregate('p',req,{'flash':{'p/check':'reject'},'qwen27b':{'p/check':'accept'}},{'p':'accept'})=='reject'


def test_all_required_accepts_and_no_empty_check_set():
    req=[{'id':'p/check','parent_id':'p'}]
    votes={'flash':{'p/check':'accept'},'qwen27b':{'p/check':'accept'}}
    assert aggregate('p',req,votes,{'p':'accept'})=='accept'
    assert aggregate('p',[],votes,{'p':'accept'})=='unresolved'
    assert aggregate('p',req,votes,{'p':'unresolved'})=='unresolved'
