import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('quote_diagnostics',Path(__file__).parents[1]/'scripts/dfm13_arena_quote_diagnostics.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_unique_exact_only():
    messages=[{'content':'Give one example'}, {'content':'Here are two examples'}]
    assert module.classify({'quote':'Give one example','message_index':1},messages)==('exact_unique_elsewhere',[0])
    assert module.classify({'quote':'Give an example','message_index':1},messages)[0]=='absent_or_paraphrase'
    assert module.classify({'quote':'Give  one example','message_index':1},messages)[0]=='whitespace_only_match'
    assert module.classify({'quote':'**Give** one example','message_index':1},messages)[0]=='formatting_heuristic_match'


def test_ambiguous_no_proposal():
    messages=[{'content':'same'}, {'content':'same'}, {'content':'different'}]
    assert module.classify({'quote':'same','message_index':2},messages)==('exact_ambiguous_elsewhere',[0,1])
    assert module.classify({'quote':'same','message_index':0},messages)[0]=='exact_at_claimed_index'


def test_changes_index_only_and_preserves_semantic_uncertainty():
    row={'messages':[{'role':'user','content':'Give one example'},
                     {'role':'assistant','content':'Here are two examples'}],'target_message_index':1}
    result=dict(disposition='repair',confidence='high',rationale='Count violation',
        issues=[dict(category='instruction_following',severity='major',message_index=1,
            quote='Give one example',evidence='Two instead of one',basis='conversation')],
        verification=dict(category='none',question='',required_evidence=''),repair_plan='Give one')
    report=module.diagnose(result,row)
    assert report['proposed_passes_original_validator']
    assert report['semantic_approval'] is False
    assert result['issues'][0]['message_index']==1
    expected=dict(result,issues=[dict(result['issues'][0],message_index=0)])
    assert report['proposed_result']==expected
    assert report['changes'][0]['message_role']=='user'


def test_mixed_failure_not_accepted():
    row={'messages':[{'role':'user','content':'Give one example'},
                     {'role':'assistant','content':'Here are two examples'}],'target_message_index':1}
    result=dict(disposition='reject',confidence='high',rationale='Issue',issues=[
        dict(category='correctness',severity='major',message_index=1,quote=q,evidence='Issue',basis='conversation')
        for q in ('Give one example','fabricated quote')],
        verification=dict(category='none',question='',required_evidence=''),repair_plan='')
    report=module.diagnose(result,row)
    assert len(report['changes'])==1
    assert not report['proposed_passes_original_validator']
