"""Compare frozen blind prose labels with independently collected judge votes."""
import hashlib
import json
from pathlib import Path

from dfm12.io import rows, write_json
from scripts.dfm16_judge_ensemble_study import ROOT, save_rows
from scripts.queue_dfm16_stories_qwen import DEFAULT, audited_records

LABELS = Path('docs/reports/odin-ensemble-manual-200-20261028.md')
REPORT = Path('docs/reports/simplestories-ensemble-20261028.md')
COMBINATIONS = [('odin',), ('qwen27b',), ('flash',), ('odin', 'qwen27b'),
                ('odin', 'flash'), ('qwen27b', 'flash'), ('odin', 'qwen27b', 'flash')]


def combine(votes):
    if 'reject' in votes:
        return 'reject'
    return 'accept' if votes and all(v == 'accept' for v in votes) else 'unresolved'


def category(labels):
    return 'bad' if 'bad' in labels else 'borderline' if 'borderline' in labels else 'clear'


def main():
    labels, notes = {}, {}
    for line in LABELS.read_text().splitlines():
        if line.startswith('| H'):
            identifier, language, coherence, note = [s.strip() for s in line.split('|')[1:5]]
            labels[identifier] = [language, coherence]
            notes[identifier] = note
    assert len(labels) == 200
    for i in range(1, 21):
        labels[f'C{i:03}'] = ['clear', 'clear']
    labels['C001'] = ['bad', 'clear']
    labels['C019'] = ['clear', 'bad']
    for i in (3, 4, 12, 14):
        labels[f'C{i:03}'] = ['borderline', 'clear']
    samples = list(rows(ROOT/'samples.jsonl'))
    decisions = {name: {} for name in ('odin', 'qwen27b', 'flash')}
    for name in decisions:
        for source, result in audited_records(ROOT/name):
            decisions[name][source['study_id'], source['aspect']] = result.get('review', {}).get('decision', 'unresolved')
    old = {(s['parent_id'], s['turn_index'], s['aspect']): r.get('review', {}).get('decision', 'unresolved')
           for s, r in audited_records(DEFAULT/'odin-text-units/probe')}
    for s in samples:
        if s['cohort'] == 'current':
            for aspect in ('language', 'coherence'):
                decisions['odin'][s['study_id'], aspect] = old.get((s['parent_id'], s['turn_index'], aspect), 'unresolved')
    records = []
    for s in samples:
        identifier = s['study_id']
        votes = {name: {a: lookup.get((identifier, a), 'unresolved') for a in ('language', 'coherence')}
                 for name, lookup in decisions.items()}
        records.append(dict(s, manual=labels[identifier], manual_category=category(labels[identifier]),
                            note=notes.get(identifier, 'See prior accepted-text review.'), votes=votes,
                            decisions={'+'.join(c): combine([votes[n][a] for n in c for a in ('language', 'coherence')])
                                       for c in COMBINATIONS}))
    save_rows(ROOT/'comparison.jsonl', records)
    summary = {'manual_sha256': hashlib.sha256(LABELS.read_bytes()).hexdigest(), 'cohorts': {}}
    lines = ['# SimpleStories prose judge ensemble comparison', '',
             '2026-10-28. Accept only when every selected judge accepts both language and coherence.', '',
             'Manual labels were frozen before inspecting judge outputs. Clear defects, borderline cases, and clean texts are separated.', '',
             'The fresh sample contains 200 unique parent conversations, one intact assistant text each: 50 Danish, English, Hindi and Japanese. It is drawn from previously conversation-approved candidates, not the raw generation population. The old 20 were selected among Odin accepts. Do not pool these cohorts.', '',
             'This is assistant manual review, not native-speaker certification. Source fidelity, instruction compliance and whole-conversation consistency are outside scope.', '']
    for cohort in ('current', 'holdout'):
        selected = [r for r in records if r['cohort'] == cohort]
        counts = {c: sum(r['manual_category'] == c for r in selected) for c in ('bad', 'clear', 'borderline')}
        stats = {}
        lines += [f'## {cohort}: {len(selected)} texts', '', str(counts), '',
                  '| Judges | Accepted | Clear defects passed | Clean texts rejected | Borderlines passed | Unresolved |',
                  '|---|---:|---:|---:|---:|---:|']
        for combination in COMBINATIONS:
            name = '+'.join(combination)
            passed = [r for r in selected if r['decisions'][name] == 'accept']
            bad = [r['study_id'] for r in passed if r['manual_category'] == 'bad']
            good_rejected = [r['study_id'] for r in selected if r['manual_category'] == 'clear' and r['decisions'][name] == 'reject']
            borderline = sum(r['manual_category'] == 'borderline' for r in passed)
            unknown = sum(r['decisions'][name] == 'unresolved' for r in selected)
            stats[name] = dict(accepted=len(passed), bad_passed=bad, clean_rejected=good_rejected,
                               borderline_passed=borderline, unresolved=unknown)
            lines.append(f'| {name} | {len(passed)} | {len(bad)}/{counts["bad"]} | {len(good_rejected)}/{counts["clear"]} | {borderline}/{counts["borderline"]} | {unknown} |')
        summary['cohorts'][cohort] = dict(counts=counts, combinations=stats)
        lines += ['', '### Defects missed by all three', '']
        for r in selected:
            if r['manual_category'] == 'bad' and r['decisions']['odin+qwen27b+flash'] == 'accept':
                lines.append(f'- {r["study_id"]} ({r["language"]}): {r["note"]}')
    lines += ['', '## Interpretation and reproducibility', '',
              'An intersection mechanically cannot admit more bad texts than its constituent judges on the same fixed votes; the relevant question is how much it catches versus how many clean texts it loses. These judges share blind spots; Flash also generated this corpus, so errors are correlated.', '',
              'Borderlines are excluded from both clear-defect and clean-text denominators. Their accepted count provides a sensitivity bound if a stricter policy considers them defective. Missing/invalid votes never count as accepts.', '',
              'Remote Odin used concurrency 64; HTTP dispatch was reduced to 90 per 61 seconds after account 429 responses, below the 180/minute cap. Local judges used concurrency 128, non-thinking yes/no. No production admission policy or datasets were changed.', '',
              f'Manual label SHA256: `{summary["manual_sha256"]}`.', '',
              f'Frozen inputs, raw audit journals, per-text votes and machine-readable summary: `{ROOT}`.', '',
              'Reproduce aggregation: `python -m scripts.analyze_dfm16_judge_ensemble`.', '',
              '[Manual labels and explanations](odin-ensemble-manual-200-20261028.md).']
    write_json(ROOT/'summary.json', summary)
    REPORT.write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
