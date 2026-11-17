"""Post-hoc development combinations of completed reviews; no model requests."""
from itertools import combinations
from pathlib import Path

from dfm12.io import rows, file_hash
from scripts.dfm16_story_calibration import immutable, metrics
from scripts.dfm16_validation_audit import whole_vote
from scripts.queue_dfm16_stories_qwen import audited_records

BASE = Path('data/dfm16')
LOCAL = BASE/'staged-stories-evidence-v8-20261029'
ODIN = BASE/'staged-stories-odin-evidence-v9-20261029'
OUTPUT = BASE/'staged-stories-saved-combinations-v10-20261029'


def analyze():
    reference = list(rows(LOCAL/'reference.jsonl'))
    arms = {'focused_v7':{r['id']:r['decision'] for r in reference}}
    pins = {str(LOCAL/'reference.jsonl'):file_hash(LOCAL/'reference.jsonl')}
    for kind, name in [('direct','flash'),('direct','qwen27b'),('verified','flash')]:
        stage = LOCAL/kind/name
        arms[f'{name}_{kind}'] = {r['id']:v.get('review',{}).get('decision','unresolved')
                                  for r,v in audited_records(stage)}
        for p in stage.glob('audit/quality-*/receipt.json'):
            pins[str(p)] = file_hash(p)
    for name in ('direct','with_evidence'):
        path = ODIN/'scored'/f'{name}.jsonl'
        arms[f'odin_{name}'] = {r['id']:r['decision'] for r in rows(path)}
        pins[str(path)] = file_hash(path)
    reports = []
    for size in range(1,len(arms)+1):
        for names in combinations(arms,size):
            scored = [dict(r,decision=whole_vote(arms[n].get(r['id'],'unresolved') for n in names)
                           if r['deterministic_pass'] else 'reject') for r in reference]
            m = metrics(scored)
            reports.append(dict(arms=names,metrics=m,
                generated_only=metrics([r for r in scored if r['deterministic_pass']]),
                uses_generator_self_review=any(n.startswith('odin_') for n in names)))
    eligible = [r for r in reports if r['metrics']['clean_withholding']['rate']<=.20]
    best = min(eligible,key=lambda r:(r['metrics']['false_acceptance']['numerator'],
                                     r['metrics']['clean_withholding']['numerator'],len(r['arms'])))
    independent = [r for r in eligible if not r['uses_generator_self_review']]
    best_independent = min(independent,key=lambda r:(r['metrics']['false_acceptance']['numerator'],
                                                   r['metrics']['clean_withholding']['numerator'],len(r['arms'])))
    # Distinct missed examples, not individual checks, determine complementarity.
    shared = {}
    for a,b in combinations(arms,2):
        missed_a = {r['id'] for r in reference if r['label']=='bad' and arms[a].get(r['id'])=='accept'}
        missed_b = {r['id'] for r in reference if r['label']=='bad' and arms[b].get(r['id'])=='accept'}
        shared[f'{a} + {b}'] = dict(a_missed=len(missed_a),b_missed=len(missed_b),
                                    both_missed=len(missed_a & missed_b))
    value = dict(scope='Post-hoc adaptive development; 63 combinations of saved complete arms. No new requests.',
        qualified=False,production_authorized=False,
        reference='provisional assistant-manual; failed v7 sample reused',
        best_within_20_percent_withholding=best,
        best_without_generator_self_review=best_independent,
        all_checks_required=reports[-1], reports=reports, shared_misses=shared)
    immutable(OUTPUT/'report.json',value)
    pins[str(Path(__file__))] = file_hash(Path(__file__))
    pins[str(OUTPUT/'report.json')] = file_hash(OUTPUT/'report.json')
    immutable(OUTPUT/'receipt.json',dict(pins=pins,production_authorized=False))
    for key in ('best_within_20_percent_withholding','best_without_generator_self_review','all_checks_required'):
        r=value[key]
        print(key,r['arms'],'FA',r['metrics']['false_acceptance'],
              'CW',r['metrics']['clean_withholding'])
    print('evidence verifier shared misses',shared['flash_verified + odin_with_evidence'])


if __name__=='__main__':analyze()
