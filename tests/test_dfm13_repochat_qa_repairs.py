from scripts import dfm13_repochat_qa_repairs as r


def test_scope_and_isolation():
    assert len(r.FEEDBACK) == 2
    assert r.ROOT != r.SOURCE
    tasks = r.repair.b.load(r.SOURCE / 'selection.json')['tasks']
    assert set(r.FEEDBACK) <= {t['id'] for t in tasks}
    assert all(len(key) == 64 for key in r.FEEDBACK)


def test_feedback_preserves_source_uncertainty():
    feedback = '\n'.join(r.FEEDBACK.values())
    assert 'external availability not verified' in feedback
    assert 'maximum safety' in feedback
    assert 'claiming execution' in feedback
