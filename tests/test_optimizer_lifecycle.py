from types import SimpleNamespace
import pytest
from models.optimizer_lifecycle import accumulated_step_lifecycle


@pytest.mark.parametrize('skip,fail',[(False,False),(True,False),(False,True)])
def test_step_lifecycle(skip,fail):
    events=[]
    model=SimpleNamespace(begin_optimizer_step=lambda:events.append('begin'),end_optimizer_step=lambda **kw:events.append(kw['success']))
    @accumulated_step_lifecycle
    def step(train_state, optimizer_step_enabled=True):
        if fail:
            raise ValueError('test failure')
        return {},skip
    state=SimpleNamespace(model=model)
    if fail:
        with pytest.raises(ValueError): step(state)
    else:
        step(state)
    assert events == ['begin',not (skip or fail)]


def test_no_hooks_for_compile_warmup():
    @accumulated_step_lifecycle
    def step(train_state, optimizer_step_enabled=True): return {},False
    model=SimpleNamespace(begin_optimizer_step=lambda:pytest.fail('Warmup must not update routing'))
    step(SimpleNamespace(model=model),optimizer_step_enabled=False)
