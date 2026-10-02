#!/usr/bin/env python3
"""Render saved multilingual smoke answers and authored reviews, one language/page."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re

try:
    from scripts.multilingual_family_report import LANGUAGES, escape
except ModuleNotFoundError:
    from multilingual_family_report import LANGUAGES, escape

TASKS = {
    'grammatical_error_correction': 'Grammatical error correction',
    'creative_writing': 'Creative writing',
    'summarization': 'Summarization',
}


def prose(text):
    """Escape LaTeX while preserving paragraphs and allowing long loops to wrap."""
    def token(value):
        if len(value) <= 32:
            return escape(value)
        return r'\allowbreak{}'.join(escape(value[i:i+16]) for i in range(0, len(value), 16))
    paragraphs = []
    for paragraph in re.split(r'\n\s*\n', text.strip()):
        paragraphs.append(''.join(part if part.isspace() else token(part)
                                  for part in re.split(r'(\s+)', paragraph)))
    return ('\n' + r'\par\smallskip' + '\n').join(paragraphs)


def render(document, paper='a4paper'):
    grouped = defaultdict(dict)
    for row in document['responses']:
        lang, task = row['language'], row['task']
        if lang not in LANGUAGES or task not in TASKS or task in grouped[lang]:
            raise ValueError(f'Unknown or duplicate language/task: {lang}/{task}')
        scores = row['judgment']['scores']
        if len(scores) != 3 or any(type(s) is not int or s not in range(4) for s in scores):
            raise ValueError('Expected three integer scores in 0..3')
        grouped[lang][task] = row
    if not grouped or any(set(tasks) != set(TASKS) for tasks in grouped.values()):
        raise ValueError('Every language requires exactly the three tasks')
    if paper not in ('a4paper', 'a3paper'):
        raise ValueError('Unsupported paper')
    lines = [r'\documentclass[10pt]{article}',
             r'\usepackage[' + paper + r',margin=12mm]{geometry}',
             r'\usepackage{fontspec,graphicx,xcolor}',
             r'\setmainfont{DejaVu Serif}',
             r'\newsavebox{\languagepage}',
             r'\setlength{\parindent}{0pt}',
             r'\setlength{\emergencystretch}{3em}',
             r'\begin{document}']
    for index, lang in enumerate(k for k in LANGUAGES if k in grouped):
        if index:
            lines.append(r'\clearpage')
        lines += [r'{\Large\bfseries ' + escape(LANGUAGES[lang]) + ' --- ' + escape(document.get('label', 'XL 2930K EMA')) + r'}\par\smallskip',
                  r'\noindent\sbox{\languagepage}{\begin{minipage}{\textwidth}',
                  r'\fontsize{9}{10.5}\selectfont',
                  r'\textbf{Scores:} task success / language correctness / fluency; each 0--3. '
                  r'3 strong; 2 usable with reservations; 1 major problems; 0 failed/unusable. '
                  r'Direct Codex review, not an external judge or native-speaker certification. '
                  r'One prompt per task; greedy decoding; no matched earlier-checkpoint/backend comparison.\par\smallskip']
        for number, task in enumerate(TASKS, 1):
            row = grouped[lang][task]
            scores = ' / '.join(str(v) for v in row['judgment']['scores'])
            lines += [r'\medskip\hrule\smallskip',
                      r'{\bfseries ' + str(number) + '. ' + TASKS[task] + r'}\par\smallskip',
                      r'\textbf{Instruction and input}\par ' + prose(row['prompt']) + r'\par\smallskip',
                      r'\textbf{Answer}\par ' + prose(row['response']) + r'\par\smallskip',
                      r'\textbf{Evaluation: ' + scores + r'}\par ' + prose(row['judgment']['assessment']),
                      r'\par {\color{gray} ' + escape(f"Output: {row['output_tokens']} tokens; finish: {row['finish_reason']}.") + r'}\par']
        lines += [r'\medskip\footnotesize All answer text is retained. Length finishes reflect the 768-token story / 384-token other-task caps. '
                  r'Long pages are scaled to fit. Scores are qualitative judgments, not benchmark estimates.',
                  r'\end{minipage}}%',
                  r'\noindent\ifdim\dimexpr\ht\languagepage+\dp\languagepage\relax>0.93\textheight%',
                  r'\resizebox*{!}{0.93\textheight}{\usebox{\languagepage}}%',
                  r'\else\usebox{\languagepage}\fi%']
    return '\n'.join([*lines, r'\end{document}', ''])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True, help='JSON emitted by build_multilingual_smoke_review.py')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--paper', choices=('a4', 'a3'), default='a4', help='A3 gives more room for long verbatim answers')
    a = p.parse_args()
    document = json.loads(a.input.read_text())
    tex = render(document, a.paper + 'paper')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(tex)
    print(a.output)


if __name__ == '__main__':
    main()
