"""Reconcile sampled inherited sources and the finalized DFM13 publication map."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

from scripts.download_training_datasets import HF_DATASETS
from scripts.prepare_dfm10_hf_exports import SPECS


# Explicit aliases between sampler task names and the published replacements.
PACKAGE_ALIASES = {
    'alexandra_multi_zebra': 'alexandra-multi-zebra-logic',
    'danmarks_statistik_bt_repaired': 'danmarks-statistik-bt-repaired',
    'dfm4_arxiv_paper_summarization': 'arxiv-paper-summarization-sft',
    'dsldk_danish_framenet.jsonl': 'danish-framenet-sft',
    'dsldk_danish_framenet_natural.jsonl': 'danish-framenet-sft',
    'dsldk_danish_sentiment_lexicon.jsonl': 'danish-lexical-sentiment-sft',
    'dsldk_danish_sentiment_lexicon_natural.jsonl': 'danish-lexical-sentiment-sft',
    'dst_table_prompts_repaired': 'dst-table-prompts-repaired',
    'govreport_summarization_repaired': 'govreport-summarization-repaired',
    'mimir_grounded_expanded_sft': 'mimir-grounded-expanded-sft',
    'nordjylland_news_repaired': 'nordjylland-news-repaired',
    'openstax_mimir_sft': 'openstax-mimir-sft',
    'tidsskrift_open_article_summaries.jsonl': 'tidsskrift-open-sft',
    'wiki_cat_sum_repaired': 'wiki-cat-sum-repaired',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    remote_code = '''
import json
from pathlib import Path
from scripts.dfm13_specification_reconciliation import dala_publications
i=json.loads(Path('data/dfm13/all-source-finalization-20261004-v1/inventory.json').read_text())
grouped=dala_publications(i)
rows=[]
for x in i['components']:
 if not x['integrated']: continue
 repo=grouped.get(x['name'],{}).get('repo') or x.get('publication_overlay',{}).get('hf_repo_id') or x.get('recorded_hf_repo') or x.get('hf_repo_id')
 if x['name']=='setur_fo_instruct': repo='Setur/fo-instruct'
 e=x['integration_evidence']
 rows.append(dict(source=x['name'],repo=repo,tokens_per_epoch=e['tokens']*e['repeat'],component='dfm13'))
inheritance=json.loads(Path('data/dfm13/dfm12-full-inheritance-20261004-v2/inheritance.json').read_text())
for x in inheritance['sources']:
 if x['repeat']>0 and x['rows']>0:
  rows.append(dict(source=x['name'],repo=x['hf_repo_id'],tokens_per_epoch=x['tokens']*x['repeat'],component='dfm12'))
metadata=json.loads(Path('data/sampled_dfm13/metadata.json').read_text())
print(json.dumps(dict(rows=rows, base_metadata_sha256=inheritance['base']['metadata_sha256'],sampled_total=metadata['total_length'])))
'''
    remote = subprocess.check_output(
        ['ssh', '-p', '2850', '-o', 'BatchMode=yes', 'ucloud@ssh.cloud.sdu.dk',
         'cd /work/mimir/HRM-Text && /home/ucloud/miniforge3/envs/hrm/bin/python -'],
        input=remote_code.encode())
    remote = json.loads(remote)
    additions = remote['rows']
    mapping = {x.name: [x.repo_id] for x in HF_DATASETS}
    for line in Path('docs/dfm8-datasets.md').read_text().splitlines():
        if not line.startswith('| ['): continue
        # The prefix field can contain a brace-delimited union.
        repo = re.search(r'https://huggingface.co/datasets/([^)]*)', line).group(1)
        prefix = line.split(') | ', 1)[1].split(' | ', 1)[0]
        for name in prefix.strip('{}').split('|'):
            mapping[name] = [repo]
    packages = json.loads(Path('exports_dfm10/manifest.json').read_text())['packages']
    package_names = {p['name'] for p in packages}
    for spec in SPECS:
        root = Path(spec.source_root).name
        if root not in {'data', 'accepted', 'final', 'sapient_cleaned'}:
            mapping[root] = ['schneiderkamplab/' + spec.name]
        for pattern in spec.patterns:
            if not any(c in pattern for c in '*?'):
                mapping[pattern.split('__')[0]] = ['schneiderkamplab/' + spec.name]
    for source, suffix in PACKAGE_ALIASES.items():
        assert 'dfm10-' + suffix in package_names
        mapping[source] = ['schneiderkamplab/dfm10-' + suffix]
    mapping.update({
        'elrc_medical_en_da': ['qanastek/ELRC-Medical-V2'],
        'gsm_symbolic_da': ['danish-foundation-models/multilingual-gsm-symbolic'],
        'nhs_synthetic_clinical_notes': ['NHSEDataScience/synthetic_clinical_notes'],
    })
    report = json.loads(Path('docs/reports/dfm12_training_composition.json').read_text())
    assert report['provenance']['data/sampled_dfm11/metadata.json']['sha256'] == remote['base_metadata_sha256']
    rows = [r for r in report['source_rows'] if r['component']=='inherited_dfm11' and r['rows']>0]
    inherited = {}
    for row in rows:
        source = row['source']
        repos = mapping.get(source)
        if source == 'data':
            suffix = {'data__all_sft_splits.parquet': 'openstax-mimir-sft',
                      'data__model_charter_values_da.jsonl': 'synthetic-values-model-charter-da'}[row['task']]
            repos = ['schneiderkamplab/dfm10-' + suffix]
        if source == 'giannor_tv2r_instruction':
            repos = ['giannor/' + row['task'].split('__')[1].removeprefix('giannor_')]
        if source.startswith('folketingets-dokumenter-'):
            repos = ['schneiderkamplab/dfm10-' + source]
        sapient = {'Platypus': 'platypus', 'SYNTH': 'synth', 'acereason': 'acereason',
                   'ampsmathematica': 'amps-mathematica', 'dmmath': 'dmmath',
                   'sudoku_extreme': 'sudoku-extreme', 'tasksource': 'tasksource',
                   'textbookreasoning': 'textbook-reasoning', 'openthoughts2': 'openthoughts2'}
        if source in sapient:
            repos = ['schneiderkamplab/dfm10-sapient-' + sapient[source] + '-filtered-sft']
        if source in {'flan', 'flan_factual'}:
            family = row['task'].split('__')[1].split('_')[0]
            name = 'dfm10-sapient-flan-' + family + '-filtered-sft'
            assert name in package_names, row['task']
            repos = ['schneiderkamplab/' + name]
        if source.startswith('dfm11-'):
            name = re.sub(r'-(controlled|legacy-balanced)$', '', source)
            repos = ['schneiderkamplab/' + name]
        if source.startswith(('sapient-synth-', 'dfm8-', 'common-pile-', 'danish-dynaword-', 'transformations-')):
            repos = ['schneiderkamplab/' + source]
        if source in {'lexdk', 'dbc', 'dbc_repaired'}: repos = []
        previous = inherited.setdefault(source, dict(source=source, repos=repos,tokens_per_epoch=0))
        previous['tokens_per_epoch'] += row['rendered_tokens']
        if previous['repos'] is not None and repos is not None:
            previous['repos'] = sorted(set(previous['repos']) | set(repos))
    result = dict(scope='Finalized DFM13 plus sampled DFM11 base; unique payload repositories',
                  additions=additions, inherited=list(inherited.values()))
    unresolved = [r['source'] for r in additions if not r['repo']]
    unresolved += [r['source'] for r in inherited.values() if r['repos'] is None]
    repos = {r['repo'] for r in additions if r['repo']}
    repos.update(repo for row in inherited.values() for repo in (row['repos'] or []))
    result.update(unresolved=unresolved, repositories=sorted(repos), total=len(repos),
                  by_account=dict(sorted(Counter(r.split('/')[0] for r in repos).items())))
    result['inputs'] = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (
        'docs/reports/dfm12_training_composition.json', 'exports_dfm10/manifest.json',
        'docs/dfm8-datasets.md', 'scripts/download_training_datasets.py',
        'scripts/prepare_dfm10_hf_exports.py')}
    result['base_metadata_sha256'] = remote['base_metadata_sha256']
    result['non_hf_collections'] = ['Lex.dk', 'DBC (original and repaired views)']
    result['complete_mapping'] = not unresolved
    account_tokens = Counter()
    local_tokens = Counter()
    for row in additions:
        if row['repo']:
            account_tokens[row['repo'].split('/')[0]] += row['tokens_per_epoch']
    for row in inherited.values():
        accounts = {r.split('/')[0] for r in (row['repos'] or [])}
        if accounts:
            assert len(accounts) == 1, row
            account_tokens[next(iter(accounts))] += row['tokens_per_epoch']
        elif row['repos'] == []:
            local_tokens['Lex.dk' if row['source']=='lexdk' else 'DBC'] += row['tokens_per_epoch']
    result['tokens_per_epoch_by_account'] = dict(sorted(account_tokens.items()))
    result['tokens_per_epoch_non_hf'] = dict(local_tokens)
    result['tokens_per_epoch_total'] = sum(account_tokens.values()) + sum(local_tokens.values())
    result['remote_sampled_total_length'] = remote['sampled_total']
    assert result['tokens_per_epoch_total'] == remote['sampled_total'], (result['tokens_per_epoch_total'],remote['sampled_total'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    table = ['# DFM13 Repositories and Tokens by HF Account', '',
             'Corrected 2026-10-06: the previous 776 count omitted the separate DFM12 inheritance list.',
             'Unique published training-payload repositories; repeats affect tokens, not repository counts.',
             'Tokens include rendered prompts and targets, with sampling/repeats, for one epoch.', '',
             '| HF account | Repositories | Tokens/epoch (billions) |', '|---|---:|---:|']
    for account, count in sorted(result['by_account'].items(), key=lambda x: (-x[1],x[0])):
        table.append(f'| {account} | {count:,} | {account_tokens[account]/1e9:.6f} |')
    table.append(f'| **HF total** | **{len(repos):,}** | **{sum(account_tokens.values())/1e9:.6f}** |')
    for name, tokens in sorted(local_tokens.items()):
        table.append(f'| {name} (non-HF) | - | {tokens/1e9:.6f} |')
    table.append(f'| **Full epoch** | | **{result["tokens_per_epoch_total"]/1e9:.6f}** |')
    table.extend(['', 'The integer token sum equals the finalized remote sampled DFM13 metadata total_length exactly.',
                  'This is finalized expanded DFM13, not the older local October 2 training snapshot.'])
    args.output.with_suffix('.md').write_text('\n'.join(table)+'\n')
    print(json.dumps({k:result[k] for k in ('total','by_account','unresolved')},indent=2))
    if unresolved:
        raise SystemExit('Incomplete repository attribution; do not publish the total')


if __name__ == '__main__':
    main()
