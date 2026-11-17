"""Fail-closed, whole-conversation, per-language development and validation gates."""
from collections import Counter
from scripts.dfm16_story_calibration import metrics
from scripts.dfm16_staged_stories import TASKS

MODELS = ('flash','qwen27b','odin')
LABELS = ('clear','bad','borderline','unresolved')


def policy_vote(votes, generator, policy):
    judges = [m for m in MODELS if m != generator]
    if generator not in MODELS: raise ValueError('unknown generator')
    if policy in judges:
        required = [votes.get(policy)]
    elif policy in ('both','either'):
        required = [votes.get(m) for m in judges]
    else: raise ValueError('self-review or unknown policy')
    if any(v not in ('accept','reject') for v in required): return 'unresolved'
    if policy == 'either': return 'reject' if all(v=='reject' for v in required) else 'accept'
    return 'accept' if all(v=='accept' for v in required) else 'reject'


def validate_labels(records):
    if len({r['id'] for r in records}) != len(records): raise ValueError('duplicate conversation')
    for r in records:
        if r['label'] not in LABELS: raise ValueError('invalid whole-conversation label')
        if r['label']=='clear' and not r.get('deterministic_pass',False):
            raise ValueError('clear example violates deterministic contract')


def select_generator(records):
    """20 paired families per language, four per task. First attempts only."""
    validate_labels(records)
    if len({r['language'] for r in records}) != 1: raise ValueError('language pooling forbidden')
    arms = {m:[r for r in records if r['arm']==m] for m in ('legacy',*MODELS)}
    families = None
    assignments = None
    for arm, group in arms.items():
        fs = {r['family'] for r in group}
        if len(group)!=20 or len(fs)!=20 or Counter(r['task'] for r in group)!=Counter({t:4 for t in TASKS}):
            raise ValueError('require all matched development examples')
        if families is not None and fs != families: raise ValueError('unpaired families')
        families=fs
        mapping={r['family']:r['task'] for r in group}
        if assignments is not None and mapping!=assignments:raise ValueError('unmatched task assignments')
        assignments=mapping
    old = sum(r['label']=='clear' for r in arms['legacy'])
    eligible=[]
    for name in MODELS:
        group=arms[name]
        clear=sum(r['label']=='clear' for r in group)
        # User amendment, 2026-10-29: 10/20 is enough to explore audit policies.
        # Task shortfalls and legacy comparisons are diagnostics, not vetoes.
        if clear>=10:
            cost=sum(r['cost'] for r in group)/clear
            elapsed=sum(r['seconds'] for r in group)
            eligible.append((-clear,cost,elapsed,name))
    return min(eligible)[-1] if eligible else None


def select_policy(records,generator):
    validate_labels(records)
    if len({r['language'] for r in records})!=1: raise ValueError('language pooling forbidden')
    development=[r for r in records if r['cohort']=='development']
    controls=[r for r in records if r['cohort']=='controls']
    if len(development)!=20 or len(controls)!=80: raise ValueError('20 development plus 40 whole-conversation pairs required')
    pairs=Counter(r['pair'] for r in controls)
    if len(pairs)!=40 or set(pairs.values())!={2}: raise ValueError('40 pairs required')
    for pair in pairs:
        if {r['label'] for r in controls if r['pair']==pair}!={'clear','bad'}: raise ValueError('clean/defective pairs required')
    candidates=[]; reports={}
    for policy in (*[m for m in MODELS if m!=generator],'both','either'):
        scored=[dict(r,decision=policy_vote(r['votes'],generator,policy) if r['deterministic_pass'] else 'reject') for r in records]
        report=metrics(scored); reports[policy]=report
        if report['point_targets']:
            clear_retained=sum(r['label']=='clear' and r['decision']=='accept' for r in scored)
            candidates.append((report['false_acceptance']['rate'],-clear_retained,policy))
    return dict(policy=min(candidates)[-1] if candidates else None,reports=reports)


def validation_report(records):
    validate_labels(records)
    if len({r['language'] for r in records})!=1: raise ValueError('language pooling forbidden')
    if len({r['family'] for r in records})!=len(records): raise ValueError('dependent families')
    cohorts=Counter(r['cohort'] for r in records)
    if set(cohorts)-{'validation','supplementary'} or cohorts.get('validation')!=800 or cohorts.get('supplementary',800)!=800:
        raise ValueError('one balanced 800 cohort, at most one supplementary cohort')
    for cohort in cohorts:
        if Counter(r['task'] for r in records if r['cohort']==cohort)!=Counter({t:160 for t in TASKS}):
            raise ValueError('unbalanced validation cohort')
    report=metrics(records)
    report['accepted_unresolved_labels']=sum(r['label']=='unresolved' and r['decision']=='accept' for r in records)
    report['first_attempt_clear']=sum(r.get('first_label')=='clear' for r in records)
    report['corrected_clear']=sum(r.get('corrected',False) and r['label']=='clear' for r in records)
    report['residual_defective']=sum(r['label']=='bad' for r in records)
    report['cost']=sum(r.get('cost',0) for r in records) if all('cost' in r for r in records) else None
    report['elapsed_seconds']=sum(r.get('seconds',0) for r in records) if all('seconds' in r for r in records) else None
    tasks={t:metrics([r for r in records if r['task']==t]) for t in TASKS}
    report.update(cohorts={c:metrics([r for r in records if r['cohort']==c]) for c in cohorts},tasks=tasks,qualified=report['demonstrated'] and all(r['point_targets'] for r in tasks.values()),
        production_authorized=False,reference='provisional assistant-manual')
    return report


def supplementary_needed(blind_labels):
    """Only labels, never votes or outcomes; one decision before supplementary sampling."""
    if len(blind_labels)!=800 or any(set(r)-{'id','label'} for r in blind_labels):
        raise ValueError('exactly 800 blinded class labels required')
    if len({r['id'] for r in blind_labels})!=800: raise ValueError('duplicate label')
    if any(r['label'] not in LABELS for r in blind_labels): raise ValueError('invalid label')
    counts=Counter(r['label'] for r in blind_labels)
    return counts['clear']<300 or counts['bad']<100
