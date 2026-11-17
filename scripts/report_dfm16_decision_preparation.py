"""Assemble preparation receipts; does not select rows or sample epochs."""
import json
from pathlib import Path


def main():
    root = Path('data/dfm16/decisions-v1')
    registry = json.loads(Path('config/dfm16_decision_sources.json').read_text())
    results, pending = [], []
    sources = [(s['name'], root / s['name'], s['repo_id']) for s in registry['sources']]
    sources.append(('decision_curriculum', Path('data/dfm16/decision_curriculum'), 'local/executable-curriculum'))
    for name, path, repo in sources:
        prepared = path / 'prepared.json'
        if not prepared.exists():
            pending.append(name)
            continue
        stats = json.loads(prepared.read_text())
        conversion = json.loads((path / 'conversion.json').read_text())
        results.append(dict(name=name, repo_id=repo, **stats,
            conversion_receipt=str((path / 'conversion.json').resolve()),
            rejected=conversion.get('rejected', {})))
    summary = dict(sources=results, pending=pending, sampled=False,
                   total_rows=sum(s['rows'] for s in results),
                   total_tokens=sum(s['tokens'] for s in results),
                   includes_hetionet=False,
                   scope='Approved decision additions only; inherited DFM corpus unchanged.')
    root.mkdir(parents=True, exist_ok=True)
    (root / 'preparation_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    for r in results:
        print(f'{r["repo_id"]}: {r["rows"]:,} examples; {r["tokens"]:,} tokens; '
              f'{r.get("over_4096", 0):,} over 4096')
    print(f'Total: {summary["total_rows"]:,} examples; {summary["total_tokens"]:,} tokens')
    print('Pending:', ', '.join(pending) or 'none')


if __name__ == '__main__':
    main()
