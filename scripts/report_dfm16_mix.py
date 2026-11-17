"""Compare verified DFM15/16 sampling receipts and epoch-zero source domains."""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT/'data/sampled_dfm16'
    new = json.loads((target/'validated.json').read_text())
    base = Path(new['base'])
    old = json.loads((base/'validated.json').read_text())
    averages = [sum(x['tokens'] for x in r['epochs'])/len(r['epochs']) for r in (old, new)]
    category_totals = []
    for directory in (base, target):
        arrays = {k: np.load(directory/'epoch_0'/(k+'.npy'), mmap_mode='r')
                  for k in ('category_id', 'inst_len', 'resp_len')}
        counts = np.zeros(3, dtype=np.uint64)
        for start in range(0, len(arrays['category_id']), 1_000_000):
            labels = arrays['category_id'][start:start+1_000_000]
            lengths = arrays['inst_len'][start:start+1_000_000]+arrays['resp_len'][start:start+1_000_000]
            for category in range(3):
                counts[category] += lengths[labels == category].sum(dtype=np.uint64)
        category_totals.append([int(x) for x in counts])
    for totals, receipt in zip(category_totals, (old, new)):
        assert sum(totals) == receipt['epochs'][0]['tokens']
    result = dict(dfm15_mean_tokens=averages[0], dfm16_mean_tokens=averages[1],
                  added_tokens_per_epoch=sum(x['sampled_tokens'] for x in new['additions']),
                  growth_percent=(averages[1]/averages[0]-1)*100,
                  epoch_zero_source_domain_tokens=category_totals,
                  additions=new['additions'], epochs=new['epochs'])
    out = ROOT/'data/dfm16/mix-comparison.json'
    out.write_text(json.dumps(result, indent=2)+'\n')
    lines = ['# DFM15 to DFM16 sampled mix', '',
             'Three epochs; unchanged inherited exposure; complete rows only (4097 token index limit).', '',
             '| Measure | DFM15 | DFM16 |', '|---|---:|---:|',
             f'| Mean tokens/epoch | {averages[0]:,.0f} | {averages[1]:,.0f} |',
             f'| Epoch-zero examples | {old["epochs"][0]["rows"]:,} | {new["epochs"][0]["rows"]:,} |', '',
             '| New source | Repeat | Eligible examples | Tokens/epoch | Excluded long/empty examples |',
             '|---|---:|---:|---:|---:|']
    for entry in new['additions']:
        lines.append(f'| {entry["repo_id"]} | {entry["repeat"]} | {entry["eligible_rows"]:,} | {entry["sampled_tokens"]:,} | {entry["excluded_rows"]:,} |')
    lines += ['', 'Source-domain categories are provenance routing labels, not semantic or language judgments.',
              'The math/code/tool-agentic category includes the new OpenScience science-reasoning examples.', '',
              '| Epoch-zero domain | DFM15 tokens | DFM16 tokens | DFM15 share | DFM16 share |',
              '|---|---:|---:|---:|---:|']
    for i, name in enumerate(('Neutral/general knowledge/uncertain', 'Math/code/tool-agentic', 'Language/chat/summarization/translation')):
        a, b = category_totals[0][i], category_totals[1][i]
        lines.append(f'| {name} | {a:,} | {b:,} | {a/sum(category_totals[0]):.2%} | {b/sum(category_totals[1]):.2%} |')
    lines += ['', 'All inherited rows retain their original order after filtering out the interleaved additions.',
              'New examples are shuffled independently per epoch, with full integer repeats.',
              'Length-excluded examples remain in the tokenized source stores for future longer-context sampling.',
              'No comprehensive inherited-versus-new semantic overlap audit was performed.', '']
    (ROOT/'docs/dfm16-mix.md').write_text('\n'.join(lines))
    print(json.dumps({k:v for k,v in result.items() if k not in ('additions', 'epochs')}, indent=2))


if __name__ == '__main__':
    main()
