"""Supplemental development checks for shared misses, never a qualification claim.

Reuses StagedAudit/audit_pipeline. Base votes remain immutable; these checks are
added conjunctively at conversation level, not counted as independent examples.
"""
import re
from copy import deepcopy
from scripts.dfm16_staged_audit import StagedAudit,checks,BASE

RULES={
 'request_preconditions': '''Inspect ONLY the current request's transformation preconditions against its actual input. Identify the input's existing tense/viewpoint and the state the request claims it has. Reject a false claimed starting state or an already-satisfied conversion presented as a real change. A grammatical unchanged answer does not cure a false request. Intentional grammar-correction inputs are allowed: check whether the requested correction actually applies, not whether the input is already grammatical. Accept legitimate changes superseding earlier facts. Do not judge unrelated answer quality.''',
 'paragraph_grammar': '''Inspect ONLY target_text for definite grammar errors in the stated language. Check every finite verb against its subject, every adjective/determiner against its noun, case and required particles, and word forms. For Hindi, check feminine/plural agreement and ergative ने with perfective transitive verbs, and do not accept masculine agreement for an explicitly all-female group. Use full context to resolve referents. Ignore stylistic preferences, fictional events, valid quotations and intentionally flawed text when the task requires quoting it. Do not assess source fidelity in this check.''',
 'paragraph_fidelity': '''Inspect ONLY target_text against the authoritative source and the current request. Check each asserted event, sensory detail, participant, direction of action, time relation and quantity for support. A plausible detail is not necessarily supported. Reject definite unsupported additions or changed facts when preservation is required. Permit paraphrase and omission appropriate to a summary. Respect explicit requested transformations and legitimate later revisions; do not demand literal copying. Do not judge grammar in this check.''',
}


def supplemental_checks(row):
    """Uniform criteria across the cohort, no labels or identified defects in evidence."""
    base=list(checks(row))
    for i,message in enumerate(row['messages']):
        if message['role']=='user':
            if row['task']!='rewrite':continue
            template=next(c for c in base if c['criterion']=='request_validity' and c['evidence']['target']['turn']==i)
            c=deepcopy(template);c['criterion']='request_preconditions'
            c['id']=c['audit_id']=f'{row["id"]}/precision/request/{i}'
            c['evidence']['target_text']=message['content'];yield c
            continue
        template=next(c for c in base if c['criterion']=='answer_language' and c['evidence']['target']['turn']==i)
        for j,text in enumerate(re.split(r'\n\s*\n',message['content'])):
            criteria=['paragraph_grammar']
            if row['task'] in ('summary','qa','rewrite'):criteria.append('paragraph_fidelity')
            for criterion in criteria:
                c=deepcopy(template);c['criterion']=criterion
                c['id']=c['audit_id']=f'{row["id"]}/precision/{criterion}/{i}/{j}'
                c['evidence']['target']=dict(field='target_text',turn=i,paragraph=j)
                c['evidence']['target_text']=text
                yield c


class PrecisionAudit(StagedAudit):
    def prepare(self,row):
        request=super().prepare(dict(row,criterion='answer_language'))
        request['messages'][0]['content']=BASE+'\n'+RULES[row['criterion']]+'''
Background seed is provenance only. The named target_text is the sole target;
other supplied context supports interpretation but is not an additional target.
Return only accept or reject. Definite defects remain in scope regardless of severity.'''
        return request
