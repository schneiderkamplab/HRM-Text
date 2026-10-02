from copy import deepcopy
from scripts import dfm13_search_targeted_cpu2 as client


def test_only_final_replaced_with_authorship_preserved():
    for prefix in client.ANSWERS:
        candidate = dict(id=prefix+'suffix', messages=[dict(role='user',content='original'),
            dict(role='tool',content='unchanged observations'), dict(role='assistant',content='old')],
            provenance=dict(teacher_generated_final=True), tools=[])
        before = deepcopy(candidate)
        corrected = client.correct(candidate)
        assert candidate == before
        assert corrected['messages'][:-1] == before['messages'][:-1]
        assert corrected['messages'][-1]['content'] == client.ANSWERS[prefix]
        assert corrected['provenance']['teacher_generated_final'] is False
        assert corrected['admission_authorized'] is False
        assert corrected['correction_provenance']['original_hold_not_cleared'] is True
