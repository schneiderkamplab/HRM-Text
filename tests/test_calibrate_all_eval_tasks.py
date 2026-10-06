from scripts.calibrate_all_eval_tasks import candidates
from scripts.group_eval_capacity_tasks import family


def test_short_requests_allow_large_candidate():
    task = {'rows': [{'prompt_tokens': 80, 'payload': {'max_tokens': 8}, 'historical_output_tokens': 2}]}
    assert candidates(task, 250000) == [32, 512, 1024]


def test_long_requests_receive_smaller_candidates():
    task = {'rows': [{'prompt_tokens': 3000, 'payload': {'max_tokens': 512}}]}
    assert candidates(task, 250000) == [16, 32]


def test_candidates_are_bounded_and_sorted():
    task = {'rows': [{'prompt_tokens': 4000, 'payload': {'max_tokens': 96}}]}
    levels = candidates(task, 1000)
    assert levels == sorted(set(levels))
    assert min(levels) >= 8 and max(levels) <= 1024


def test_translated_templates_share_family_but_not_unrelated_datasets():
    assert family({'action':'eval_euroeval','name':'multi-ifeval-da'}) == 'multi-ifeval'
    assert family({'action':'eval_euroeval','name':'multi-ifeval-en'}) == 'multi-ifeval'
    assert family({'action':'eval_dfm','name':'gec_dala_nl'}) == 'gec_dala'
    assert family({'action':'eval_euroeval','name':'dutch-cola'}) == 'dutch-cola'
