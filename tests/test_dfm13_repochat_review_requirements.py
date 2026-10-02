import pytest
from scripts import dfm13_repochat_review_requirements as r


def test_extraction_never_sees_answer():
    messages = r.requirements_request('Change data handling; preserve all styles.')
    assert messages[-1] == {'role': 'user', 'content': 'Change data handling; preserve all styles.'}
    assert len(messages) == 2
    assert 'NOT seen an answer' in messages[0]['content']


def test_requirement_contract():
    assert r.validate_requirements({'requirements': ['Preserve all styles.']}) == ['Preserve all styles.']


@pytest.mark.parametrize('value', [{}, {'requirements': []}, {'requirements': ['']}, {'requirements': [True]}, {'requirements': ['x'], 'accept': True}])
def test_requirement_contract_fails_closed(value):
    with pytest.raises(ValueError):
        r.validate_requirements(value)


def test_only_read_only_tools():
    assert {x['function']['name'] for x in r.native.TOOLS} == {'list_files', 'search_repository', 'read_file'}


def test_cases_are_unique():
    assert len(r.IDS) == len(set(r.IDS)) == 8


def test_repairs_are_additive_and_concrete():
    from scripts import dfm13_repochat_targeted_repair as repair
    assert repair.ROOT != r.SOURCE
    assert len(repair.FEEDBACK) == 3
    assert '${GFLAGS_TARGET}' in repair.FEEDBACK['ef7ba0d5783760ad92a866fc69ec6699e45ecee6faa8a2bd3f1af9e43dde66b3']
    assert 'N-1' in repair.FEEDBACK['7d4bf1be1f03dc470b753cf9c2adaeccd3a5e09d50edf7734b01854ae3cbed35']
