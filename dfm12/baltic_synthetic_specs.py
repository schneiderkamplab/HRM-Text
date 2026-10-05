"""Baltic adapter using the established European contracts in isolated globals."""
import importlib.util
from pathlib import Path
from types import FunctionType

from . import multilingual_tasks as tasks

LANGUAGES = {'lt': 'Lithuanian', 'lv': 'Latvian'}
_path = Path(__file__).with_name('european_synthetic_specs.py')
_spec = importlib.util.spec_from_file_location('dfm12._baltic_specs', _path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
_module.LANGUAGES = dict(LANGUAGES)
_module.VERSION = 'baltic-synthetic-specs-v1'
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
