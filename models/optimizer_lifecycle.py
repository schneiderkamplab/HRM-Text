"""Optional model lifecycle around an accumulated optimizer step."""
from functools import wraps
from inspect import signature


def accumulated_step_lifecycle(function):
    parameters = signature(function)

    @wraps(function)
    def wrapped(*args, **kwargs):
        bound = parameters.bind(*args, **kwargs)
        bound.apply_defaults()
        model = bound.arguments['train_state'].model
        # DDP/compile wrappers; FSDP2 retains the module's methods.
        while hasattr(model, '_orig_mod') or hasattr(model, 'module'):
            model = model._orig_mod if hasattr(model, '_orig_mod') else model.module
        begin = getattr(model, 'begin_optimizer_step', None)
        if begin is None or not bound.arguments['optimizer_step_enabled']:
            return function(*args, **kwargs)
        begin()
        try:
            result = function(*args, **kwargs)
            model.end_optimizer_step(success=not result[1])
            return result
        except BaseException:
            model.end_optimizer_step(success=False)
            raise
    return wrapped
