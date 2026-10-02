#!/usr/bin/env python3
"""Render directly authored judgments alongside saved responses; no model calls."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from statistics import mean

try:
    from scripts.multilingual_family_report import LANGUAGES
except ModuleNotFoundError:
    from multilingual_family_report import LANGUAGES


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--responses', type=Path, required=True)
    p.add_argument('--judgments', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--label', default='XL 2930K EMA')
    p.add_argument('--checkpoint-tag', default='step_2930000')
    a = p.parse_args()
    responses = [json.loads(line) for line in a.responses.read_text().splitlines()]
    review = json.loads(a.judgments.read_text())
    judgments = {r['index']: r for r in review['judgments']}
    assert len(judgments) == len(review['judgments']) == len(responses) == 63
    assert {r['index'] for r in responses} == set(judgments) == set(range(63))
    for r in responses:
        r['judgment'] = judgments[r['index']]
        assert len(r['judgment']['scores']) == 3 and all(s in range(4) for s in r['judgment']['scores'])
    header = [
        '# ' + a.label + ': 21-language qualitative smoke', '',
        '**Checkpoint:** `checkpoints/dfm12/XL-from-dfm11-epoch10-noidentity`, `' + a.checkpoint_tag + '`, EMA.',
        '**Backend:** Transformers HRM-Text, HF-split export, BF16/SDPA, PrefixLM prompt tokens enabled.',
        '**Prompt contract:** training tokenizer (Mistral regex fix disabled), training Gemma template, thinking disabled, no system prompt.',
        '**Decoding:** greedy, batch one; 768 new tokens for stories, 384 for correction/summary; no repetition penalty. Eight GPUs alongside training, 8 GiB PyTorch allocator cap per worker. No W&B.',
        '**Review:** ' + review['reviewer'] + '.', '',
        '## Rubric', '', review['scale'] + '.', '',
        'Scores are reported separately as task success / language correctness / fluency. '
        'Fluency includes natural phrasing and coherent discourse, not merely grammatical sentences. '
        'Correction permits valid alternative repairs. Summary review checks faithfulness, the key change/result and exactly two sentences. '
        'Story review checks the requested duck/astronaut/beak premise, conversation, obstacle, ending and coherence.', '',
        review['caveats'], '',
        '## Main Findings', '',
        '- Short-form correction and summarization are much stronger than sustained creative generation.',
        '- Eighteen corrections succeed. Icelandic and Faroese copy the explicit error; Finnish copies the intended agreement error, but that prompt is context-sensitive and should be improved before formal scoring.',
        '- All summaries have two sentences and stay broadly on topic. Some add small unsupported claims or have clear language errors, especially Faroese and Finnish.',
        '- Twelve stories hit the token cap, all with visible repetition or degeneration. Several completed stories still contain serious grammatical, logical or instruction-following failures.',
        '- English is comparatively grammatical, but its story contradicts itself about the beak solution. Strong benchmark scores do not establish reliable open-ended writing.',
        '- These are observations of this greedy Transformers run, not proof of a training regression. No matched vLLM replay or earlier-checkpoint comparison was performed.', '',
        '## Task Summary', '',
        '| Task | Score 3 | Score 2 | Score 1 | Score 0 | Length finishes |',
        '|---|---:|---:|---:|---:|---:|']
    if 'findings' in review:
        start = header.index('## Main Findings') + 1
        end = header.index('## Task Summary')
        header[start:end] = ['', *['- ' + item for item in review['findings']], '']
    elif a.checkpoint_tag != 'step_2930000':
        raise ValueError('New checkpoints require their own reviewed findings')
    for task in ('grammatical_error_correction', 'creative_writing', 'summarization'):
        rows = [r for r in responses if r['task'] == task]
        counts = Counter(r['judgment']['scores'][0] for r in rows)
        header.append('| ' + task + ' | ' + ' | '.join(str(counts[i]) for i in (3,2,1,0)) +
                      f" | {sum(r['finish_reason']=='length' for r in rows)} |")
    header += ['', '## Per-language Summary', '',
               'Correction/story/summary columns are **task-success scores**, not combined quality scores. Language and fluency columns are descriptive means across just three examples.', '',
               '| Language | Correction | Story | Summary | Language /3 | Fluency /3 |',
               '|---|---:|---:|---:|---:|---:|---:|']
    for lang, name in LANGUAGES.items():
        rows = [r for r in responses if r['language'] == lang]
        assert len(rows) == 3
        scores = {r['task']:r['judgment']['scores'][0] for r in rows}
        header.append(f"| {name} | {scores['grammatical_error_correction']} | {scores['creative_writing']} | {scores['summarization']} | {mean(r['judgment']['scores'][1] for r in rows):.2f} | {mean(r['judgment']['scores'][2] for r in rows):.2f} |")
    for r in responses:
        header += ['', f"## {r['index']+1}. {LANGUAGES[r['language']]}: {r['task']}", '',
                   '**Prompt**', '', r['prompt'], '', '**Response (verbatim)**', '',
                   '```text', r['response'], '```', '',
                   '**Scores (task / language / fluency):** ' + ' / '.join(map(str,r['judgment']['scores'])), '',
                   '**Assessment:** ' + r['judgment']['assessment'], '',
                   f"**Generation:** {r['output_tokens']} tokens; finish={r['finish_reason']}; {r['elapsed_seconds']:.1f}s."]
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text('\n'.join(header)+'\n')
    a.output.with_suffix('.json').write_text(json.dumps(dict(
        label=a.label, checkpoint_tag=a.checkpoint_tag,
        reviewer=review['reviewer'], rubric=review['scale'], caveats=review['caveats'],
        source_sha256=hashlib.sha256(a.responses.read_bytes()).hexdigest(), responses=responses), ensure_ascii=False, indent=2)+'\n')
    print('\n'.join(header[header.index('## Task Summary'):header.index('## Per-language Summary')]))


if __name__ == '__main__':
    main()
