"""Explicit request policy for wave-three/four calibrated synthetic production."""
import copy
import json
from collections.abc import Mapping
from urllib.parse import urlparse

from .io import digest, file_hash, load
from .multilingual_tasks import MODEL


def approved_groups(root):
    approval = load(root / 'calibration-approved.json')
    if approval.get('manifest_sha256') != file_hash(root / 'manifest.json'):
        raise ValueError('Calibration approval does not match campaign')
    groups = approval.get('approved_groups')
    if (not isinstance(groups, list) or not groups
            or any(not isinstance(g, list) or len(g) != 2
                   or not all(isinstance(v, str) and v for v in g) for g in groups)
            or len({tuple(g) for g in groups}) != len(groups)):
        raise ValueError('Explicit unique language/family approvals required')
    evidence = approval.get('evidence_files')
    if not isinstance(evidence, dict) or not evidence:
        raise ValueError('Pinned calibration evidence required')
    for path, sha in evidence.items():
        from pathlib import Path
        if file_hash(Path(path)) != sha:
            raise ValueError('Calibration evidence changed')
    return groups


def endpoint_limit(document):
    matches=[m for m in document.get('data',[]) if m.get('id')==MODEL]
    if len(matches)!=1 or type(matches[0].get('max_model_len')) is not int:
        raise ValueError('Exact model and advertised context required')
    if matches[0]['max_model_len']<32768:
        raise ValueError('Wave production requires verified 32K teacher context')
    return 32768


def validate_endpoints(endpoints):
    parsed=[urlparse(e) for e in endpoints]
    if (len(endpoints)!=8 or len(set(endpoints))!=8
            or {p.port for p in parsed}!=set(range(8800,8808))
            or any(p.scheme!='http' or p.hostname not in ('localhost','127.0.0.1')
                   or p.path.rstrip('/')!='/v1' or p.query or p.fragment for p in parsed)):
        raise ValueError('Require shared local servers 8800..8807')


class Budget:
    def __init__(self,directory,tokenizer=None):
        if tokenizer is None:
            from transformers import AutoTokenizer
            tokenizer=AutoTokenizer.from_pretrained(str(directory),local_files_only=True)
        self.tokenizer=tokenizer

    def measure(self,payload,limit=32768):
        if payload.get('model')!=MODEL or payload.get('chat_template_kwargs')!={'enable_thinking':False}:
            raise ValueError('Exact teacher and disabled thinking required')
        reserve=payload.get('max_tokens')
        if type(reserve) is not int or reserve<=0 or type(limit) is not int or not 0<limit<=32768:
            raise ValueError('Invalid token budget')
        ids=self.tokenizer.apply_chat_template(payload['messages'],tokenize=True,
            add_generation_prompt=True,enable_thinking=False)
        if isinstance(ids,Mapping):ids=ids['input_ids']
        if not isinstance(ids,list) or not all(type(i) is int for i in ids):
            raise ValueError('Expected flat token IDs')
        if len(ids)+reserve>limit:
            raise ValueError(f'Full prompt {len(ids)} + reserve {reserve} exceeds {limit}; no truncation')
        return dict(prompt_tokens=len(ids),max_tokens=reserve,total_tokens=len(ids)+reserve,
            context_limit=limit,token_ids_sha256=digest(ids))


def decoder_schema(value):
    if isinstance(value,dict):
        return {key:decoder_schema(item) for key,item in value.items()
                if key not in ('minLength','maxLength','pattern')}
    if isinstance(value,list):
        return [decoder_schema(item) for item in value]
    return value


def generation_request(spec,generation,endpoint_models=None):
    request_spec=copy.deepcopy(spec)
    if request_spec.get('source') and request_spec['family'] in ('multiturn','grounded-instruct','summary-rewrite'):
        request_spec.pop('topic',None)
    if spec['family']=='tool-dialogue':
        from .multilingual_tool_dialogue import request
        payload=request(spec)
        schema=payload['response_format']['json_schema']['schema']
    else:
        payload=generation.request(request_spec,endpoint_models=endpoint_models)
        schema=generation.schema(spec)
    payload=copy.deepcopy(payload)
    payload.pop('structured_outputs',None)
    payload['response_format']={'type':'json_schema','json_schema':{
        'name':'conversation','strict':True,'schema':schema}}
    payload['messages'][0]['content'] += '\nReturn exactly this JSON structure, without extra fields: '+json.dumps(schema)
    payload['messages'][0]['content'] += (
        '\nWhen source text is supplied, its subject overrides the generic topic label. '
        'Do not mention metadata labels, subtype names or these instructions in the conversation. '
        'Write idiomatic, grammatically correct native language. Use short, natural sentences. '
        'For math preserve the exact operation and every constant in reference.requirement; '
        'do not invent a story that changes the calculation. Describe the requested boxed '
        'answer format in words in the user prompt, avoiding backslash escapes there.')
    return payload


def review_request(record,review):
    payload=copy.deepcopy(review.request(record))
    schema=review.schema(record)
    payload.pop('structured_outputs',None)
    payload['response_format']={'type':'json_schema','json_schema':{
        'name':'review','strict':True,'schema':schema}}
    payload['messages'][0]['content'] += '\nReturn exactly this review JSON schema: '+json.dumps(decoder_schema(schema))
    payload['messages'][0]['content'] += (
        '\nCheck every generated user turn as well as assistant turns for natural grammar and coherent intent. '
        'For source-grounded tasks reject a conversation whose subject does not follow the passage. '
        'Check conceptual definitions, logical relations, scope, and qualifiers: repeating source vocabulary '
        'does not establish semantic equivalence. Reject an answer that conflates distinct concepts, '
        'reverses a relationship or strengthens a qualified claim. Do not excuse such errors because '
        'some other facts or numbers are correct.')
    return payload


def compact_request(payload):
    transport=copy.deepcopy(payload)
    formatted=transport.pop('response_format')
    schema=formatted['json_schema']['schema']
    transport.pop('structured_outputs',None)
    if formatted['json_schema']['name']=='review':
        transport['temperature']=0
        transport.pop('frequency_penalty',None)
        transport['response_format']={'type':'json_schema','json_schema':{
            'name':'review','strict':True,'schema':decoder_schema(schema)}}
    else:
        transport.update(temperature=.3,repetition_penalty=1.1)
        transport['response_format']={'type':'json_object'}
    # CPU stage validation still receives the full original constraints.
    return transport,schema
