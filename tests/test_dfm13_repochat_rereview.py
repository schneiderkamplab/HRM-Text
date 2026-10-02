import pytest
from scripts import dfm13_repochat_rereview as r


def test_good_control():
    assert r.validate({'support': 'sufficient', 'findings': [], 'rationale': 'Matches the retrieved function.'})


@pytest.mark.parametrize('kind', r.KINDS)
def test_typed_finding_rejects(kind):
    assert not r.validate({'support': 'sufficient', 'findings': [{'kind': kind, 'detail': 'Concrete defect'}], 'rationale': 'Otherwise useful'})


def test_insufficient():
    assert not r.validate({'support': 'insufficient', 'findings': [], 'rationale': 'Missing declaration'})


@pytest.mark.parametrize('doc', [{}, {'support': True, 'findings': [], 'rationale': 'x'}, {'support': 'sufficient', 'findings': ['wrong'], 'rationale': 'x'}, {'support': 'sufficient', 'findings': [], 'rationale': ''}, {'support': 'sufficient', 'findings': [], 'rationale': 'x', 'verdict': True}])
def test_contract_failures(doc):
    with pytest.raises(ValueError):
        r.validate(doc)


def test_schema_matches_validator():
    import jsonschema
    doc = {'support': 'sufficient', 'findings': [], 'rationale': 'Supported'}
    jsonschema.validate(doc, r.SCHEMA)
    assert r.validate(doc)


def test_review_package_excludes_generator_instructions():
    from scripts.dfm13_repochat_review_probe import package
    doc = package([{'role': 'system', 'content': 'Generator instruction'},
                   {'role': 'user', 'content': 'Original task'},
                   {'role': 'tool', 'content': 'Actual source'},
                   {'role': 'user', 'content': 'Calibration harness: reminder'},
                   {'role': 'assistant', 'content': 'Final answer'}])
    assert doc == {'original_request': 'Original task', 'final_answer': 'Final answer', 'retrieved_source': ['Actual source']}
