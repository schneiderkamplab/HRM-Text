import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('arena_verdict_test',Path(__file__).parents[1]/'scripts/dfm13_arena_verdict_comparison.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_metadata_error_preserves_consensus_without_certifying():
    assert module.decision({'status':'review_error'},{'neutral':{'verdict':'keep'},'critic':{'verdict':'keep'}})==('keep','unvalidated_initial_consensus')


def test_disagreement_is_unresolved_not_forced_wrong():
    assert module.decision({'status':'review_error'},{'neutral':{'verdict':'keep'},'critic':{'verdict':'repair'}})[0] is None


def test_adjudicator_and_validated_precedence():
    stages={'adjudicator':{'verdict':'repair'}}
    assert module.decision({'status':'invalid_response'},stages)==('repair','unvalidated_adjudicator')
    assert module.decision({'status':'complete','result':{'verdict':'reject'}},stages)==('reject','validated_final')
