"""Isolated wave-four adapter for native, audited synthetic conversation contracts."""
import importlib.util
from pathlib import Path
from types import FunctionType

from . import multilingual_tasks as tasks
from .wave4_cpu import LANGUAGES

_path = Path(__file__).with_name('european_synthetic_specs.py')
_spec = importlib.util.spec_from_file_location('dfm12._wave4_specs', _path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
_module.LANGUAGES = dict(LANGUAGES)
_module.VERSION = 'wave4-synthetic-specs-v1'
_module._factory = FunctionType(tasks.spec_for.__code__,
    dict(tasks.spec_for.__globals__, LANGUAGES=dict(LANGUAGES)),
    tasks.spec_for.__name__, tasks.spec_for.__defaults__, tasks.spec_for.__closure__)

SourceProvider = _module.SourceProvider
SeedUnavailable = _module.SeedUnavailable
spec_for = _module.spec_for
audit_record = _module.audit_record
request = _module.request
decode = _module.decode
assemble = _module.assemble
review_request = _module.review_request
