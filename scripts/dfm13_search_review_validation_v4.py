"""Typed semantic review validation using destination-aware link parsing."""
from scripts.dfm13_search_links_v4 import equivalent, check


def validate_review(value,pages,answer):
    required={'reason','supporting_urls','unsupported_claims','findings'}
    if not isinstance(value,dict) or set(value)!=required:
        raise ValueError('review schema invalid')
    if not isinstance(value['reason'],str) or not value['reason'].strip():
        raise ValueError('review reason invalid')
    for key in ('supporting_urls','unsupported_claims'):
        if not isinstance(value[key],list) or not all(isinstance(x,str) and x.strip() for x in value[key]):
            raise ValueError('review list invalid')
    findings=value['findings']
    kinds={'incorrect_fact','unsupported_claim','temporal_mismatch','task_failure','uncertainty'}
    if not isinstance(findings,list) or not all(isinstance(x,dict) and set(x)=={'kind','explanation'} and
            x['kind'] in kinds and isinstance(x['explanation'],str) and x['explanation'].strip() for x in findings):
        raise ValueError('invalid typed findings')
    known={equivalent(u) for u in pages}
    if any(equivalent(u) not in known for u in value['supporting_urls']):
        raise ValueError('review cites unobserved source')
    verdict='reject' if any(x['kind']!='uncertainty' for x in findings) else (
        'needs_verification' if findings or value['unsupported_claims'] else 'keep')
    if verdict=='keep': check(answer,pages,value['supporting_urls'])
    return dict(value,verdict=verdict)
