#!/usr/bin/env python3
"""Read-only multilingual task-family LaTeX report from merged eval artifacts."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
from statistics import mean

LANGUAGES = dict(zip(
    'da en nb nn sv is fo nl pl de fr es it cs pt_pt fi et ca el ro uk'.split(),
    ['Danish', 'English', 'Norwegian Bokmal', 'Norwegian Nynorsk', 'Swedish',
     'Icelandic', 'Faroese', 'Dutch', 'Polish', 'German', 'French', 'Spanish',
     'Italian', 'Czech', 'Portuguese', 'Finnish', 'Estonian', 'Catalan',
     'Greek', 'Romanian', 'Ukrainian']))
ALIASES = {'nb_no': 'nb', 'nn_no': 'nn', 'pt': 'pt_pt', 'pt_pt-pt': 'pt_pt'}
EURO_METRICS = {
    'linguistic-acceptability': 'macro_f1',
    'reading-comprehension': 'f1',
    'instruction-following': 'instruction_accuracy',
    'summarization': 'chr_f3pp',
    'named-entity-recognition': 'micro_f1',
    'knowledge': 'accuracy',
    'common-sense-reasoning': 'accuracy',
    'sentiment-classification': 'macro_f1',
}


def binding(key):
    """Return family, language, task identity, divisor; never infer units by value."""
    parts = key.split('/')
    if len(parts) == 5 and parts[0] == 'euroeval':
        _, lang, family, task, metric = parts
        if task.startswith('valeu-') or EURO_METRICS.get(family) != metric:
            return None
        return family, ALIASES.get(lang, lang), 'EuroEval:' + task, 1
    match = re.fullmatch(r'dfm_eval/(dala|gec_dala)(?:_([a-z_]+))?/(.+)', key)
    if match:
        task, lang, metric = match.groups()
        expected = 'semantic_v1/macro_f1' if task == 'dala' else 'exact_match/mean'
        if metric == expected:
            return ('linguistic-acceptability' if task == 'dala' else
                    'grammatical-error-correction', lang or 'da', 'DFM:' + task, .01)
        return None
    fixed = {
        'dfm_eval/govreport/chrf3pp/mean': ('summarization', 'en', 'DFM:GovReport', 1),
        'dfm_eval/nordjyllandnews/chrf3pp/mean': ('summarization', 'da', 'DFM:NordjyllandNews', 1),
        'dfm_eval/multi_wiki_qa/f1/mean': ('reading-comprehension', 'da', 'DFM:MultiWikiQA', .01),
        'dfm_eval/ifeval-da/instruction_following/inst_strict_acc':
            ('instruction-following', 'da', 'DFM:IFEval-DA', .01),
        'eval/DROP/f1': ('reading-comprehension', 'en', 'Standard:DROP', .01),
    }
    for task in ('drop', 'triviaqa', 'nq_open', 'squad', 'coqa'):
        fixed[f'dfm_eval/{task}/f1/mean'] = ('reading-comprehension', 'en', 'DFM:' + task, .01)
    for task in ('hellaswag', 'winogrande', 'piqa_en', 'socialiqa', 'commonsense_qa'):
        fixed[f'dfm_eval/{task}/choice/accuracy'] = ('common-sense-reasoning', 'en', 'DFM:' + task, .01)
    fixed['dfm_eval/boolq/pattern/accuracy'] = ('common-sense-reasoning', 'en', 'DFM:boolq', .01)
    fixed['dfm_eval/piqa/piqa_scorer/accuracy'] = ('common-sense-reasoning', 'da', 'DFM:piqa', .01)
    fixed['dfm_eval/danish-citizen-tests/knowledge/accuracy'] = ('knowledge', 'da', 'DFM:citizen-tests', .01)
    for task in ('arc_challenge', 'arc_easy', 'openbookqa', 'mmlu_pro', 'agieval'):
        fixed[f'dfm_eval/{task}/choice/accuracy'] = ('knowledge', 'en', 'DFM:' + task, .01)
    for task, family in [('BoolQ', 'common-sense-reasoning'), ('HellaSwag', 'common-sense-reasoning'),
                         ('Winogrande', 'common-sense-reasoning'), ('MMLU', 'knowledge'), ('ARC', 'knowledge')]:
        fixed[f'eval/{task}/acc'] = (family, 'en', 'Standard:' + task, .01)
    return fixed.get(key)


def read_checkpoint(checkpoint):
    results = {}
    paths = set()
    for root in checkpoint['roots']:
        root = Path(root)
        if not root.is_dir():
            raise ValueError(f'Missing root: {root}')
        paths.update(root.rglob('merged_metrics.json'))
        paths.update(root.glob('merged_ifeval_da_metrics.json'))
    for path in sorted(paths):
        document = json.loads(path.read_text())
        metrics = document.get('metrics', document)
        selected = [(key, value, binding(key)) for key, value in metrics.items() if binding(key)]
        if not selected:
            continue
        for source in (document, metrics):
            for key, value in source.items():
                if key in ('epoch', 'eval/epoch', 'dfm_eval/epoch', 'euroeval/epoch'):
                    if not isinstance(value, (int, float)) or not math.isclose(value, checkpoint['epoch'], abs_tol=1e-8, rel_tol=0):
                        raise ValueError(f'Epoch mismatch: {path}: {key}={value}')
                if key in ('eval/train_step', 'dfm_eval/train_step', 'euroeval/train_step') and value != checkpoint['step']:
                    raise ValueError(f'Step mismatch: {path}')
        for key, raw, (family, lang, task, divisor) in selected:
            if type(raw) not in (float, int) or not math.isfinite(raw) or not 0 <= raw / divisor <= 100:
                raise ValueError(f'Invalid score: {path}: {key}={raw}')
            identity = (family, lang, task)
            evidence = {'score': raw / divisor, 'key': key, 'raw': raw, 'paths': [str(path)]}
            if identity in results:
                previous = results[identity]
                if previous['score'] != evidence['score'] or previous['key'] != key:
                    raise ValueError(f'Conflicting duplicate: {identity}: {path}')
                previous['paths'].append(str(path))
            else:
                results[identity] = evidence
    return results


def aggregate(checkpoints, minimum=18):
    if not 1 <= minimum <= 21 or not checkpoints:
        raise ValueError('Require checkpoints and a coverage threshold in 1..21')
    loaded = [read_checkpoint(cp) for cp in checkpoints]
    identities = set().union(*(set(data) for data in loaded))
    families = {}
    excluded = {}
    for family in sorted({key[0] for key in identities}):
        rows = {}
        for lang in [*LANGUAGES, 'nb_nn_no']:
            tasks = sorted(key for key in identities if key[:2] == (family, lang))
            cells = []
            for data in loaded:
                found = [data[key] for key in tasks if key in data]
                complete = bool(tasks) and len(found) == len(tasks)
                scores = [entry['score'] for entry in found]
                cells.append({'mean': mean(scores) if complete else None,
                              'min': min(scores) if complete else None,
                              'max': max(scores) if complete else None,
                              'complete': complete, 'evidence': found,
                              'missing': [key[2] for key in tasks if key not in data]})
            delta = (cells[-1]['mean'] - cells[0]['mean']
                     if cells[0]['complete'] and cells[-1]['complete'] else None)
            rows[lang] = {'tasks': [key[2] for key in tasks], 'cells': cells,
                         'change_pp': delta}
        coverage = sum(all(cell['complete'] for cell in rows[lang]['cells']) for lang in LANGUAGES)
        if coverage >= minimum:
            families[family] = {'coverage': coverage, 'rows': rows}
        else:
            excluded[family] = coverage
    return {'checkpoints': checkpoints, 'minimum_languages': minimum,
            'weighting': 'Equal task/suite combinations; fixed union of tasks across checkpoints; complete cells only',
            'families': families, 'excluded_families': excluded}


def escape(text):
    replacements = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$',
                    '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(replacements.get(c, c) for c in str(text))


def make_plots(report, directory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    directory.mkdir(parents=True, exist_ok=True)
    # One common axis allows honest comparisons between family pages.
    deltas = [row['change_pp'] for data in report['families'].values()
              for row in data['rows'].values() if row['change_pp'] is not None]
    low, high = min([0, *deltas]), max([0, *deltas])
    pad = max(3, (high - low) * .13)
    paths = {}
    for family, data in report['families'].items():
        rows = [(lang, row) for lang, row in data['rows'].items()
                if lang != 'nb_nn_no' or row['tasks']]
        fig, ax = plt.subplots(figsize=(5.6, 5.2), layout='constrained')
        for i, (_, row) in enumerate(rows):
            value = row['change_pp']
            if value is None:
                ax.text(0, i, '  n/a', va='center', fontsize=8, color='#666666')
            else:
                ax.barh(i, value, height=.65, color='#247a68' if value >= 0 else '#b04450')
                ax.annotate(f'{value:+.2f}', (value, i), xytext=(3 if value >= 0 else -3, 0),
                            textcoords='offset points', va='center',
                            ha='left' if value >= 0 else 'right', fontsize=8)
        ax.set_yticks(range(len(rows)), [LANGUAGES.get(lang, 'Norwegian (joint)') for lang, _ in rows], fontsize=8)
        ax.invert_yaxis()
        ax.set_xlim(low - pad, high + pad)
        ax.axvline(0, color='#444444', linewidth=.8)
        ax.set_axisbelow(True)
        ax.grid(axis='x', alpha=.2)
        ax.set_xlabel('Change in mean score (percentage points)', fontsize=9)
        ax.set_title(report['checkpoints'][-1]['label'] + ' minus ' + report['checkpoints'][0]['label'], fontsize=11)
        for spine in ('top', 'right', 'left'):
            ax.spines[spine].set_visible(False)
        path = directory / (family + '.pdf')
        fig.savefig(path)
        plt.close(fig)
        paths[family] = path
    return paths


def render(report, plots=None):
    n = len(report['checkpoints'])
    lines = [r'\documentclass[10pt]{article}', r'\usepackage[a4paper,landscape,margin=12mm]{geometry}',
             r'\usepackage[T1]{fontenc}', r'\usepackage{booktabs,graphicx}',
             r'\newsavebox{\familytable}', r'\begin{document}']
    for index, (family, data) in enumerate(report['families'].items()):
        if index:
            lines.append(r'\clearpage')
        lines += [r'\section*{' + escape(family.replace('-', ' ').title()) + '}',
                  escape(f"Complete matched coverage: {data['coverage']}/21 languages. Scores: 0--100; mean (minimum--maximum) across tasks."),
                  r'\par\smallskip\noindent',
                  r'\begin{minipage}[t]{0.57\textwidth}\vspace{0pt}' if plots else '',
                  r'\sbox{\familytable}{%',
                  r'\begin{tabular}{ll' + 'r' * (n + 1) + '}', r'\toprule',
                  'Language & Tasks & ' + ' & '.join(escape(cp['label']) for cp in report['checkpoints']) + r' & Change (pp) \\', r'\midrule']
        for lang, row in data['rows'].items():
            if lang == 'nb_nn_no' and not row['tasks']:
                continue
            values = ['--' if c['mean'] is None else f"{c['mean']:.2f} ({c['min']:.2f}--{c['max']:.2f})" for c in row['cells']]
            lines.append(escape(LANGUAGES.get(lang, 'Norwegian (joint NB/NN)')) + ' & ' +
                         str(len(row['tasks'])) + ' & ' + ' & '.join(values) + ' & ' +
                         ('--' if row['change_pp'] is None else f"{row['change_pp']:+.2f}") + r' \\')
        lines += [r'\bottomrule\end{tabular}}',
                  r'\ifdim\wd\familytable>\linewidth\resizebox{\linewidth}{!}{\usebox{\familytable}}\else\usebox{\familytable}\fi']
        if plots:
            lines += [r'\end{minipage}\hfill\begin{minipage}[t]{0.42\textwidth}\vspace{0pt}',
                      r'\includegraphics[width=\linewidth]{\detokenize{' + str(plots[family]) + '}}',
                      r'\end{minipage}']
        lines += [
                  r'\par\smallskip\footnotesize',
                  'Equal weight per task/suite; not per sample. Ranges are not confidence intervals. '
                  'Missing/incomplete cells are withheld. Joint Norwegian results do not count as two languages. '
                  'Change is last minus first checkpoint, in percentage points (not relative percent). All plots share the same horizontal scale.',
                  r'\par ' + escape('Checkpoint steps: ' + '; '.join(f"{cp['label']}: {cp['step']} (epoch {cp['epoch']:.6f})" for cp in report['checkpoints'])),
                  r'\par Primary scores: ' + escape('EuroEval: ' + EURO_METRICS.get(family, 'not applicable') +
                      '; DFM: semantic macro-F1 for acceptability, exact match for correction, strict instruction accuracy for IFEval, answer F1 for QA, chrF3++ for summarization.'),
                  r'\par Task membership and source paths are recorded in the accompanying JSON evidence file.\normalsize']
    lines.append(r'\end{document}')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--min-languages', type=int, default=18)
    args = parser.parse_args()
    report = aggregate(json.loads(args.manifest.read_text())['checkpoints'], args.min_languages)
    if not report['families']:
        raise ValueError('No task family meets coverage threshold')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    plots = make_plots(report, args.output.parent / (args.output.stem + '_plots'))
    args.output.write_text(render(report, plots))
    args.output.with_suffix('.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print('Included:', {k: v['coverage'] for k, v in report['families'].items()})
    print('Excluded:', report['excluded_families'])
    print(args.output)


if __name__ == '__main__':
    main()
