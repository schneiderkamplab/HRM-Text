"""W4-only768/off-loop execution, with no fixed admission spacing."""
from . import baltic_async_io as shared_offload


def widen(function, previous):
    code = function.__code__
    if sum(type(v) is int and v == previous for v in code.co_consts) != 1:
        raise ValueError('Unexpected private concurrency guard')
    function.__code__ = code.replace(co_consts=tuple(
        768 if type(v) is int and v == previous else v for v in code.co_consts))
    return function


def install(c, owner):
    c = shared_offload.install(c, owner)
    widen(c.execute, 384)
    gate = c.AdmissionGate
    def initialize(self, *args, **kwargs):
        gate.__init__(self, *args, **kwargs)
        self.spacing = 0
    c.AdmissionGate = type('Wave4AdmissionGate', (gate,), {'__init__': initialize})
    # Correct emitted runtime metadata without modifying the shared installer.
    original_write = c.write_json
    def write(path, value):
        if path.name == 'runtime.json':
            value = dict(value, admission_spacing_seconds=0,
                         io_runtime_module='dfm12.wave4_async_runtime')
        return original_write(path, value)
    c.write_json = write
    return c
