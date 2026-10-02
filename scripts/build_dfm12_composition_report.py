#!/usr/bin/env python3
"""Combine measured source accounting and corruption evidence into two pages."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from scripts.multilingual_family_report import LANGUAGES
from scripts.training_composition_latex import render


FAMILIES = [('instruction_following', 'Instr. follow.'), ('common_sense', 'Commonsense'),
            ('gec', 'Correction'), ('acceptability', 'Acceptability'),
            ('summary', 'Summary'), ('qa', 'Reading QA'), ('knowledge', 'Knowledge'),
            ('ner', 'NER'), ('sentiment', 'Sentiment'),
            ('mixed_instruction_unclassified', 'Mixed SFT')]


def millions(value):
    return f'{value / 1e6:,.3f}' if value is not None else None


def composition_page(data):
    recovered = bool(data.get('inherited_source_recovery'))
    grouped = defaultdict(dict)
    row_counts = defaultdict(dict)
    total_tokens = data['totals']['combined']['rendered_tokens']
    total_rows = data['totals']['combined']['rows']
    def cell(tokens, count):
        if tokens is None:
            return None
        return f'{tokens / 1e6:,.3f} ({100 * tokens / total_tokens:.3f}% / {100 * count / total_rows:.3f}%)'
    for row in data['language_family_rows']:
        grouped[row['language']][row['family']] = row['rendered_tokens']
        row_counts[row['language']][row['family']] = row['rows']
    represented = {family for family, _ in FAMILIES}
    rows = []
    for lang, name in LANGUAGES.items():
        groups = grouped[lang]
        counts = row_counts[lang]
        other = sum(value or 0 for family, value in groups.items() if family not in represented)
        total = sum(value or 0 for value in groups.values())
        rows.append([name, *[cell(groups.get(family), counts.get(family) or 0) for family, _ in FAMILIES],
                     cell(other, sum(n or 0 for f, n in counts.items() if f not in represented)),
                     cell(total, sum(n or 0 for n in counts.values()))])
    unknown_groups = defaultdict(lambda: defaultdict(int))
    unknown_counts = defaultdict(lambda: defaultdict(int))
    for row in data['unknowns']:
        unknown_groups[row['component']][row['family']] += row['rendered_tokens']
        unknown_counts[row['component']][row['family']] += row['rows']
    for component, groups in unknown_groups.items():
        counts = unknown_counts[component]
        name = ('Inherited DFM11' if not recovered else 'Base: language unassigned') if component == 'inherited_dfm11' else 'Additions: language unassigned'
        rows.append([name, *[cell(groups.get(f), counts.get(f, 0)) for f, _ in FAMILIES],
                     cell(sum(n for f, n in groups.items() if f not in represented), sum(n for f, n in counts.items() if f not in represented)),
                     cell(sum(groups.values()), sum(counts.values()))])
    all_tokens = data['totals']['combined']['rendered_tokens']
    inherited_missing = not recovered
    provenance_note = ('The inherited sampled DFM11 store has no locally recoverable source-offset map. Its entire token count is retained as unallocated rather than omitted or guessed.'
                       if inherited_missing else
                       'Inherited source attribution was recovered from the originating machine and reconciled against the sampled epoch. Broad sources still need semantic task labels; recovered provenance is not a claim that every conversation has been classified.')
    return dict(title='DFM12 XL epoch 11: traceable training composition by language',
                description='Each cell: million rendered tokens (percentage of ALL epoch tokens / percentage of ALL epoch rows). Input + response + template; identity repeat 0. Dedicated family allocations are lower bounds, not a full semantic census.',
                columns=['Language/source block', *[label for _, label in FAMILIES], 'Other/mixed', 'Allocated total'],
                rows=rows,
                notes=[f'Full sampled epoch: {all_tokens:,} tokens. Base DFM11: {data["totals"]["inherited_dfm11"]["rendered_tokens"]:,}; DFM12 additions: {data["totals"]["dfm12_additions"]["rendered_tokens"]:,}.',
                       'A dash means unavailable family attribution, NOT zero training exposure. Language-row totals exclude unassigned-language sources' + (' and inherited DFM11.' if inherited_missing else '.'),
                       'Mixed SFT is broad instruction/chat supervision without a validated family split. Other/mixed includes translation, math/code, tool use, text transformations, general reasoning, and combined summary/rewrite. General reasoning is not automatically commonsense reasoning.',
                       'Bilingual translation tokens are not arbitrarily split between source and target languages. Unspecified Norwegian is not silently assigned to Bokmal or Nynorsk.',
                       provenance_note,
                       'Exact per-source row, rendered-token and response-token counts, provenance, and classification rationale are in dfm12_training_composition.json. These allocations do not measure causal contribution to evaluation scores.'])


def error_page(data):
    if data['status'] == 'in_progress':
        raise ValueError('Refusing to render incomplete corruption statistics')
    rows = []
    for lang, name in LANGUAGES.items():
        entry = data['languages'][lang]
        categories = entry.get('categories', {}) if entry.get('status', '').startswith('complete') else {}
        row = [name, f'{entry["correction_rows"]:,}' if entry['correction_rows'] is not None else None]
        for category in ('spelling', 'grammar'):
            group = categories.get(category, {})
            count = group.get('rows')
            row.extend([f'{count:,} ({100 * count / data["denominators"]["sampled_rows"]:.4f}%)' if count is not None else None,
                        group.get('distinct_rule_ids'), group.get('distinct_edit_pairs'),
                        f'{group["pct_all_training_tokens"]:.4f}' if group.get('pct_all_training_tokens') is not None else None])
        row.extend(f'{entry["mistake_count_pct_within_correction"][key]:.2f}'
                   if entry['mistake_count_pct_within_correction'].get(key) is not None else None
                   for key in ('0', '1', '2', '3', '4+', 'unknown'))
        rows.append(row)
    return dict(title='Error correction: recorded spelling and grammar corruptions',
                description='Identified sampled correction rows in the active DFM12 epoch. Counts are post-admission and sampling; mistake categories/counts require matching producer annotations.',
                columns=['Language', 'Correction rows', 'Spelling rows (% all)', 'Spell rules', 'Spell pairs', 'Spell tok. %',
                         'Grammar rows (% all)', 'Gram. rules', 'Gram. pairs', 'Gram. tok. %',
                         '0 errors %', '1 error %', '2 errors %', '3 errors %', '4+ errors %', 'Unknown %'],
                rows=rows,
                notes=[f'The percentages in parentheses divide by ALL {data["denominators"]["sampled_rows"]:,} sampled training rows, across all languages and tasks. They are row exposure percentages, not percentages of tokens.',
                       f'Token percentages divide the full rendered tokens of affected correction rows by ALL {data["denominators"]["sampled_tokens"]:,} sampled tokens. They do not count only the misspelled/incorrect token spans.',
                       'The final six columns divide by identified correction rows in that language. Clean controls (0) and unknown annotation coverage remain in the denominator. A row with both spelling and grammar errors contributes to both coverage columns.',
                       'Rules = distinct producer rule IDs actually observed; pairs = distinct original edit span / corrupted edit span pairs. Neither is the number of linguistic phenomena, and neither is inferred from character edit distance.',
                       'Grammar uses an explicit morphology/syntax-label allowlist. Generic deletion/swap operations without such a label stay unclassified; spelling and grammar columns are therefore neither mutually exclusive nor exhaustive.',
                       'The mistake count is the number of recorded corruption operations, not a guarantee that every operation corresponds to exactly one human-perceived error. Multiple operations may share a linguistic cause.',
                       'Coverage follows identified correction components; embedded correction examples in broad instruction sources may remain unclassified. A dash is unknown, not zero. Missing or conflicting producer metadata is not treated as a clean sample. Recovered source provenance does not itself recover missing edit annotations.',
                       'Detailed counts, token-weighted exposure, producer taxonomy, exact source paths, hashes, and annotation coverage are recorded in dfm12_error_composition.json.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--composition', type=Path, default=Path('docs/reports/dfm12_training_composition.json'))
    parser.add_argument('--errors', type=Path, default=Path('docs/reports/dfm12_error_composition.json'))
    parser.add_argument('--output', type=Path, default=Path('docs/reports/dfm12_training_composition_report.tex'))
    args = parser.parse_args()
    data = json.loads(args.composition.read_text())
    errors = json.loads(args.errors.read_text())
    allocated = sum(row['rendered_tokens'] or 0 for row in data['language_family_rows'])
    allocated += sum(row['rendered_tokens'] for row in data['unknowns'])
    if allocated != data['totals']['combined']['rendered_tokens']:
        raise ValueError('Language table and unknown buckets do not reconcile')
    if errors['denominators']['sampled_tokens'] != allocated:
        raise ValueError('Error and token accounting refer to different epochs')
    document = {'pages': [composition_page(data), error_page(errors)]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(document))
    args.output.with_suffix('.json').write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n')
    print(args.output)


if __name__ == '__main__':
    main()
