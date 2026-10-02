#!/usr/bin/env python3
"""Build collection membership from the DFM8 ledger and DFM11 source policy."""
import json
import re
from pathlib import Path

import yaml

from prepare_dfm10_hf_exports import SPECS


def main():
    rows = []
    for line in Path('docs/dfm8-datasets.md').read_text().splitlines():
        match = re.match(r'\| \[([^]]+)\]\(https://huggingface.co/datasets/[^)]+\) \| (.*?) \|', line)
        if match:
            rows.append(match.groups())
    v1 = {repo for repo, _ in rows}
    rules = yaml.safe_load(Path('data_io/prefix_config_dfm11.yaml').read_text())
    active = {r['prefix'] for r in rules if r.get('max_per_file', 1) > 0 and r.get('repeat', 1) > 0}
    disabled = {r['prefix'] for r in rules if r['prefix'] not in active}
    replaced = ('glaive_native_tool_use__', 'toolace_native_tool_use__', 'folketingets-dokumenter-error-correction__', 'dfm8-synthetic-native-tool-calling__')
    active.difference_update(replaced)
    v15 = set()
    covered = set()
    for repo, prefix in rows:
        matches = {p for p in active if p.rstrip('_') == prefix or prefix.startswith(p)}
        excluded = any(prefix.startswith(p.rstrip('_')) for p in disabled | set(replaced))
        if not excluded:
            v15.add(repo)
            covered.update(matches)
    aliases = {
        'govreport_summarization_repaired__': 'dfm10-govreport-summarization-repaired',
        'wiki_cat_sum_repaired__': 'dfm10-wiki-cat-sum-repaired',
        'danmarks_statistik_bt_repaired__': 'dfm10-danmarks-statistik-bt-repaired',
        'nordjylland_news_repaired__': 'dfm10-nordjylland-news-repaired',
        'dst_table_prompts_repaired__': 'dfm10-dst-table-prompts-repaired',
        'dfm4_arxiv_paper_summarization__': 'dfm10-arxiv-paper-summarization-sft',
        'dfm11-fineinstructions-en-controlled__': 'dfm11-fineinstructions-en',
        'dfm11-fineinstructions-en-legacy-balanced__': 'dfm11-fineinstructions-en',
    }
    for p in active - covered:
        if p.startswith('dfm11-'):
            v15.add('schneiderkamplab/' + aliases.get(p, p.rstrip('_')))
            covered.add(p)
            continue
        for spec in SPECS:
            needle = p.rstrip('_')
            if p in aliases and spec.name == aliases[p] or any(
                needle in part for part in (spec.source_root, *spec.patterns)
            ):
                v15.add('schneiderkamplab/' + spec.name)
                covered.add(p)
    manual = {
        'elrc_medical_en_da__': 'qanastek/ELRC-Medical-V2',
        'emea_medical_da_en__': 'qanastek/EMEA-V3',
        'ecdc_public_health_en_da__': 'qanastek/ECDC',
        'nhs_synthetic_clinical_notes__': 'NHSEDataScience/synthetic_clinical_notes',
        'posttrain_coedit__': 'grammarly/coedit',
        'posttrain_asset__': 'facebook/asset',
        'gsm_symbolic_da__': 'danish-foundation-models/multilingual-gsm-symbolic',
        'dfm10_synthetic_values_model_charter__': 'danish-foundation-models/synthetic-values-model-charter',
        'alexandra_nordjylland_original__': 'alexandrainst/nordjylland-news-summarization',
        'dsldk_danish_framenet.jsonl': 'schneiderkamplab/dfm10-danish-framenet-sft',
        'dsldk_danish_framenet_natural.jsonl': 'schneiderkamplab/dfm10-danish-framenet-sft',
        'dsldk_danish_sentiment_lexicon.jsonl': 'schneiderkamplab/dfm10-danish-lexical-sentiment-sft',
        'dsldk_danish_sentiment_lexicon_natural.jsonl': 'schneiderkamplab/dfm10-danish-lexical-sentiment-sft',
    }
    for p, repo in manual.items():
        if p in active:
            v15.add(repo)
            covered.add(p)
    # Default-repeat sources integrated by the DFM10 union builder after their
    # finalization; completion is recorded in dfm10-residual-quality-audit-queue.
    for name in ('boolq-entailment', 'drop-reasoning', 'event-coreference', 'ifeval-verifier'):
        v15.add(f'schneiderkamplab/dfm10-mimir-{name}-sft')
    # These are aliases/group selectors already represented by the ledger;
    # the remaining unmatched placeholders had no coverage in the base build.
    accounted = {'flan__cot_', 'flan_factual__', 'synth_high40__', 'synth_repeat30__'}
    agreement = {p for p in active if p.startswith(('dbc_', 'lexdk__'))}
    placeholders = {'ai_arenaen_conversations__', 'allenai_if_multi_constraints_upto5__',
                    'allenai_rlvr_ifeval__', 'gsm8k_train.jsonl', 'math_train.jsonl',
                    'no_robots.jsonl', 'omnimath.jsonl', 'webinstruct_verified.jsonl'}
    result = {'collections': [
        {'title': 'Mimir Training Corpus v1', 'description': 'DFM8 training sources for Mimir v1. Selected splits/subsets and converted derivatives, not unrestricted use of every row. DBC and Lex.dk are agreement-only sources outside the Hub.', 'datasets': sorted(v1)},
        {'title': 'Mimir Training Corpus v1.5', 'description': 'DFM11 training sources for Mimir v1.5, including inherited sources and repaired replacements. Selected training subsets only. Agreement-only sources are not hosted on the Hub.', 'datasets': sorted(v15)},
    ], 'agreement_only_prefixes': sorted(agreement),
        'configured_placeholders_without_base_coverage': sorted(placeholders),
        'unresolved_dfm11_prefixes': sorted(active-covered-accounted-agreement-placeholders)}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
