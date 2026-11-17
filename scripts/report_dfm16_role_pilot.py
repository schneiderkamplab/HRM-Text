"""Summarize development paired controls and independently labeled generation."""
from collections import Counter,defaultdict
from pathlib import Path
from dfm12.io import load,rows,file_hash,write_json
from scripts.dfm16_role_pilot import ROOT,OLD
from scripts.queue_dfm16_stories_qwen import audited_records

def main():
 controls=load(ROOT/'control-report.json');lines=['# SimpleStories role and source diagnostic pilot','',
 'Development only. References are provisional assistant-manual assessments; no validation or production admission.','',
 '## Matched targeted checks','',
 '| Judge | Prompt | Defective targets accepted / 28 | Clean targets withheld / 28 | Both members correct / 28 pairs |',
 '|---|---|---:|---:|---:|']
 for judge,variants in controls['judges'].items():
  for variant,data in variants.items():
   a=data['aggregate'];m=a['targeted_metrics'];lines.append(f'| {judge} | {variant} | {m["false_acceptance"]["numerator"]} | {m["clean_withholding"]["numerator"]} | {a["pairs_both_correct"]} |')
 lines+=['','These are targeted synthetic controls, not whole-conversation false-acceptance estimates. Each language contributes seven pairs. Source coherence adds coverage absent from the legacy seed check; differences are not attributable to wording alone.','',
 '| Check | Qwen old → role pairs correct | Flash old → role | Odin old → role |','|---|---:|---:|---:|']
 for criterion in next(iter(controls['judges'].values()))['role']['by_criterion']:
  values=[]
  for judge in ('qwen27b','flash','odin'):
   v=controls['judges'][judge];values.append(f'{v["legacy"]["by_criterion"][criterion]["pairs_both_correct"]} → {v["role"]["by_criterion"][criterion]["pairs_both_correct"]} / {v["role"]["by_criterion"][criterion]["pairs"]}')
  lines.append('| '+criterion+' | '+' | '.join(values)+' |')
 details=dict(controls=controls,production_authorized=False)
 labelsfile=ROOT/'generation-manual-labels.jsonl'
 if labelsfile.exists():
  labels=list(rows(labelsfile));packets={r['id']:r for r in rows(ROOT/'generation-blind-packet.jsonl')}
  assert len(labels)==len(packets)==32 and {r['id'] for r in labels}==set(packets)
  assert all(r['reviewer']=='assistant-manual' and r['blind_to_judge_verdicts'] and r['note'] for r in labels)
  groups={}
  for language in ('da','en','hi','ja'):
   for condition in ('original','clean'):
    subset=[r for r in labels if r['id'].endswith('-'+condition) and packets[r['id']]['language']==language]
    groups[language+'/'+condition]=dict(n=len(subset),labels=dict(Counter(r['label'] for r in subset)),generated_turn_labels=dict(Counter(r['generated_label'] for r in subset)),
      defects=dict(Counter(d for r in subset for d in r['defect_locations'])))
  origins=load(ROOT/'generation-origin-assessment.json')['records']
  details['generation']=dict(origin_counts=dict(new_definite_defects=sum(v['new_definite_generated_defect'] is True for v in origins.values()),inherited_user_source_defects=sum(v['inherited_source_defect_in_user'] for v in origins.values())),groups=groups,labels_sha256=file_hash(labelsfile),packet_sha256=file_hash(ROOT/'generation-blind-packet.jsonl'),
      note='Two changed source families, two identical-source controls; no population effect or independent-trial confidence claim.')
  lines+=['','## First-attempt generation','',
   '| Language / input | Clear | Defective | Borderline | No candidate |','|---|---:|---:|---:|---:|']
  for group,data in groups.items():
   c=data['labels'];lines.append(f'| {group} | {c.get("clear",0)} | {c.get("bad",0)} | {c.get("borderline",0)} | {c.get("unresolved",0)} |')
  lines+=['','| Language / input | Generated turns clear | Generated turns defective | Generated turns borderline |','|---|---:|---:|---:|']
  for group,data in groups.items():
   c=data['generated_turn_labels'];lines.append(f'| {group} | {c.get("clear",0)} | {c.get("bad",0)} | {c.get("borderline",0)} |')
  lines+=['',f'Newly introduced definite defects: {details["generation"]["origin_counts"]["new_definite_defects"]} outputs; copied defective source passages: {details["generation"]["origin_counts"]["inherited_user_source_defects"]} outputs (overlap allowed). Three missing candidates remain unknown semantically.', '', 'Whole-example labels include supplied seed quality. Separate `defect_locations` distinguish original input, generated user/source, assistant, and deterministic contract failures. No generation was repaired or retried.','',
   'Only Danish H001 (English source with an unexplained map) and Hindi H101 changed between conditions. English H051 and Japanese H151 are identical-source stochastic controls. Four task outputs per seed are correlated. This tiny convenience experiment cannot establish a population-level cleaning benefit.']
 tokens=Counter();output=ROOT/'control-votes/odin'
 for _,r in audited_records(output):tokens.update({k:v for k,v in r.get('review_response',{}).get('usage',{}).items() if isinstance(v,(int,float))})
 rates={r['unit']:float(r['price']) for r in load(OLD/'provider-pricing.json')['prices']}
 cost=tokens['prompt_tokens']*rates['input_token']+tokens['completion_tokens']*rates['output_token']
 details['odin']=dict(recorded_usage=dict(tokens),estimated_dkk=cost,timing=load(output/'timing.json'))
 lines+=['','## Interpretation and next development step','',
 'Role-specific checks help on these simple controls, especially Flash, but do not qualify a filter. Flash has 1/28 defective accepts and 3/28 clean withheld; the corresponding one-sided 95% upper bounds are 15.9% and 25.4%. Request validity and authoritative-source selection remain unresolved design problems.',
 'Clean inputs do not prevent generation errors. The English clean-condition QA answer says before departure while quoting a sequence that places the event after departure. Danish generation introduces malformed grammar from cleaned English source. Hindi generation introduces दिए गए कहानी even with a grammatical source. Eleven of 29 parseable conversations fail the existing deterministic contract before any semantic judgment.',
 'Recommended next development change: use vetted native-language request templates and an explicit authoritative source; generate one answer or one edited paragraph per request; construct preservation and selective undo mechanically; count lengths before acceptance. Compare that staged generator against the current whole-conversation generator on additional development seeds. Keep the simpler role-specific checks, but test source-selection explicitly before any new holdout. No such new generator or production policy has been deployed here.']
 lines+=['','## Operations and limits','',f'Recorded Odin usage estimate: {cost:.4f} DKK at the previously retrieved provider list prices; not an invoice, excludes missing retry/failure usage and local GPU cost. Actual sends capped at 100 per rolling minute, including retries. Local concurrency 128, Odin 64. Existing shared runtime, journals and receipts used; servers unchanged.','',
 'Verification: 32 focused/runtime/limiter tests passed. All three control stages and the generation stage completed with verified receipts. The worker exited and controller lock was released. Repository OKF validation retains an unrelated oversized concept and 15 pre-existing link warnings.', '', 'Prompts, references, inputs and code were frozen before votes in `design.json`. Full per-language/criterion control metrics and one-sided confidence bounds are in `control-report.json`; pair totals, not overlapping checks, are the diagnostic comparison unit. Validation remains untouched.']
 write_json(ROOT/'diagnostics.json',details)
 dest=Path('docs/reports/simplestories-role-source-pilot-20261028.md');dest.write_text('\n'.join(lines)+'\n');print(dest)

if __name__=='__main__':main()
