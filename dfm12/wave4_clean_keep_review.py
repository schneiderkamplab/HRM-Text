"""Private end-to-end review contract: only exact clean keeps may omit rationale."""
from copy import deepcopy
from pathlib import Path
import sys
from jsonschema import Draft202012Validator
from . import wave_compact_review as original
from .io import load

deterministic_checks=original.deterministic_checks


def schema(record=None):
    value=deepcopy(original.schema(record))
    value['properties']['reason']['minLength']=0
    value['allOf']=[{'anyOf':[
        {'properties':{'reason':{'minLength':1}}},
        {'properties':{'verdict':{'const':'keep'},'issues':{'maxItems':0},'reason':{'const':''}}}]}]
    return value


def validate(value):
    Draft202012Validator(schema()).validate(value)
    if value==dict(verdict='keep',issues=[],reason=''):return value
    return original.validate(value)


def keeps(value,record,deterministic=True):
    return validate(value)['verdict']=='keep' and (
        not deterministic or all(c['passed'] for c in deterministic_checks(record)))


def request(record):
    payload=original.request(record)
    payload['response_format']['json_schema']['schema']=schema(record)
    return payload


def install(controller):
    previous=controller.v6.adapters
    module=sys.modules[__name__]
    controller.v6.adapters=lambda:(module,previous()[1])
    controller.v6.review_request=lambda record,adapter:request(record)
    retained=controller.validate_saved_keep
    def saved(directory,key,spec,outcome,adapters=None):
        contract=load(Path(directory)/'requests'/f'{key}-review.json')['schema']
        if contract==schema():review=module
        elif contract==original.schema():review=original
        else:raise ValueError('Unknown saved review contract')
        return retained(directory,key,spec,outcome,(review,controller.v6.adapters()[1]))
    controller.validate_saved_keep=saved
    return controller
