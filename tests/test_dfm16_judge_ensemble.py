from scripts.analyze_dfm16_judge_ensemble import category, combine
from scripts.dfm16_judge_ensemble_study import StudyJudge


def test_ensemble_requires_every_valid_accept():
    assert combine(['accept', 'accept']) == 'accept'
    assert combine(['accept', 'unresolved']) == 'unresolved'
    assert combine(['accept', 'reject']) == 'reject'
    assert combine(['reject', 'unresolved']) == 'reject'
    assert combine([]) == 'unresolved'


def test_manual_borderlines_not_counted_as_definite_defects():
    assert category(['clear', 'borderline']) == 'borderline'
    assert category(['bad', 'borderline']) == 'bad'
    assert category(['clear', 'clear']) == 'clear'


def test_expanded_manual_stats_do_not_treat_missing_as_clear_or_invalid_as_accept():
    from scripts.report_dfm16_multiview_judges import manual_check_stats
    checks = [dict(id=str(i)) for i in range(5)]
    labels = {str(i): dict(label=label) for i, label in enumerate(['bad', 'clear', 'borderline', 'bad'])}
    result = manual_check_stats(checks, labels, {'0': 'accept', '1': 'reject', '2': 'accept', '3': 'invalid'})
    assert result == dict(labelled=4, bad=2, bad_accepted=1, clear=1, clear_rejected=1,
                          borderline=1, borderline_accepted=1, unresolved=1)


def test_model_prompt_does_not_leak_labels():
    judge = object.__new__(StudyJudge)
    judge.model = 'Qwen/Qwen3.8-27B'
    row = dict(prompt='Text: example. Answer yes or no.', language_decision='reject',
               manual_category='bad', coherence_decision='reject')
    payload = judge.prepare(row)
    assert payload['messages'] == [{'role': 'user', 'content': row['prompt']}]
    assert payload['chat_template_kwargs'] == {'enable_thinking': False}


def test_multiview_includes_seed_all_messages_and_both_window_types():
    from scripts.prepare_dfm16_multiview_judges import build_checks
    parent = dict(id='p', language='en', task='revision', provenance=dict(seed_audit_id='s'),
        messages=[dict(role=role, content=str(i)) for i,role in enumerate(['user','assistant','user','assistant'])])
    checks = build_checks([dict(parent_id='p', study_id='H001')], {'p': parent}, {'s': {'seed': 'Original story'}})
    assert len({r['id'] for r in checks}) == len(checks)
    assert sum(r['view'] == 'seed' for r in checks) == 3
    assert sum(r['view'] == 'message' for r in checks) == 12
    assert sum(r['view'] == 'conversation' for r in checks) == 2
    assert sum(r['view'] == 'message_pair' for r in checks) == 5
    assert sum(r['view'] == 'exchange_pair' for r in checks) == 1
    assert all(r['prompt'].endswith('Answer only yes or no.') for r in checks)
