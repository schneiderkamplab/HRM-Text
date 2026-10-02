#!/usr/bin/env python3
"""Render evidence-backed training composition tables, one table per page."""
import argparse
import json
from pathlib import Path


def escape(value):
    mapping = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$',
               '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}',
               '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(mapping.get(c, c) for c in str(value))


def render(document):
    lines = [r'\documentclass[10pt]{article}',
             r'\usepackage[a3paper,landscape,margin=15mm]{geometry}',
             r'\usepackage{fontspec,booktabs,graphicx}',
             r'\setmainfont{DejaVu Serif}',
             r'\setlength{\parindent}{0pt}',
             r'\begin{document}']
    for index, page in enumerate(document['pages']):
        columns = page['columns']
        if not columns or any(len(row) != len(columns) for row in page['rows']):
            raise ValueError('Table rows must match columns')
        if index:
            lines.append(r'\clearpage')
        lines.extend([r'\section*{' + escape(page['title']) + '}',
                      escape(page['description']) + r'\par\medskip',
                      r'\resizebox{\textwidth}{!}{%',
                      r'\begin{tabular}{l' + 'r' * (len(columns) - 1) + '}',
                      r'\toprule',
                      ' & '.join(escape(c) for c in columns) + r' \\',
                      r'\midrule'])
        lines.extend(' & '.join(escape('--' if c is None else c) for c in row)
                     + r' \\' for row in page['rows'])
        lines.extend([r'\bottomrule\end{tabular}}', r'\par\bigskip'])
        for note in page['notes']:
            lines.append(escape(note) + r'\par\smallskip')
    return '\n'.join([*lines, r'\end{document}', ''])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(json.loads(args.input.read_text())))
    print(args.output)


if __name__ == '__main__':
    main()
