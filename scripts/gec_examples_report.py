#!/usr/bin/env python3
"""Sample reference GEC pairs from completed Inspect artifacts into a LaTeX report."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

try:
    from scripts.multilingual_family_report import LANGUAGES, escape
except ModuleNotFoundError:
    from multilingual_family_report import LANGUAGES, escape


def sentence_pair(sample):
    metadata = sample.get('metadata', {})
    if metadata.get('variant') not in (None, 'corrupted'):
        return None
    incorrect = metadata.get('corrupted')
    correct = sample.get('target')
    if isinstance(correct, list):
        if len(correct) != 1:
            raise ValueError('Expected a single reference correction')
        correct = correct[0]
    if not isinstance(incorrect, str) or not isinstance(correct, str):
        raise ValueError('Missing corrupted sentence or reference target')
    incorrect, correct = incorrect.strip(), correct.strip()
    if not incorrect or not correct or incorrect == correct:
        return None
    if metadata.get('original') is not None and metadata['original'].strip() != correct:
        raise ValueError('Reference target disagrees with original sentence')
    return incorrect, correct


def collect(roots, language):
    task = 'gec_dala' if language == 'da' else 'gec_dala_' + language
    manifests = [Path(root) / task / 'merged_metrics.json' for root in roots]
    manifests = [path for path in manifests if path.is_file()]
    if len(manifests) != 1:
        raise ValueError(f'{language}: expected one merged task, found {len(manifests)}')
    manifest = manifests[0]
    archives = json.loads(manifest.read_text())['inputs']
    pairs = {}
    for archive in sorted(archives):
        with zipfile.ZipFile(archive) as handle:
            for member in sorted(handle.namelist()):
                if not member.startswith('samples/') or not member.endswith('.json'):
                    continue
                sample = json.loads(handle.read(member))
                lang = sample.get('metadata', {}).get('language', language)
                if lang != language:
                    raise ValueError(f'Language mismatch: {archive}:{member}')
                pair = sentence_pair(sample)
                if pair is None:
                    continue
                incorrect, correct = pair
                if incorrect in pairs and pairs[incorrect]['correct'] != correct:
                    raise ValueError(f'Conflicting corrections: {language}: {incorrect}')
                pairs.setdefault(incorrect, dict(incorrect=incorrect, correct=correct,
                    sample_id=sample.get('id'), archive=archive, member=member,
                    metadata=sample.get('metadata', {})))
    return list(pairs.values()), str(manifest)


def select(rows, language, seed, count):
    if len(rows) < count:
        raise ValueError(f'{language}: only {len(rows)} distinct corrupted pairs; need {count}')
    def rank(row):
        value = json.dumps([seed, language, row['incorrect'], row['correct']], ensure_ascii=False)
        return hashlib.sha256(value.encode()).hexdigest()
    return sorted(rows, key=rank)[:count]


def render(report):
    lines = [r'\documentclass[10pt]{article}',
             r'\usepackage[a4paper,margin=15mm]{geometry}',
             r'\usepackage{fontspec}', r'\setmainfont{DejaVu Serif}',
             r'\usepackage{array,booktabs,graphicx}',
             r'\newsavebox{\pairtable}', r'\setlength{\emergencystretch}{2em}',
             r'\begin{document}']
    for index, (language, data) in enumerate(report['languages'].items()):
        if index:
            lines.append(r'\clearpage')
        lines += [r'\section*{' + escape(LANGUAGES[language]) + ': Grammatical Error Correction}',
                  r'\noindent Reference sentence pairs from held-out evaluation data; not model outputs.',
                  r'\par\smallskip\noindent\sbox{\pairtable}{\renewcommand{\arraystretch}{1.25}%',
                  r'\begin{tabular}{@{}>{\raggedright\arraybackslash}p{0.48\textwidth}@{\hspace{0.04\textwidth}}>{\raggedright\arraybackslash}p{0.48\textwidth}@{}}',
                  r'\toprule Incorrect & Correct \\ \midrule']
        for row in data['rows']:
            lines.append(escape(row['incorrect']) + ' & ' + escape(row['correct']) + r' \\ \addlinespace[5pt]')
        lines += [r'\bottomrule\end{tabular}}%',
                  r'\ifdim\dimexpr\ht\pairtable+\dp\pairtable\relax>0.82\textheight%',
                  r'\resizebox*{!}{0.82\textheight}{\usebox{\pairtable}}%',
                  r'\else\usebox{\pairtable}\fi%',
                  r'\par\smallskip\footnotesize ' + escape(f"Seed {report['seed']}; {len(data['rows'])} of {data['eligible_pairs']} distinct corrupted pairs. References are dataset labels, not a fresh linguistic audit.") + r'\normalsize']
    return '\n'.join([*lines, r'\end{document}', ''])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, action='append', required=True,
                        help='Checkpoint directory containing gec_dala[_LANG]/merged_metrics.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--languages', nargs='+', choices=list(LANGUAGES), default=list(LANGUAGES))
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--count', type=int, default=10)
    args = parser.parse_args()
    if args.count < 1:
        parser.error('--count must be positive')
    report = {'seed': args.seed, 'selection': 'SHA256-ranked distinct corrupted pairs; unchanged controls excluded', 'languages': {}}
    for lang in args.languages:
        rows, manifest = collect(args.root, lang)
        report['languages'][lang] = {'manifest': manifest, 'eligible_pairs': len(rows),
                                    'rows': select(rows, lang, args.seed, args.count)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(report))
    args.output.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f"Wrote {len(report['languages'])} language pages to {args.output}")


if __name__ == '__main__':
    main()
