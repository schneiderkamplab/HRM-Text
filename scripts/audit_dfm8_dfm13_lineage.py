"""Cross-check every original DFM8 inventory entry against DFM13 repository attribution."""
from collections import Counter
import json
from pathlib import Path
import re


def main():
    inventory = json.loads(Path('docs/reports/dfm13_hf_repository_counts_20261006.json').read_text())
    current = set(inventory['repositories'])
    packages = json.loads(Path('exports_dfm10/manifest.json').read_text())['packages']
    successors = {}
    for package in packages:
        repo = 'schneiderkamplab/' + package['name']
        if repo not in current:
            continue
        for upstream in package.get('upstream', []):
            successors.setdefault(upstream, set()).add(repo)
    explicit = {
        'MegaScience/TextbookReasoning': ['dfm10-sapient-textbook-reasoning-filtered-sft'],
        'nvidia/AceReason-1.1-SFT': ['dfm10-sapient-acereason-filtered-sft'],
        'open-thoughts/OpenThoughts2-1M': ['dfm10-sapient-openthoughts2-filtered-sft'],
        'Team-ACE/ToolACE': ['dfm11-toolace-native-tool-use-repaired'],
        'glaiveai/glaive-function-calling-v2': ['dfm11-glaive-native-tool-use-repaired'],
        'schneiderkamplab/dfm8-synthetic-native-tool-calling': ['dfm11-synthetic-native-tool-calling-repaired'],
        'schneiderkamplab/sapient-synth-flan-dialog-fsopt-data-qrecc-ii': ['dfm10-sapient-qrecc-ii-repaired'],
        'schneiderkamplab/sapient-synth-flan-dialog-zsopt-data-qrecc-ii': ['dfm10-sapient-qrecc-ii-repaired'],
        'schneiderkamplab/sapient-synth-platypus-scibench': ['dfm10-sapient-scibench-repaired'],
    }
    for repo, names in explicit.items():
        successors[repo] = {'schneiderkamplab/' + name for name in names}
    exclusions = {
        'oliverkinch/machine-translation-da-ar': 'Explicit quality exclusion; source audit found 7% usable.',
        'oliverkinch/machine-translation-da-en': 'Explicit quality/redundancy exclusion in favor of filtered OPUS DA-EN.',
        'schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task871-msmarco-question-generation': 'Explicit quality exclusion: negligible low-quality source.',
        'schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task871-msmarco-question-generation': 'Explicit quality exclusion: negligible low-quality source.',
    }
    rows = []
    for line in Path('docs/dfm8-datasets.md').read_text().splitlines():
        if not line.startswith('| ['):
            continue
        repo = re.search(r'https://huggingface.co/datasets/([^)]*)', line).group(1)
        if repo in current:
            status, targets, evidence = 'same_repository', [repo], 'DFM13 reconciled included-repository inventory'
        elif repo in exclusions:
            status, targets, evidence = 'deliberately_excluded', [], exclusions[repo]
        elif repo in successors:
            status, targets = 'successor_package', sorted(successors[repo])
            evidence = 'DFM10 export manifest; DFM11 tool replacements; DFM10 final source reconciliation'
            assert set(targets) <= current, (repo, targets)
        else:
            status, targets, evidence = 'unresolved', [], 'No proven successor mapping'
        rows.append(dict(original=repo, status=status, current_repositories=targets, evidence=evidence))
    for name, prefixes in [('Lex.dk', {'lexdk'}), ('DBC', {'dbc', 'dbc_repaired'})]:
        assert prefixes <= {r['source'] for r in inventory['inherited']}
        rows.append(dict(original=name, status='agreement_source_retained', current_repositories=[],
                         evidence='Positive sampled DFM11 rows inherited by DFM13; original/repaired views'))
    counts = dict(Counter(r['status'] for r in rows))
    result = dict(original_entries=len(rows), counts=counts, rows=rows,
                  limitations=['Source lineage, not row-for-row retention or unchanged sampling weight.',
                               'Same repository does not imply identical revision or selection.',
                               'Uses finalized expanded DFM13 scope, not the local October 2 sample.'])
    output = Path('docs/reports/dfm8_to_dfm13_lineage_20261006.json')
    output.write_text(json.dumps(result, indent=2)+'\n')
    assert len(rows) == 161
    assert not counts.get('unresolved'), [r for r in rows if r['status']=='unresolved']
    md = ['# Original Mimir v1 / DFM8 Sources in DFM13', '',
          'Source-level crosswalk. Retention does not imply all original rows or unchanged weights.', '',
          '| Original dataset | Disposition | Current repositories |', '|---|---|---|']
    md.extend('| '+r['original']+' | '+r['status']+' | '+(', '.join(r['current_repositories']) or r['evidence'])+' |' for r in rows)
    output.with_suffix('.md').write_text('\n'.join(md)+'\n')
    print(json.dumps(counts, indent=2))


if __name__ == '__main__':
    main()
