#!/usr/bin/env python3
"""Build and sample DFM11-post from the completed, corrected DFM11 inventory."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

import yaml
import numpy as np
from dfm11_post_quality import ANCHOR_WEIGHTS, REPEAT_ONE, reviewed_stats

ROOT = Path(__file__).resolve().parents[1]

TWICE = set('''dfm11-synthetic-native-tool-calling-repaired
dfm11-glaive-native-tool-use-repaired dfm11-toolace-native-tool-use-repaired
dfm8-synthetic-constrained-format-following
dfm8-synthetic-danish-summarization-rewrite-controls
dfm8-synthetic-multiturn-danish-english-chat
dfm8-synthetic-strict-math-answer-contract
allenai_if_sft_verified allenai_if_multi_constraints_upto5 allenai_rlvr_ifeval
synquid_ifbench_train posttrain_coedit posttrain_asset
kobprof_skolegpt_instruct no_robots no_robots.jsonl'''.split())

FOCUS = TWICE | set('''dfm11-koolbardi-da dfm11-koolbardi-en
dfm11-fineinstructions-da dfm11-fineinstructions-en-controlled
dfm11-fineinstructions-en-legacy-balanced dfm11-nemotron-agentic-tool-calling-repaired
dfm11-folketingets-dokumenter-error-correction
dfm11-mathagentic-gsm8k-prolog dfm11-mathagentic-tinygsm-python
dfm8-openhermes-en dfm8-openhermes-da dfm8-synthetic-code-debugging
dolci_tool_use_repaired xlam_native_tool_use nemotron_agentic
nemotron_instruction_reasoning_off zai_deepdive_trajectories_sft
danish_persona_chats domsdatabasen_grounded_chats ai_arena_udtraek ai_arenaen_conversations
danish_wikipedia_open_chats.jsonl openstax_open_chats.jsonl tidsskrift_open_chats.jsonl
tidsskrift_open_sft.jsonl openstax_mimir_sft mimir_grounded_expanded_sft
mimir_answer_contract_calibration.jsonl ifeval_verifier.jsonl boolq_entailment.jsonl
drop_reasoning.jsonl event_coreference.jsonl posttrain_natural_instructions
govreport_summarization_repaired nordjylland_news_repaired wiki_cat_sum_repaired
scientific_summaries_repaired dfm4_arxiv_paper_summarization giannor_tv2r_instruction
andersen_modernization diem_modernization cor_sem alexandra_scandi_qa_da alexandra_dane
dsldk_danish_sentiment_lexicon.jsonl dsldk_danish_sentiment_lexicon_natural.jsonl
dsldk_danish_framenet.jsonl dsldk_danish_framenet_natural.jsonl
synquid_wiki_instruct_da synquid_danish_verifiable_reasoning
synquid_wildchat_100k_qwen_messages oliverkinch_instruct_bt
oliverkinch_multi_wiki_qa_high_quality oliverkinch_danish_qa
oliverkinch_danish_summarization oliverkinch_autodata_da_sft
oliverkinch_eur_lex_sum_instruct dst_table_prompts_repaired
dynaword_instruct_repaired danish_university_portals_bt_repaired
danmarks_statistik_bt_repaired dbc_repaired lexdk
dfm10_synthetic_values_model_charter dfm10_synthetic_values_model_charter_da'''.split())

EXCLUDE_PREFIXES = (
    'folketingets-dokumenter-', 'danish-dynaword-', 'common-pile-', 'transformations-',
    'opus', 'machine_translation_', 'oliverkinch_machine_translation_',
    'synquid_translation_', 'synquid_mt_', 'dmmath', 'ampsmathematica',
    'sudoku_extreme', 'bornholmsk_parallel', 'elrc_medical_', 'emea_medical_',
    'ecdc_public_health_', 'nhs_synthetic_', 'medquad_', 'danish_book_ads', 'sks_tei',
)
ANCHOR_PREFIXES = (
    'flan', 'SYNTH', 'sapient-synth-', 'sapient_', 'allenai_', 'tasksource',
    'Platypus', 'acereason', 'openthoughts', 'openmathinstruct2_repaired',
    'numinamath', 'code_meta_reasoning_repaired', 'textbookreasoning',
    'nemotron_swe_repaired', 'nemotron_terminal_corpus_native', 'nemotron_multilingual',
    'laerebogen_with_followups', 'dolci_instruct_sft', 'dfm_dyna_instruct',
    'oliverkinch_', 'croco_munin_da_sft', 'gsm_symbolic_da', 'kaenguruen',
    'alexandra_multi_zebra', 'gsm8k_train', 'math_train', 'webinstruct_verified',
    'omnimath',
)


def task_report(path):
    result = {}
    in_tasks = False
    for line in path.read_text().splitlines():
        if line == '### Task Coverage Stats':
            in_tasks = True
        elif line.startswith('### '):
            in_tasks = False
        if in_tasks and line.startswith('| **'):
            fields = line.split('|')
            name = fields[1].strip().removeprefix('**').removesuffix('**')
            values = [int(c.strip().split()[0].replace(',', '')) for c in fields[2:8]]
            if name in result:
                raise ValueError(f'Duplicate task in report: {name}')
            result[name] = dict(rows=values[0], tokens=values[1], sampled_tokens=values[3])
    if not result:
        raise ValueError(f'No task report in {path}')
    return result


def allocate(capacities, target, weight_factors=None):
    """Square-root source weighting with saturation, without replacement."""
    if target > sum(capacities.values()):
        raise ValueError('Insufficient unique anchor capacity for requested fraction')
    weights = {k: math.sqrt(v) * (weight_factors or {}).get(k, 1.) for k, v in capacities.items()}
    lo, hi = 0., max(v / weights[k] for k, v in capacities.items())
    for _ in range(80):
        mid = (lo + hi) / 2
        if sum(min(v, mid * weights[k]) for k, v in capacities.items()) < target:
            lo = mid
        else:
            hi = mid
    return {k: min(v, hi * weights[k]) for k, v in capacities.items()}


def validate_sampled_output(path, epochs):
    token_count = len(np.load(path / 'tokens.npy', mmap_mode='r'))
    totals = []
    for epoch in range(epochs):
        arrays = [np.load(path / f'epoch_{epoch}' / f'{name}.npy', mmap_mode='r')
                  for name in ('inst_start', 'inst_len', 'resp_start', 'resp_len')]
        if len({len(a) for a in arrays}) != 1 or not len(arrays[0]):
            raise ValueError(f'Invalid index arrays for epoch {epoch}')
        total = 0
        for start in range(0, len(arrays[0]), 1000000):
            ps, pl, rs, rl = (a[start:start + 1000000] for a in arrays)
            if (np.any(pl + rl > 4097) or np.any(rl == 0)
                    or np.any(ps >= token_count) or np.any(rs >= token_count)
                    or np.any(pl > token_count - ps) or np.any(rl > token_count - rs)):
                raise ValueError(f'Invalid token bounds in epoch {epoch}')
            total += int((pl + rl).sum())
        totals.append(total)
    metadata = json.loads((path / 'metadata.json').read_text())
    if round(sum(totals) / epochs) != metadata['total_length']:
        raise ValueError('Metadata token count disagrees with epoch indices')
    return totals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--epochs', type=int, default=10)
    parser.add_argument('--anchor-fraction', type=float, default=.33)
    parser.add_argument('--sample', action='store_true')
    parser.add_argument('--rebuild', action='store_true', help='Stage revised indices, reusing the validated token store')
    args = parser.parse_args()
    if not 0 < args.anchor_fraction < 1 or args.epochs < 1:
        parser.error('Require 0 < anchor fraction < 1 and positive epochs')
    subprocess.run([sys.executable, str(ROOT / 'scripts/validate_dfm11_sampling_policy.py')], check=True)
    source = ROOT / 'data/tokenized_dfm11'
    tree = ROOT / 'data/tokenized_dfm11_post'
    output = ROOT / 'data/sampled_dfm11_post'
    if args.rebuild and not args.sample:
        parser.error('--rebuild requires --sample')
    if not args.rebuild and (tree.exists() or output.exists()):
        raise FileExistsError('DFM11-post exists; use --rebuild for a staged replacement')
    logdir = ROOT / 'logs/dfm11_post'
    logdir.mkdir(exist_ok=True)
    if args.rebuild:
        if not tree.is_dir() or not (output / 'metadata.json').is_file():
            raise FileNotFoundError('Rebuild requires a complete existing post corpus')
        for suffix in ('.rebuilding', '.pre_quality_review'):
            if output.with_name(output.name + suffix).exists():
                raise FileExistsError(f'Inspect existing {output.name + suffix} before rebuilding')
        logdir = logdir / 'quality_rebuild'
        logdir.mkdir(exist_ok=True)
    masks = logdir / 'conversation_selections'
    masks.mkdir(exist_ok=True)
    report_path = ROOT / 'logs/dfm11/sample_corrected.log'
    rules_path = ROOT / 'data_io/prefix_config_dfm11.yaml'
    report = task_report(report_path)
    names = {p.name for p in source.iterdir() if p.is_dir()}
    if names != set(report):
        raise ValueError('Completed DFM11 report does not cover exactly the current union')
    baseline = yaml.safe_load(rules_path.read_text())
    tasks = []
    for name, stats in sorted(report.items()):
        family = name.split('__', 1)[0]
        rule = next((r for r in baseline if name.startswith(r['prefix'])), {})
        cap = min(stats['rows'], rule.get('max_per_file', stats['rows']))
        reason = None
        if not cap or not rule.get('repeat', 1):
            reason = 'inherited exclusion or empty'
        elif family.startswith(EXCLUDE_PREFIXES):
            reason = 'post exclusion'
        elif family in FOCUS or name == 'data__model_charter_values_da.jsonl':
            bucket = 'behavior'
        elif family.startswith(ANCHOR_PREFIXES):
            bucket = 'anchor'
        else:
            reason = 'unclassified: excluded pending review'
        item = dict(name=name, family=family, **stats, cap=cap,
                    repeat=2 if family in TWICE else 1,
                    long_context=rule.get('long_context', 'truncate'))
        if reason:
            item.update(bucket='excluded', reason=reason, selected_rows=0, expected_tokens=0)
        else:
            item.update(bucket=bucket, mean_tokens=stats['tokens'] / stats['rows'])
        tasks.append(item)

    # This source-level editing cap is independent of the number of input shards.
    correction = [t for t in tasks if t['family'] == 'dfm11-folketingets-dokumenter-error-correction']
    total = sum(t['cap'] for t in correction)
    if total:
        for t in correction:
            t['cap'] = min(t['cap'], math.floor(100000 * t['cap'] / total))
    behavior = [t for t in tasks if t['bucket'] == 'behavior']
    for t in behavior:
        reviewed_stats(ROOT, t, masks)
        if t['family'] in REPEAT_ONE:
            t['repeat'] = 1
        t.update(selected_rows=t['cap'], expected_tokens=t['cap'] * t['mean_tokens'] * t['repeat'])
    behavior_tokens = sum(t['expected_tokens'] for t in behavior)
    anchors = [t for t in tasks if t['bucket'] == 'anchor']
    capacities = defaultdict(float)
    for t in anchors:
        capacities[t['family']] += t['cap'] * t['mean_tokens']
    target = behavior_tokens * args.anchor_fraction / (1 - args.anchor_fraction)
    allocation = allocate(capacities, target, ANCHOR_WEIGHTS)
    for t in anchors:
        fraction = allocation[t['family']] / capacities[t['family']]
        count = math.floor(t['cap'] * fraction)
        t.update(selected_rows=count, repeat=1, expected_tokens=count * t['mean_tokens'])
    selected = [t for t in tasks if t['selected_rows'] > 0]
    if args.rebuild:
        # Keep the exact task layout, even for a newly empty selection, so the
        # existing immutable concatenated token store retains identical offsets.
        previous = json.loads((ROOT / 'logs/dfm11_post/manifest.json').read_text())
        for key, path in (('baseline_sha256', rules_path), ('report_sha256', report_path)):
            if previous[key] != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError('Baseline inventory changed; cannot safely reuse the post token store')
        old_names = {t['name'] for t in previous['tasks'] if t['selected_rows'] > 0}
        if not {t['name'] for t in selected} <= old_names:
            raise ValueError('Cannot reuse token store when adding task directories')
        selected = [t for t in tasks if t['name'] in old_names]
        if {p.name for p in tree.iterdir() if p.is_dir()} != old_names:
            raise ValueError('Existing task layout differs from manifest')
    anchor_tokens = sum(t['expected_tokens'] for t in anchors)
    summary = dict(behavior_tokens=behavior_tokens, anchor_tokens=anchor_tokens,
                   total_tokens=behavior_tokens + anchor_tokens,
                   anchor_fraction=anchor_tokens / (behavior_tokens + anchor_tokens),
                   behavior_tasks=len(behavior), anchor_tasks=len(anchors), epochs=args.epochs)
    # Never overwrite a corpus that may already be in use.
    if not args.rebuild:
        tree.mkdir()
        (tree / 'tokenizer_info.json').symlink_to((source / 'tokenizer_info.json').resolve())
        for t in selected:
            (tree / t['name']).symlink_to((source / t['name']).resolve(), target_is_directory=True)
    # Longest first prevents a task name that is a prefix of another from shadowing it.
    selected.sort(key=lambda t: (-len(t['name']), t['name']))
    rules = [dict(prefix=t['name'], max_per_file=t['selected_rows'],
                  repeat=t['repeat'], long_context=t['long_context'],
                  **({'selection_indices_path': t['selection_indices_path']}
                     if 'selection_indices_path' in t else {})) for t in selected]
    policy = ROOT / 'data_io/prefix_config_dfm11_post.yaml'
    staged_policy = logdir / 'prefix_config.yaml' if args.rebuild else policy
    staged_policy.write_text('# Generated by scripts/prepare_dfm11_post.py; exact task allowlist.\n'
                      + yaml.safe_dump(rules, sort_keys=False))
    manifest = dict(summary=summary, tasks=tasks, anchor_weighting='sqrt capped source token capacity',
                    anchor_quality_weights=ANCHOR_WEIGHTS,
                    baseline_sha256=hashlib.sha256(rules_path.read_bytes()).hexdigest(),
                    report_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest())
    (logdir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    if not args.rebuild:
        (tree / 'union_manifest.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)
    if args.sample:
        sampled_output = output
        if args.rebuild:
            sampled_output = output.with_name(output.name + '.rebuilding')
            sampled_output.mkdir()
            os.link(output / 'tokens.npy', sampled_output / 'tokens.npy')
        with (logdir / 'sample.log').open('w') as log:
            subprocess.run([sys.executable, '-u', 'sample_tokenized.py',
                            'tokenized_path=../data/tokenized_dfm11_post',
                            f'output_path={sampled_output}',
                            f'prefix_config_path={staged_policy}',
                            f'reuse_tokens={str(args.rebuild).lower()}',
                            'skip_unmatched=true', f'epochs={args.epochs}', 'concat_workers=16'],
                           cwd=ROOT / 'data_io', stdout=log, stderr=subprocess.STDOUT, check=True)
        actual = task_report(logdir / 'sample.log')
        measured = defaultdict(float)
        for t in selected:
            measured[t['bucket']] += actual[t['name']]['sampled_tokens'] / args.epochs
        measured['total_tokens'] = measured['behavior'] + measured['anchor']
        measured['anchor_fraction'] = measured['anchor'] / measured['total_tokens']
        if abs(measured['anchor_fraction'] - args.anchor_fraction) > .005:
            raise ValueError(f'Anchor share outside 0.5 percentage-point tolerance: {dict(measured)}')
        (logdir / 'measured.json').write_text(json.dumps(dict(measured), indent=2) + '\n')
        print(json.dumps(dict(measured), indent=2), flush=True)
        if args.rebuild:
            totals = validate_sampled_output(sampled_output, args.epochs)
            (logdir / 'validated_epoch_tokens.json').write_text(json.dumps(totals) + '\n')
            backup = output.with_name(output.name + '.pre_quality_review')
            if backup.exists():
                raise FileExistsError(backup)
            output.rename(backup)
            try:
                sampled_output.rename(output)
            except BaseException:
                backup.rename(output)
                raise
            archive = ROOT / 'logs/dfm11_post/pre_quality_review'
            archive.mkdir(exist_ok=True)
            for name in ('manifest.json', 'measured.json', 'sample.log'):
                current = ROOT / 'logs/dfm11_post' / name
                shutil.copy2(current, archive / name)
                shutil.copy2(logdir / name, current)
            shutil.copy2(policy, archive / 'prefix_config.yaml')
            shutil.copy2(staged_policy, policy)
            (tree / 'union_manifest.json').write_text(json.dumps(summary, indent=2) + '\n')
            print(f'Published {output}; rollback indices in {backup}', flush=True)


if __name__ == '__main__':
    main()
