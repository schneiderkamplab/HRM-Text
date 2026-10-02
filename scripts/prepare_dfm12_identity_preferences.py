#!/usr/bin/env python3
"""CPU-only reviewed EMA identity preferences; final-assistant-only SFT loss."""
import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import atomic, digest, file_hash, load, write_json
from scripts import evaluate_dfm12_identity_continuation_v4 as evaluation

SOURCE_SHA = 'c35216ad479e26c1542a266664922b6f74b6a371b6c975ce993ea53af506b787'
FACTS_SHA = 'd81c94652a494d84e9937299964baad5519f150e96bea056ce197d5c95488a71'
CORRECTION_SHA = 'b750f605d951fc22740d483fe4e913265427b3b711af44fbfc35490c2d3d476b'


def split_families(cases, seed='identity-ema-preferences-20260927-v1'):
    families = sorted({c['family'] for c in cases})
    if not families or any(not f for f in families):
        raise ValueError('Missing family')
    ordered = sorted(families, key=lambda f: digest([seed, f]))
    validation = set(ordered[:max(1, len(ordered) // 5)])
    result = {f: 'validation' if f in validation else 'train' for f in families}
    # Do not allow an identical user question to cross family splits.
    owners = {}
    for case in cases:
        for prompt in case['users']:
            key = ' '.join(prompt.casefold().split())
            if key in owners and owners[key] != result[case['family']]:
                raise ValueError('Cross-family duplicate prompt would leak across splits')
            owners[key] = result[case['family']]
    return result


def validate_source(path, expected_sha=SOURCE_SHA):
    if file_hash(path) != expected_sha:
        raise ValueError('Unpinned response source')
    report = load(path)
    if (report.get('ema') is not True or report.get('non_ema') is not False
            or report.get('wandb') is not False or report.get('identity_priming') is not False
            or report['status'] not in evaluation.v3.COMPLETED):
        raise ValueError('Require completed, unprimed EMA source only')
    if len(report['runs']) != 1 or report['runs'][0]['tag'] != 'step_2887261':
        raise ValueError('Require latest step2887261 only')
    run = report['runs'][0]
    if len(run.get('workers', [])) != 8 or any(
            not (w.get('ema_verification') or {}).get('verified') for w in run['workers']):
        raise ValueError('Missing all-worker EMA verification')
    if load(path.parent / 'completion.json')['responses_sha256'] != expected_sha:
        raise ValueError('Completion hash mismatch')
    expected, _, _ = evaluation.load_cases(ROOT / 'data/dfm12/identity-corrected-da-en-20260926-v4',
                                           CORRECTION_SHA, 'metadata/identity_correction.yaml')
    expected = [c for c in expected if c['suite'] == 'heldout']
    if report['cases'] != expected:
        raise ValueError('Source case bindings differ from approved source')
    if [c['id'] for c in run['conversations']] != [c['id'] for c in expected]:
        raise ValueError('Incomplete or reordered source coverage')
    for case, conversation in zip(expected, run['conversations']):
        evaluation.validate_conversation(case, conversation, report['max_new_tokens'], True)
    return report


def tokenize_final(tokenizer, prompt, chosen, original_rendered, original_ids):
    rendered = tokenizer.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True,
                                             enable_thinking=False)
    prefix = tokenizer.encode(rendered, add_special_tokens=False)
    if rendered != original_rendered or prefix != original_ids:
        raise ValueError('Exact source prompt/template/token binding changed')
    full = tokenizer.apply_chat_template(prompt + [{'role': 'assistant', 'content': chosen}],
                                        tokenize=False, add_generation_prompt=False, enable_thinking=False)
    tokens = tokenizer.encode(full, add_special_tokens=False)
    if not full.startswith(rendered) or tokens[:len(prefix)] != prefix or len(tokens) <= len(prefix):
        raise ValueError('Cannot establish exact final-only token loss boundary')
    if len(tokens) > 4096:
        raise ValueError('Chosen SFT exceeds context; never truncate history')
    return dict(input_ids=tokens, labels=[-100] * len(prefix) + tokens[len(prefix):],
                attention_mask=[1] * len(tokens), prompt_token_count=len(prefix))


def make_example(case, turn, review, split, source_sha):
    prompt = copy.deepcopy(turn['prompt_messages'])
    if any(m['role'] == 'system' for m in prompt) or prompt[-1] != {'role': 'user', 'content': turn['user']}:
        raise ValueError('No system interventions or changed last user turn')
    status = review['verdict']
    if status not in ('verified_correct', 'wrong', 'partial'):
        raise ValueError('Unreviewed output cannot enter training exports')
    chosen = turn['response'] if status == 'verified_correct' else review['chosen']
    if not chosen.strip() or (status == 'verified_correct' and turn['truncated']):
        raise ValueError('Empty/length-limited positive not verified')
    if status != 'verified_correct' and chosen == turn['response']:
        raise ValueError('Preference cannot have identical sides')
    if not review['reason'] or not review['facts']:
        raise ValueError('Missing factual review rationale')
    kind = review.get('preference_kind', {
        'wrong': 'factual_correction', 'partial': 'completeness',
        'verified_correct': 'verified_positive',
    }[status])
    if kind not in ('factual_correction', 'completeness', 'precision', 'style', 'verified_positive'):
        raise ValueError('Unknown preference kind')
    if (kind == 'verified_positive') != (status == 'verified_correct'):
        raise ValueError('Positive/preference kind mismatch')
    identifier = digest([source_sha, case['id'], turn['turn'], chosen])
    provenance = dict(source_sha256=source_sha, case_id=case['id'], turn=turn['turn'],
                      original_suite=case['suite'], current_use='development_identity_preferences',
                      family=case['family'], language=case['language'], ema=True, tag='step_2887261',
                      prompt_sha256=digest(prompt), response_sha256=digest(turn['response']),
                      rendered_prompt=turn['rendered_prompt'], prompt_token_ids=turn['prompt_token_ids'],
                      generated_token_ids=turn['generated_token_ids'], finish_reason=turn['finish_reason'],
                      preference_kind=kind, review=review, chosen_origin='verified_model_output' if status == 'verified_correct'
                      else 'individually_authored_fact_grounded_correction')
    sft = dict(id=identifier, split=split, preference_kind=kind, messages=prompt + [{'role': 'assistant', 'content': chosen}],
               message_loss_mask=[0] * len(prompt) + [1], provenance=provenance)
    pair = None if status == 'verified_correct' else dict(
        id=identifier, split=split, preference_kind=kind, prompt_messages=prompt,
        chosen_completion_messages=[{'role': 'assistant', 'content': chosen}],
        rejected_completion_messages=[{'role': 'assistant', 'content': turn['response']}],
        chosen_messages=prompt + [{'role': 'assistant', 'content': chosen}],
        rejected_messages=prompt + [{'role': 'assistant', 'content': turn['response']}], provenance=provenance)
    return sft, pair


def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with atomic(path) as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')


def build(source, reviews_path, output):
    from transformers import PreTrainedTokenizerFast
    source = Path(source).resolve()
    report = validate_source(source)
    reviews = yaml.safe_load(Path(reviews_path).read_text())
    if reviews['source_sha256'] != SOURCE_SHA or reviews['facts_sha256'] != FACTS_SHA:
        raise ValueError('Review provenance mismatch')
    facts_path = ROOT / 'data/dfm12/identity-repair-da-en-20260926-v3/metadata/identity_facts.yaml'
    if file_hash(facts_path) != FACTS_SHA:
        raise ValueError('Authoritative fact ledger changed')
    facts = yaml.safe_load(facts_path.read_text())
    correction_path = ROOT / 'data/dfm12/identity-corrected-da-en-20260926-v4/metadata/identity_correction.yaml'
    correction = yaml.safe_load(correction_path.read_text())
    allowed = set(facts['facts']) | {'xl-full-bp', 'current_runtime', 'continuation'}
    cases = report['cases']
    assignments = split_families(cases)
    assets = report['runtime_asset_binding']['assets']
    for asset in assets.values():
        if file_hash(asset['path']) != asset['sha256']:
            raise ValueError('Runtime text asset changed')
    tokenizer = PreTrainedTokenizerFast(tokenizer_file=assets['tokenizer']['path'])
    tokenizer.chat_template = Path(assets['template']['path']).read_text()
    for field, token in [('pad_token', '<pad>'), ('bos_token', '<bos>'), ('eos_token', '<turn|>')]:
        if tokenizer.convert_tokens_to_ids(token) != tokenizer.unk_token_id:
            setattr(tokenizer, field, token)
    selected, pairs, tokenized, seen = [], [], [], set()
    for review in reviews['reviews']:
        i, number = review['case'], review['turn']
        if (i, number) in seen:
            raise ValueError('Duplicate reviewed turn')
        seen.add((i, number))
        if not set(review['facts']) <= allowed:
            raise ValueError('Unknown factual authority')
        case = cases[i]
        turn = report['runs'][0]['conversations'][i]['turns'][number - 1]
        if turn['turn'] != number:
            raise ValueError('Review turn mismatch')
        sft, pair = make_example(case, turn, review, assignments[case['family']], SOURCE_SHA)
        encoded = tokenize_final(tokenizer, sft['messages'][:-1], sft['messages'][-1]['content'],
                                 turn['rendered_prompt'], turn['prompt_token_ids'])
        selected.append(sft)
        tokenized.append(dict(id=sft['id'], split=sft['split'], preference_kind=sft['preference_kind'], **encoded))
        if pair:
            pairs.append(pair)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'family-splits.json', dict(seed='identity-ema-preferences-20260927-v1',
               assigned_before_augmentation=True, families=assignments,
               caveat='Family-separated preference development validation, NOT an unseen benchmark'))
    write_json(output / 'review-ledger.json', reviews)
    write_json(output / 'facts.json', facts)
    write_json(output / 'authority-supplement.json', dict(
        correction_manifest_sha256=CORRECTION_SHA,
        correction_path=str(correction_path), correction_sha256=file_hash(correction_path),
        current_runtime=correction['runtime_binding'],
        runtime_asset_binding=report['runtime_asset_binding'], tokenizer_vocabulary_size=len(tokenizer),
        continuation='Originally random initialization and scratch training; later continuation loads learned '
                     'checkpoint weights rather than reinitializing them. Learning from generated text '
                     'does not itself copy the producer weights.',
        continuation_authority='Owner-approved v4 checkpoint_retention/generated_text_not_weights cases; '
                               'source report expected targets retained as corroborating provenance, not automatically copied corrections',
        xl_full_bp=facts['profiles']['xl-full-bp']))
    jsonl(output / 'prompt-pool.jsonl', [dict(case, suite='development_identity_preferences',
          original_suite=case['suite'], split=assignments[case['family']]) for case in cases])
    write_json(output / 'future-evaluation-policy.json', dict(
        reused_cases_are_development=True, sealed_evaluation_created=False,
        requirement='Create and seal new prompt families disjoint from these 25 BEFORE further tuning; '
                    'do not call current preference validation or stochastic derivatives a fresh benchmark',
        excluded_families=sorted(assignments)))
    for split in ('train', 'validation'):
        jsonl(output / 'chosen-sft' / f'{split}.jsonl', [r for r in selected if r['split'] == split])
        jsonl(output / 'chosen-sft-tokenized' / f'{split}.jsonl', [r for r in tokenized if r['split'] == split])
        jsonl(output / 'dpo' / f'{split}.jsonl', [r for r in pairs if r['split'] == split])
    lines = ['# EMA-only reviewed preferences', '',
             'Earlier generated assistant messages are exact context, NOT supervised targets.',
             'Use tokenized labels or enforce message_loss_mask; all-assistant-loss ingestion is unsafe.',
             'Unreviewed source answers are excluded. Good outputs have no fabricated rejected partner.',
             'Rejected means dispreferred, not necessarily false. Filter preference_kind=factual_correction for factual repairs only.',
             'These reused evaluation prompts are now preference-development data, not fresh test data.', '']
    for row in selected:
        p = row['provenance']
        lines += [f"## Case {p['review']['case']} turn {p['turn']} / {p['language']} / {row['split']}",
                  f"Family: {p['family']}; verdict: {p['review']['verdict']}; preference kind: {p['preference_kind']}",
                  'Authority: ' + ', '.join(p['review']['facts']), p['review']['reason'],
                  '### Exact input/history', json.dumps(row['messages'][:-1], ensure_ascii=False, indent=2),
                  '### Verified chosen', row['messages'][-1]['content'], '### Original EMA answer',
                  report['runs'][0]['conversations'][p['review']['case']]['turns'][p['turn'] - 1]['response'], '']
    with atomic(output / 'review.md') as f:
        f.write('\n\n'.join(lines))
    manifest = dict(schema='dfm12-ema-identity-preferences-v1', source=str(source), source_sha256=SOURCE_SHA,
                    source_mode='EMA_ONLY', tag='step_2887261', facts_path=str(facts_path), facts_sha256=FACTS_SHA,
                    review_source=str(Path(reviews_path).resolve()), review_source_sha256=file_hash(reviews_path),
                    script_sha256=file_hash(__file__), runtime_asset_binding=report['runtime_asset_binding'],
                    checkpoint=report['runs'][0]['checkpoint'], checkpoint_pins=report['runs'][0]['checkpoint_pins'],
                    reviewed_turns=len(selected), unreviewed_turns=140-len(selected), sft_rows=len(selected),
                    dpo_pairs=len(pairs), verdicts=dict(Counter(r['provenance']['review']['verdict'] for r in selected)),
                    preference_kinds=dict(Counter(r['preference_kind'] for r in selected)),
                    review_complete=len(selected) == 140,
                    pending_review=[dict(case=i, case_id=case['id'], turn=turn['turn'],
                                         family=case['family'], language=case['language'])
                                    for i, case in enumerate(cases)
                                    for turn in report['runs'][0]['conversations'][i]['turns']
                                    if (i, turn['turn']) not in seen],
                    split_counts={s:dict(sft=sum(r['split']==s for r in selected), dpo=sum(r['split']==s for r in pairs))
                                  for s in ('train','validation')},
                    no_system_messages=True, prior_assistant_loss=False, training_launched=False,
                    files={str(p.relative_to(output)):file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()})
    write_json(output / 'manifest.json', manifest)
    print(json.dumps({k:manifest[k] for k in ['reviewed_turns','unreviewed_turns','sft_rows','dpo_pairs','split_counts']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--reviews', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.reviews, args.output)
