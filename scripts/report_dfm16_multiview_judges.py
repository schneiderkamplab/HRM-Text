"""Report separate audit scopes without pretending unlabelled views have ground truth."""
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
import sys
import time

from dfm12.io import file_hash, load, rows, write_json
from scripts.analyze_dfm16_judge_ensemble import LABELS, category, combine
from scripts.dfm16_judge_ensemble_study import ROOT as PREVIOUS, save_rows
from scripts.prepare_dfm16_multiview_judges import ROOT
from scripts.queue_dfm16_stories_qwen import audited_records


def manual_check_stats(checks, labels, votes):
    """Compare only labelled checks; retain ambiguity and invalid votes separately."""
    counts = Counter()
    for check in checks:
        label = labels.get(check['id'])
        if label is None:
            continue
        decision = votes.get(check['id'], 'unresolved')
        if decision not in ('accept', 'reject'):
            decision = 'unresolved'
        counts[label['label'], decision] += 1
    return {
        'labelled': sum(counts.values()),
        'bad': sum(counts['bad', d] for d in ('accept', 'reject', 'unresolved')),
        'bad_accepted': counts['bad', 'accept'],
        'clear': sum(counts['clear', d] for d in ('accept', 'reject', 'unresolved')),
        'clear_rejected': counts['clear', 'reject'],
        'borderline': sum(counts['borderline', d] for d in ('accept', 'reject', 'unresolved')),
        'borderline_accepted': counts['borderline', 'accept'],
        'unresolved': sum(counts[label, 'unresolved'] for label in ('bad', 'clear', 'borderline')),
    }


def main():
    models = ('odin', 'qwen27b', 'flash', 'mimir')
    checks = list(rows(ROOT/'checks.jsonl'))
    votes = {}
    for model in models:
        stage = ROOT/model/('probe' if model == 'mimir' else '')
        state = stage/'audit/pipeline/state.json'
        if not state.exists() or load(state)['phase'] != 'complete':
            votes[model] = {}
            continue
        votes[model] = {s['id']: r.get('review', {}).get('decision', 'unresolved')
                        for s,r in audited_records(stage)}
    units = defaultdict(list)
    for c in checks:
        units[(c['study_id'], c['view'], c['view_index'])].append(c['id'])
    counts = Counter()
    units_out = []
    for (identifier,view,index), ids in units.items():
        decisions = {m: combine([votes[m].get(i, 'unresolved') for i in ids]) for m in models}
        for model,decision in decisions.items():
            counts[model, view, decision] += 1
        units_out.append(dict(study_id=identifier, view=view, index=index, decisions=decisions))
    save_rows(ROOT/'unit-decisions.jsonl', units_out)
    labels = {}
    for line in LABELS.read_text().splitlines():
        if line.startswith('| H'):
            fields = [s.strip() for s in line.split('|')[1:]]
            labels[fields[0]] = category(fields[1:3])
    selected = {s['study_id']: s['turn_index'] for s in rows(PREVIOUS/'samples.jsonl') if s['cohort']=='holdout'}
    comparable = [u for u in units_out if u['view']=='message' and u['index']==selected[u['study_id']]]
    assert len(comparable) == 200
    lines = ['# Atomic multiview judge comparison', '',
        'Same 200 parent conversations. One binary question per request; no explanations or JSON.', '',
        'All view acceptance requires every applicable criterion to pass. Unresolved includes missing, invalid or over-context results; an unfinished model is reported entirely unresolved until its journals are finalized.', '',
        '## Per-view coverage', '', '| Model | View | Accept | Reject | Unresolved |', '|---|---|---:|---:|---:|']
    for model in models:
        for view in ('seed','message','conversation','message_pair','exchange_pair'):
            lines.append('| '+model+' | '+view+' | '+' | '.join(str(counts[model,view,d]) for d in ('accept','reject','unresolved'))+' |')
    lines += ['', '## Frozen manual subset: 200 assistant messages', '',
        '40 definite defects, 134 clean, 26 borderline. These are the earlier holistic assistant manual labels, not native-speaker certification. The expanded criterion-specific review below is separate and does not overwrite these historical labels.', '',
        '| Judges | Accepted | Defects accepted / 40 | Clean rejected / 134 | Borderlines accepted / 26 | Unresolved |',
        '|---|---:|---:|---:|---:|---:|']
    stats = {}
    for size in range(1,5):
        for chosen in combinations(models,size):
            c = Counter()
            for u in comparable:
                decision = combine([u['decisions'][m] for m in chosen])
                c[decision] += 1
                c[labels[u['study_id']],decision] += 1
            name = '+'.join(chosen)
            stats[name] = dict(accepted=c['accept'], bad_accepted=c['bad','accept'], clean_rejected=c['clear','reject'],
                              borderline_accepted=c['borderline','accept'], unresolved=c['unresolved'])
            lines.append(f'| {name} | '+ ' | '.join(str(n) for n in stats[name].values())+' |')
    expanded = {}
    manual_path = ROOT/'manual-labels.jsonl'
    if manual_path.exists():
        manual_rows = list(rows(manual_path))
        manual = {r['id']: r for r in manual_rows}
        assert len(manual) == len(manual_rows), 'Duplicate manual check IDs'
        assert set(manual) <= {c['id'] for c in checks}, 'Unknown manual check IDs'
        checksum = file_hash(ROOT/'checks.jsonl')
        assert all(r['source_sha256'] == checksum for r in manual_rows), 'Manual source mismatch'
        lines += ['', '## Expanded blind manual review', '',
            'Assistant manual judgments of seeds, every message, full conversations and adjacent windows. Not independent native-speaker certification. Grammar, clarity, consistency and compliance are distinct questions; borderline cases are not definite defects. Repeated views are correlated, so these are check counts, not independent sample sizes or production rejection rates.', '',
            '[Annotation source](dfm16-multiview-manual-labels.json). Rebuild with `python -m scripts.dfm16_manual_multiview`.', '',
            '| Model | View | Labelled checks | Defects | Defects accepted | Clear | Clear rejected | Borderline | Borderline accepted | Unresolved |',
            '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
        for model in models:
            for view in ('seed', 'message', 'conversation', 'message_pair', 'exchange_pair'):
                result = manual_check_stats([c for c in checks if c['view'] == view], manual, votes[model])
                expanded[model+'/'+view] = result
                lines.append('| '+model+' | '+view+' | '+' | '.join(str(v) for v in result.values())+' |')
    write_json(ROOT/'comparison-summary.json', dict(manual_subset=stats, expanded_manual=expanded,
        coverage={'/'.join(k):v for k,v in counts.items()}, production_authorized=False))
    Path('docs/reports/simplestories-atomic-multiview-20261028.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    if '--wait' in sys.argv:
        while load(ROOT/'campaign.json')['phase'] == 'running':
            time.sleep(30)
    main()
