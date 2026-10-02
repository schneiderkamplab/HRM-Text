from scripts.dfm13_search_reviewer_controls import strong_test, CASES

def test_actual_composite_counterexample():
    n=151*751*28351
    assert n==3215031751 < 2**32
    assert all(strong_test(n,a) for a in (2,3,5,7))

def test_targeted_control_balance():
    assert [c['expected'] for c in CASES].count('reject')==2
    assert [c['expected'] for c in CASES].count('keep')==2
