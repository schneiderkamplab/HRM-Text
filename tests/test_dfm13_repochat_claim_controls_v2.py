import json
import pytest
from scripts import dfm13_repochat_claim_controls_v2 as c


def raw(detail):
    findings = [] if detail is None else [{'kind': 'unsupported_claim', 'detail': detail}]
    return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({
        'support': 'sufficient', 'findings': findings, 'rationale': 'source comparison'})}}]}


@pytest.mark.parametrize('detail', ['None', 'None. All claims are supported.', '', 'N/A'])
def test_placeholders_are_invalid_not_semantic_rejections(detail):
    with pytest.raises(ValueError, match='placeholder'):
        c.checked_document(raw(detail), c.base.old.full.reviewer.r.SCHEMA)


def test_empty_findings_supported_is_valid():
    doc = c.checked_document(raw(None), c.base.old.full.reviewer.r.SCHEMA)
    assert c.base.old.full.reviewer.r.validate(doc)


def test_real_finding_beginning_none_of_is_not_filtered():
    doc = c.checked_document(raw('None of the supplied declarations exports the claimed identifier.'), c.base.old.full.reviewer.r.SCHEMA)
    assert not c.base.old.full.reviewer.r.validate(doc)


def test_prompt_is_repository_agnostic():
    prompt = c.ATOMIC_RULES + c.EMPTY_FINDINGS_RULES
    for word in c.base.FOUR + ['Agnai', 'Neuro', 'MergePath', 'Voxtulate', 'Redis', 'clients']:
        assert word not in prompt


def test_bounded_selection_and_restart(tmp_path):
    plan = c.prepare(tmp_path)
    assert len(plan['controls']) == 8
    assert sum(x['expected_pass'] for x in plan['controls']) == 4
    assert not plan['automatic_next_stage']
    assert c.prepare(tmp_path) == plan
