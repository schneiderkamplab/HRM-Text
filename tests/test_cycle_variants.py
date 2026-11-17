from models.cycle_schedule import scheme_pool, draw_cycle_scheme, weighted_call_counts

def test_pools():
    assert len(scheme_pool(15)) == 30
    assert len(scheme_pool(16)) == 34
    assert (4,3) in scheme_pool(16)
    for budget in range(2,17):
        assert all(h*(l+1)<=budget for h,l in scheme_pool(budget))

def test_replay():
    draws = [draw_cycle_scheme(42,s,i,16) for s in range(100) for i in range(1,5)]
    assert draws == [draw_cycle_scheme(42,s,i,16) for s in range(100) for i in range(1,5)]
    assert set(draws) == set(scheme_pool(16))

def test_weighted_counts():
    assert weighted_call_counts([(2,3),(2,3)],[1,3]) == (2,6)
    assert weighted_call_counts([(1,2),(3,4)],[3,1]) == (1.5,4.5)


def test_warmup_pools_and_disabled_mode():
    from types import SimpleNamespace
    from models.cycle_schedule import BASELINE,step_schemes
    from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModel
    from test_cycle_training import config,state
    c=config(budget=16);s=state(c)
    for step,expected in ((0,2),(5,9),(10,16),(100,16)):
        s.step=step
        budget=s.model.compute_train_extra_args(s)['bp_steps']
        assert budget==expected
        assert all(h*(l+1)<=budget for h,l in step_schemes(c,step,10,budget))
    c.arch.cycle_variants='off'
    assert step_schemes(c,100,1,None) is None
