from scripts.dfm13_search_final_inventory import category


def version(**changes):
    return dict(dict(student_fit_verified=True,complete_final=True,exact_hold=False,
        negative_same_content_reviews=[],manual_supported=False,automated_verdict=None),**changes)


def test_distinct_task_precedence_and_holds():
    assert category(dict(versions=[version(manual_supported=True),version(automated_verdict='keep')]))=='manual_supported'
    assert category(dict(versions=[version(automated_verdict='keep',exact_hold=True)]))=='held_no_eligible_keep'
    assert category(dict(versions=[version(automated_verdict='keep')]))=='automated_only'
    assert category(dict(versions=[version(automated_verdict='reject')]))=='rejected_no_eligible_keep'
    assert category(dict(versions=[]))=='unresolved'


def test_negative_exact_review_does_not_count_keep():
    assert category(dict(versions=[version(automated_verdict='keep',negative_same_content_reviews=['reject'])]))=='unresolved'
