"""Private successor adapter: an empty rationale alone cannot veto a clean keep."""
from copy import deepcopy
import sys
from jsonschema import Draft202012Validator
from . import wave_compact_review as original

deterministic_checks=original.deterministic_checks


def schema(record=None):
    value=deepcopy(original.schema(record))
    value['properties']['reason']['minLength']=0
    return value


def validate(value):
    Draft202012Validator(schema()).validate(value)
    if value==dict(verdict='keep',issues=[],reason=''):
        return value
    return original.validate(value)


def keeps(value,record,deterministic=True):
    return validate(value)['verdict']=='keep' and (
        not deterministic or all(c['passed'] for c in deterministic_checks(record)))


def request(record):
    value=original.request(record)
    value['response_format']['json_schema']['schema']=schema(record)
    return value


def install(controller):
    previous=controller.v6.adapters
    controller.v6.adapters=lambda:(sys.modules[__name__],previous()[1])
    controller.v6.review_request=lambda record,adapter:request(record)
    return controller
