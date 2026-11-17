"""Immutable freeze/cohort receipts for independent language qualification.

No function here changes any dataset admission policy. Failed validation is
recorded as development evidence; modifications require a new untouched cohort.
"""
from collections import Counter
import random
from dfm12.io import file_hash,load,rows
from scripts.dfm16_story_calibration import immutable,immutable_rows,sha
from scripts.dfm16_staged_stories import TASKS,LANGUAGES
from scripts.dfm16_language_qualification import validation_report,supplementary_needed,policy_vote


def freeze(root,language,generator,policy,artifacts,screen,policy_report):
    if language not in LANGUAGES or screen['selected'].get(language)!=generator:
        raise ValueError('language did not pass generator development screening')
    if policy_report['policy'] is None or policy_report['policy']!=policy:
        raise ValueError('language did not pass policy development selection')
    if not policy_report['reports'][policy]['point_targets']:
        raise ValueError('development targets failed')
    policy_vote({m:'accept' for m in ('flash','qwen27b','odin')},generator,policy)
    pins={str(p):file_hash(p) for p in artifacts}
    required={'design.json','reviewed.jsonl','manual-labels.jsonl','controls.jsonl','votes.jsonl',
              'excluded-families.jsonl','inspected-candidate-inventory.jsonl'}
    if not required.issubset({p.name for p in artifacts}):
        raise ValueError('freeze design, sources, labels, controls and votes')
    value=dict(language=language,generator=generator,policy=policy,artifacts=pins,
        screening_sha256=sha(screen),policy_report_sha256=sha(policy_report),production_authorized=False)
    immutable(root/language/'freeze.json',value)
    return value


def verify_freeze(root,language):
    value=load(root/language/'freeze.json')
    for path,digest in value['artifacts'].items():
        from pathlib import Path
        if file_hash(Path(path))!=digest:raise ValueError('frozen artifact changed')
        if Path(path).name=='design.json':
            for code,expected in load(Path(path))['software'].items():
                if file_hash(Path(code))!=expected:raise ValueError('frozen software changed')
    return value


def cohort(root,language,pool,excluded,seed,supplementary=False):
    """Draw using family IDs only; exclude every historical inspected variant.

    `excluded` is the union of prior generation, source inspection, manual labels,
    and development families; callers must retain the complete inventory receipt.
    """
    frozen=verify_freeze(root,language)
    from pathlib import Path
    excluded=set(excluded)
    for path in frozen['artifacts']:
        if Path(path).name in ('reviewed.jsonl','excluded-families.jsonl','inspected-candidate-inventory.jsonl'):
            excluded.update(r['family'] for r in rows(Path(path)))
    name='supplementary' if supplementary else 'validation'
    if supplementary:
        trigger=load(root/language/'supplementary-trigger.json')
        if not trigger['needed']:raise ValueError('supplementary cohort not authorized by blinded counts')
        excluded=set(excluded)|{r['family'] for r in rows(root/language/'validation/families.jsonl')}
    eligible={r['family']:r for r in pool if r['language']==language and r['family'] not in excluded}
    families=sorted(eligible)
    random.Random(seed).shuffle(families)
    if len(families)<800:raise ValueError('insufficient untouched families')
    selected=[dict(eligible[f],task=TASKS[i//160],cohort=name) for i,f in enumerate(families[:800])]
    immutable_rows(root/language/name/'families.jsonl',selected)
    immutable(root/language/name/'selection-receipt.json',dict(freeze_sha256=sha(frozen),
        excluded_sha256=sha(sorted(excluded)),eligible_sha256=sha(sorted(eligible)),seed=seed,count=800))
    return selected


def supplementary_trigger(root,language,labels):
    verify_freeze(root,language)
    expected={r['id'] for r in rows(root/language/'validation/blind-packet.jsonl')}
    if {r['id'] for r in labels}!=expected:raise ValueError('class labels must cover initial cohort')
    if (root/language/'validation/votes.jsonl').exists():raise ValueError('supplementary decision must precede exposing votes')
    value=dict(needed=supplementary_needed(labels),counts=dict(Counter(r['label'] for r in labels)),labels_sha256=sha(labels))
    immutable(root/language/'supplementary-trigger.json',value)
    return value


def report(root,language,records):
    frozen=verify_freeze(root,language)
    if any(r['language']!=language for r in records):raise ValueError('wrong language')
    for r in records:
        expected=policy_vote(r['votes'],frozen['generator'],frozen['policy']) if r['deterministic_pass'] else 'reject'
        if expected!=r['decision']:raise ValueError('decision does not match frozen policy')
    names={r['cohort'] for r in records}
    if 'supplementary' in names:
        if not load(root/language/'supplementary-trigger.json')['needed']:
            raise ValueError('supplementary cohort lacked blinded count trigger')
    for name in names:
        selected=list(rows(root/language/name/'families.jsonl'))
        actual=[r for r in records if r['cohort']==name]
        if {(r['family'],r['task']) for r in selected}!={(r['family'],r['task']) for r in actual}:
            raise ValueError('report does not match the frozen sampled families')
    value=validation_report(records)
    if not value['class_counts_sufficient'] and 'supplementary' not in names:
        raise ValueError('initial class counts insufficient: complete the one predeclared supplementary cohort')
    value['freeze_sha256']=sha(frozen)
    value['validation_lifecycle']='qualified_candidate_only' if value['qualified'] else 'failed_sample_is_now_development'
    immutable(root/language/'reports/qualification.json',value)
    immutable_rows(root/language/'candidate-manifest.jsonl',[
        dict(id=r['id'],family=r['family'],language=language,production_authorized=False)
        for r in records if value['qualified'] and r['decision']=='accept'])
    return value
