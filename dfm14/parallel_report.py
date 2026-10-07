"""Count unique direct/pivot coverage and materialize only novel additions."""
from collections import Counter
import json
from pathlib import Path
import typer
from dfm12.io import atomic, file_hash, load, lock, rows, write_json

app = typer.Typer()


@app.command()
def run(original:Path=Path('data/dfm14/parallel-v1'), expanded:Path=Path('data/dfm14/parallel-expansion-v2')):
    output = expanded / 'novel'
    with lock(output / '.lock'):
        cfg = load(original / 'config.json')
        results = []
        for pair in cfg['requested_pairs']:
            name = '-'.join(pair)
            old = original / 'candidates' / ('opus-' + name) / 'candidates.jsonl'
            direct = expanded / 'candidates' / ('opus-' + name) / 'candidates.jsonl'
            pivot = expanded / 'pivots' / name / 'candidates.jsonl'
            seen, counts = set(), Counter()
            with atomic(output / (name + '.jsonl')) as handle:
                for route, path in (('original_direct',old), ('new_direct',direct), ('new_pivot',pivot)):
                    if not path.exists():
                        continue
                    for row in rows(path):
                        if row['id'] in seen:
                            counts[route + '_duplicate'] += 1
                            continue
                        seen.add(row['id'])
                        counts[route] += 1
                        counts['candidate_pairs'] += 1
                        counts['rendered_tokens'] += row['rendered_tokens']
                        if route != 'original_direct':
                            row.update(training_ready=False,admission_authorized=False)
                            handle.write(json.dumps(row,ensure_ascii=False)+'\n')
            cap = cfg['pair_budgets'][name]['tokens']
            counts.setdefault('candidate_pairs', 0)
            counts.setdefault('rendered_tokens', 0)
            results.append(dict(pair=name, **counts, token_cap=cap,
                                candidate_token_shortfall=max(0,cap-counts['rendered_tokens']),
                                novel_sha256=file_hash(output/(name+'.jsonl'))))
        totals = Counter()
        for r in results:
            for key in ('original_direct','new_direct','new_pivot','candidate_pairs','rendered_tokens','candidate_token_shortfall'):
                totals[key] += r.get(key,0)
        summary = dict(pairs=len(results), totals=dict(totals),
            zero_pairs=sum(r['candidate_pairs']==0 for r in results),
            under_100=sum(r['candidate_pairs']<100 for r in results),
            under_1000=sum(r['candidate_pairs']<1000 for r in results),
            at_least_10000=sum(r['candidate_pairs']>=10000 for r in results),
            per_pair=results, training_ready=False,
            note='Candidates, not accepted data. Caps are ceilings, not minimum quotas; no repeats to fill gaps.')
        write_json(expanded/'coverage.json',summary)
        print(json.dumps({k:v for k,v in summary.items() if k!='per_pair'}),flush=True)


if __name__ == '__main__': app()
