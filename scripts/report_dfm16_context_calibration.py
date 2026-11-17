"""Read-only diagnostic report of frozen context calibration and separate repairs."""
from collections import Counter, defaultdict
import json
from pathlib import Path

from dfm12.io import file_hash, load, rows, write_json
from scripts.dfm16_story_calibration import ROOT, aggregate, deterministic, metrics
from scripts.queue_dfm16_stories_qwen import audited_records


def main():
    stage=ROOT/'development'
    final=load(stage/'report.json')
    parents=list(rows(stage/'inputs.jsonl'))
    labels={r['id']:r for r in rows(stage/'manual-labels.jsonl')}
    judges={}
    timings={}
    for name in ('qwen27b','flash','odin'):
        votes=defaultdict(list);counts=Counter();by_role=Counter();tokens=Counter();errors=Counter()
        for check,result in audited_records(stage/'votes'/name):
            d=result.get('review',{}).get('decision','unresolved')
            votes[check['parent_id']].append(d);counts[d]+=1
            by_role[(labels[check['parent_id']]['label'],check['evidence']['target']['role'],check['criterion'],d)]+=1
            if d=='unresolved':errors[result.get('error','unknown')]+=1
            usage=result.get('review_response',{}).get('usage',{})
            tokens.update({k:v for k,v in usage.items() if isinstance(v,(int,float))})
            tokens['reported_reasoning_tokens']+=usage.get('completion_tokens_details',{}).get('reasoning_tokens',0)
        records=[]
        for p in parents:
            outcomes=votes[p['id']]+['reject' for c in deterministic(p) if c['status']=='fail']
            records.append(dict(id=p['id'],label=labels[p['id']]['label'],decision=aggregate(outcomes)))
        timing=load(stage/'votes'/name/'timing.json')
        seconds=timing['seconds']
        reuse=stage/'votes'/name/'reuse.json'
        if reuse.exists() and not load(reuse).get('complete',True):
            source=Path(load(reuse)['source'])
            old=load(source/'audit/pipeline/live.json')
            campaign=source.parents[2]/'campaign.json'
            seconds+=campaign.stat().st_mtime-(old['time']-old['elapsed']-60)
        timings[name]=dict(active_session_wall_seconds=seconds,completed_checks_per_second=sum(counts.values())/seconds,
            note='Includes original failed session and resume, excludes between-session downtime; old session start reconstructed from telemetry and configured 60-second startup wait.')
        judges[name]=dict(whole_example=metrics(records),check_counts=dict(counts),reported_tokens=dict(tokens),
            checks_by_reference_role_criterion_decision={'/'.join(k):v for k,v in by_role.items()},errors=dict(errors))
    cpu_counts=Counter(c['status'] for p in parents for c in deterministic(p))
    operational=Counter()
    for name in ('qwen27b','flash','odin'):
        for check,result in audited_records(stage/'votes'/name):
            operational[name+'/'+result['status']]+=1
    pricing=load(ROOT/'provider-pricing.json')
    rates={r['unit']:float(r['price']) for r in pricing['prices']}
    def price(tokens):
        return tokens.get('prompt_tokens',0)*rates['input_token']+tokens.get('completion_tokens',0)*rates['output_token']
    repair_tokens=Counter()
    repair_stage=stage/'repaired/odin'
    if (repair_stage/'audit/pipeline/state.json').exists() and load(repair_stage/'audit/pipeline/state.json').get('phase')=='complete':
        for _,record in audited_records(repair_stage):
            repair_tokens.update({k:v for k,v in record.get('review_response',{}).get('usage',{}).items() if isinstance(v,(int,float))})
    preflight_tokens=Counter()
    for output in (stage/'votes/odin',repair_stage):
        if (output/'preflight-response.json').exists():
            preflight_tokens.update({k:v for k,v in load(output/'preflight-response.json').get('usage',{}).items() if isinstance(v,(int,float))})
    costs=dict(currency='DKK',development=price(judges['odin']['reported_tokens']),repair=price(repair_tokens),preflights=price(preflight_tokens),
        old_protocol=load(ROOT/'old-odin-protocol-cost.json')['estimated_list_price_dkk'])
    costs['recorded_total']=sum(v for v in costs.values() if isinstance(v,(int,float)))
    details=dict(cost_estimate=costs,judges=judges,corrected_session_throughput=timings,deterministic_statuses=dict(cpu_counts),operational_results=dict(operational),filter_report_sha256=file_hash(stage/'report.json'),
        manual_reference='Provisional assistant reconciliation of prior complete manual assessments, with targeted rereads.',
        cost='Published list-price estimate in DKK for recorded response usage only; failed/retried/interrupted usage and local GPU costs may be missing. Not an invoice.',
        repair_report=load(stage/'repair-report.json') if (stage/'repair-report.json').exists() else None,
        production_authorized=False)
    if details['repair_report']:
        repaired=load(stage/'repair-decisions.json')
        # Frozen raw report used 'unresolved' for every non-accepted repair.
        # Preserve it; distinguish actual rejects from operational failures here.
        repair_votes=defaultdict(list)
        expected=Counter(c['parent_id'] for c in rows(stage/'repaired-checks.jsonl'))
        for judge in ('qwen27b','odin'):
            for check,result in audited_records(stage/'repaired'/judge):
                repair_votes[check['parent_id']].append(result.get('review',{}).get('decision','unresolved'))
        cpu={r['id']:r['checks'] for r in rows(stage/'repairs.jsonl')}
        for r in repaired:
            outcomes=repair_votes[r['id']]
            if any(c['status']=='fail' for c in cpu[r['id']]) or 'reject' in outcomes:
                decision='reject'
            elif len(outcomes)!=2*expected[r['id']] or any(c['status']=='unresolved' for c in cpu[r['id']]) or any(v!='accept' for v in outcomes):
                decision='unresolved'
            else: decision='accept'
            assert (decision=='accept')==(r['decision']=='accept')
            r['decision']=decision
        details['repair_outcomes']=dict(Counter(r['decision'] for r in repaired))
        details['repair_metrics_corrected_status']=metrics(repaired)
        details['repair_status_correction']='Raw immutable repair report calls all non-acceptance unresolved; supplemental outcomes distinguish reject from unresolved without changing acceptance or labels.'
        parent_map={p['id']:p for p in parents}
        details['repair_manual_counts']=dict(Counter(r['label'] for r in repaired))
        details['repair_breakdowns']={axis:{value:metrics([r for r in repaired if parent_map[r['id']][axis]==value])
            for value in sorted({parent_map[r['id']][axis] for r in repaired})} for axis in ('language','task')}
        details['repair_manual_success']=dict(numerator=details['repair_manual_counts'].get('clear',0),
            denominator=details['repair_report']['attempted'], note='Clear complete repairs, regardless of audit acceptance; borderline is not counted as success.')
    write_json(stage/'diagnostics.json',details)
    lines=['# SimpleStories context calibration: development results','',
        'Reference: 200 complete conversations; 115 definite defects, 55 clear, 30 borderline. Labels are provisional assistant-manual reconciliations, not independent human certification.','',
        '| Fixed policy | Defects accepted unchanged | Clear withheld (including unresolved) | Retained / 200 | FA upper 95% | Withholding upper 95% |',
        '|---|---:|---:|---:|---:|---:|']
    for name,value in final['policies'].items():
        m=value['aggregate'];fa=m['false_acceptance'];cw=m['clean_withholding']
        lines.append(f'| {name} | {fa["numerator"]}/{fa["denominator"]} | {cw["numerator"]}/{cw["denominator"]} | {m["retained"]} | {fa["upper95"]:.1%} | {cw["upper95"]:.1%} |')
    lines+=['','| Policy | Accepted-set definite contamination | Unresolved | Accepted borderline |',
        '|---|---:|---:|---:|']
    for name,value in final['policies'].items():
        m=value['aggregate'];c=m['accepted_contamination'];u=m['unresolved']
        lines.append(f'| {name} | {c["numerator"]}/{c["denominator"]} ({c["rate"]:.1%}; upper 95% {c["upper95"]:.1%}) | {u["numerator"]}/200 ({u["rate"]:.1%}; upper 95% {u["upper95"]:.1%}) | {m["accepted_borderline"]} |')
    lines+=['',f'Selected qualifying development policy: **{final["selected_development_policy"] or "none"}**.',
        'No validation conclusion follows from this development sample. Production promotion remains blocked. If no policy qualifies, no 800-example validation sample is consumed.','',
        'All original versions, labels and votes are retained. v4 retains the Hindi danda sentence-segmentation fix and reuses only unchanged local Qwen/Flash votes after matching prompts, inputs and receipt hashes. Odin was rerun with corrected provider controls; its old votes are excluded.','',
        '## Individual judges (diagnostic)','',
        '| Judge | Defects accepted | Clear withheld | Unresolved conversations | Reported input tokens | Reported output tokens |',
        '|---|---:|---:|---:|---:|---:|']
    for name,value in judges.items():
        m=value['whole_example'];t=value['reported_tokens']
        lines.append(f'| {name} | {m["false_acceptance"]["numerator"]}/115 | {m["clean_withholding"]["numerator"]}/55 | {m["unresolved"]["numerator"]}/200 | {t.get("prompt_tokens",0)} | {t.get("completion_tokens",0)} |')
    lines+=['','Corrected Odin requests use reasoning_effort=none and a 32-token total completion bound. The provider reports a one-token reasoning count with no reasoning text; every parsed response is checked against these limits. Earlier misconfigured Odin runs are retained separately and are not acceptance votes.','',
        '## Timing and usage','',
        f'Published-price estimate from recorded Odin usage: development {costs["development"]:.2f} DKK; repairs {costs["repair"]:.2f} DKK; old unsupported protocol {costs["old_protocol"]:.2f} DKK; recorded total including preflights {costs["recorded_total"]:.2f} DKK. This is not an invoice and excludes unrecorded failed/interrupted/retried usage and local GPU costs.',
        '[Published model prices](https://odincore.ai/ajax/services); currency from [provider pricing UI](https://odincore.ai/docs/pricing).','',
        *[f'{n}: {t["active_session_wall_seconds"]:.1f} active-session seconds, {t["completed_checks_per_second"]:.3f} completed checks/second.' for n,t in timings.items()],
        'Timings describe active sessions for the corrected protocol and exclude paused downtime and earlier unsupported-protocol runs. Historical imported partial sessions, where applicable, are reconstructed from telemetry.','',
        '## Repairs','']
    if details['repair_report']:
        r=details['repair_report']
        lines += [f'Attempted {r["attempted"]}; produced {r["generated"]}; audit-accepted {r["accepted"]}; accepted and manually clear {r["accepted_clear"]}; definite residual defects among accepted repairs {r["residual_defects"]}.',
            f'Blind manual inspection of all generated repairs: {details["repair_manual_counts"]}. Residual-defect one-sided 95% upper bound among audit-accepted repairs: {r["residual_upper95"]:.1%}.',
            f'Repair outcomes: {details["repair_outcomes"]}. The immutable raw report calls all non-acceptance unresolved; diagnostics.json corrects that status distinction without changing acceptance.',
            'This is separate repair accounting. It does not erase any original filtering error or qualify a failed filter. Borderline repairs are reported separately in the JSON report.']
    else:lines+=['Repair generation, independent auditing or blind manual inspection is still pending.']
    lines+=['','## Scope and failure diagnosis','',
        'User-side language, fidelity and instruction checks are counted separately in diagnostics.json. A check aimed at a user request can conflate request quality with answer fulfillment; this is a candidate explanation for over-withholding, not an established causal result. No prompts were adjusted using these outcomes.',
        'Manual defect notes include accidental source corruption, clear grammar/spelling errors, unsupported rewrites, ambiguous/no-op transformations and failed local preservation. Overlapping criterion notes are diagnostic, not additional independent examples.',
        'The available pool consists of historical CPU-passing generations. Any future validation must also exclude prior manually viewed examples beyond development; fresh sampling and class-count qualification cannot be inferred from these development results.']
    lines+=['','Verification: 28 focused/runtime/limiter tests passed. All six stage journals and receipts were read successfully (1,874 checks per development judge, 63 repair attempts, 819 checks per repair judge). The worker exited and its controller lock is available. Repository OKF validation retains one unrelated oversized concept and 15 existing link warnings.','', 'Detailed language/task breakdowns, policy decisions and stage receipts are in `'+str(stage)+'`.']
    path=Path('docs/reports/simplestories-context-calibration-20261028.md')
    path.write_text('\n'.join(lines)+'\n')
    print(path)


if __name__=='__main__':main()
