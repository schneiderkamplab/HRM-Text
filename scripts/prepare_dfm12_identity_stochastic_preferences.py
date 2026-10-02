#!/usr/bin/env python3
"""CPU-only explicit semantic-review admission of pinned EMA stochastic answers."""
import argparse
import copy
import json
from collections import Counter
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import atomic, digest, file_hash, load, write_json
from scripts import prepare_dfm12_identity_preferences as previous
from scripts import queue_dfm12_identity_ema_samples as sampling

SOURCE_SHA = 'a9f16885642ef9946f43137846688803716c2e77d0a52668082bb9be175a4982'
BASE_SHA = 'ffe454b2e629f5b1cee21ab54a44b5d2a1e4ba54e411c4b29088e1b47980f5a7'


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def merge_review_ledgers(paths):
    """Merge complete per-sample reviews without replacing reviewer provenance."""
    reviews, sources, seen = [], [], set()
    for path in map(Path, paths):
        ledger = yaml.safe_load(path.read_text())
        if ledger['source_sha256'] != SOURCE_SHA or ledger['base_manifest_sha256'] != BASE_SHA:
            raise ValueError('Review ledger source pin mismatch')
        entries = ledger['reviews']
        samples = {r['sample'] for r in entries}
        if len(samples) != 1 or not samples <= set(range(4)):
            raise ValueError('Require one known sample per input ledger')
        sample = next(iter(samples))
        keys = [(r['case'], r['sample'], r['turn']) for r in entries]
        expected = {(i, sample, t) for i in range(100) for t in range(1, 3 if i < 40 else 2)}
        if len(keys) != 140 or set(keys) != expected or seen.intersection(keys):
            raise ValueError('Missing or duplicate per-sample coverage')
        seen.update(keys)
        provenance = dict(path=str(path.resolve()), sha256=file_hash(path), sample=sample,
                          reviewer=ledger['reviewer'], selection=ledger['selection'],
                          policy=ledger.get('policy'))
        sources.append(provenance)
        for entry in entries:
            if 'review_ledger_source' in entry:
                raise ValueError('Input review already has merged provenance')
            reviews.append(dict(copy.deepcopy(entry), review_ledger_source=provenance))
    expected = {(i, s, t) for i in range(100) for s in range(4)
                for t in range(1, 3 if i < 40 else 2)}
    if seen != expected:
        raise ValueError('Require exactly560unique reviews across all four samples')
    return dict(source_sha256=SOURCE_SHA, base_manifest_sha256=BASE_SHA,
        reviewer='Merged explicit reviews; original reviewer and ledger pins retained per row',
        selection='All four sampling indices,100cases each,560unique turns; no unreviewed stochastic admission',
        policy='Original row verdicts/corrections unchanged. Same-history pairs, final-only loss, '
               'family split and ambiguity exclusions remain required. These prompts are development.',
        source_ledgers=sources, reviews=sorted(reviews, key=lambda r:(r['case'], r['sample'], r['turn'])))


def validate_sources(source, base):
    if file_hash(source) != SOURCE_SHA or file_hash(base/'manifest.json') != BASE_SHA:
        raise ValueError('Unpinned stochastic/base source')
    baseline = load(base/'manifest.json')
    for name, sha in baseline['files'].items():
        if file_hash(base/name) != sha:
            raise ValueError('Base corpus file changed: ' + name)
    report = load(source)
    if (report.get('ema') is not True or report.get('non_ema') is not False
            or report.get('wandb') is not False or report.get('identity_priming') is not False
            or report['status'] not in previous.evaluation.v3.COMPLETED
            or load(source.parent/'completion.json')['responses_sha256'] != SOURCE_SHA
            or report['sampling'] != dict(temperature=0.7, top_p=0.9, samples_per_conversation=4)
            or report['source_greedy_sha256'] != baseline['source_sha256']):
        raise ValueError('Require completed, unprimed, bound stochastic EMA source')
    expected = sampling.expand_cases(read_rows(base/'prompt-pool.jsonl'))
    if report['cases'] != expected or len(expected) != 400 or len(report['runs']) != 1:
        raise ValueError('Changed stochastic case/split/seed coverage')
    run = report['runs'][0]
    if (run['tag'] != 'step_2887261' or run['checkpoint_pins'] != baseline['checkpoint_pins']
            or len(run['workers']) != 8 or {w['gpu'] for w in run['workers']} != set(range(8))
            or any(w['status'] != 'complete' or not w['ema_verification']['verified'] for w in run['workers'])
            or [c['id'] for c in run['conversations']] != [c['id'] for c in expected]):
        raise ValueError('Missing EMA verification or conversation coverage')
    for case, conversation in zip(expected, run['conversations']):
        previous.evaluation.validate_conversation(case, conversation, report['max_new_tokens'], True)
    return report, baseline


def resolve_review(review, base_row, case, turn):
    review = copy.deepcopy(review)
    if review['case'] != base_row['provenance']['review']['case']:
        raise ValueError('Original prompt reference mismatch')
    if (case['source_case_id'] != base_row['provenance']['case_id']
            or turn['user'] != base_row['messages'][-2]['content']):
        raise ValueError('Question changed from reviewed prompt family')
    if review.get('reuse_chosen'):
        # First turns have no generated assistant history to accidentally substitute.
        if (turn['turn'] != 1 or turn['prompt_messages'] != base_row['messages'][:-1]
                or review['verdict'] == 'verified_correct' or 'chosen' in review):
            raise ValueError('Chosen reuse requires explicitly reviewed identical first-turn prompt')
        review['chosen'] = base_row['messages'][-1]['content']
        review['chosen_source_id'] = base_row['id']
        review['chosen_reuse_scope'] = 'Manually approved for this same first-turn question; not automatic admission'
    elif review['verdict'] != 'verified_correct' and 'chosen' not in review:
        raise ValueError('Missing individually reviewed correction')
    review.setdefault('facts', base_row['provenance']['review']['facts'])
    if not review.get('reason', '').strip():
        raise ValueError('Review reason required')
    return review


def annotate_ambiguity(row, original_case):
    row = copy.deepcopy(row)
    ambiguous = original_case in (0, 1) and row['provenance']['turn'] == 1
    row['prompt_ambiguity'] = 'weight_training_can_mean_bodybuilding' if ambiguous else None
    row['identity_deficit_evidence_eligible'] = not ambiguous
    return row


def targeted_rows(rows, encoded):
    by_id = {r['id']: r for r in encoded}
    selected, seen = [], {}
    for row in rows:
        if row['preference_kind'] not in ('factual_correction', 'verified_positive') or row['prompt_ambiguity']:
            continue
        tokens = by_id[row['id']]
        key = digest([tokens['input_ids'], tokens['labels']])
        if key in seen:
            if seen[key]['split'] != row['split']:
                raise ValueError('Identical supervised example crosses split')
            seen[key]['source_row_ids'].append(row['id'])
            continue
        record = dict(copy.deepcopy(tokens), family=row['provenance']['family'],
                      language=row['provenance']['language'], source_row_ids=[row['id']])
        selected.append(record)
        seen[key] = record
    return selected


def token_counts(rows):
    return dict(rows=len(rows), rendered_tokens=sum(len(r['input_ids']) for r in rows),
                target_tokens=sum(sum(t != -100 for t in r['labels']) for r in rows),
                max_sequence_tokens=max((len(r['input_ids']) for r in rows), default=0))


def packer_subset(output, rows, binding, pending, ledger_sha):
    for split in ('train','validation'):
        previous.jsonl(output/'chosen-sft-tokenized'/f'{split}.jsonl', [r for r in rows if r['split']==split])
    manifest = dict(schema='reviewed-ema-sft-subset-v1', source_mode='EMA_ONLY',
        review_complete=True, unreviewed_turns=0, prior_assistant_loss=False,
        review_scope='Every exported row explicitly reviewed; NOT every source answer reviewed',
        excluded_unreviewed_source_turns=pending, source_sha256=SOURCE_SHA, base_manifest_sha256=BASE_SHA,
        review_ledger_sha256=ledger_sha, runtime_asset_binding=binding, training_launched=False,
        split_counts={s:dict(sft=sum(r['split']==s for r in rows)) for s in ('train','validation')},
        files={str(p.relative_to(output)):file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()})
    write_json(output/'manifest.json',manifest)


def recipe(targeted):
    train = [r for r in targeted if r['split'] == 'train']
    stats = token_counts(train)
    return dict(status='user_authorized_plan_parent_owned_not_launched', source_mode='EMA_ONLY',
        supersedes='Earlier one-pass/max20updates and EMA-weight initialization proposals; user authorization2026-09-27',
        initialization='Resume latest normal training checkpoint weights plus optimizer and existing EMA state unchanged; no EMA-weight conversion or reset',
        selection='Deduplicated factual_correction plus verified_positive; ambiguous initial weight-training prompts excluded',
        data=stats, optimizer_updates=10000,
        mixture=dict(identity_fraction=0.05, dfm11_fraction=0.95,
                     owner='Parent owns actual mixture construction and sampling semantics'),
        lr=1e-5, lr_auto=True, warmup_updates=0, lr_schedule='constant_no_decay',
        exposure_accounting=dict(assumed_global_batch_tokens=262144,
            identity_rendered_token_budget=262144*10000*0.05,
            estimated_rendered_corpus_passes=(262144*10000*0.05/stats['rendered_tokens']
                                             if stats['rendered_tokens'] else None),
            caveat='Token-share estimate, not measured repeats. Parent must confirm actual batch, '
                   'row/token mixture semantics, packing and repeats; this accounting does not change authorized10000updates.'),
        ema=dict(decay=0.9999, state='preserve_existing_unchanged', reset=False,
            initialize_training_from_ema=False, update_unit='optimizer update',
            old_weight_fraction={str(n):0.9999**n for n in (1,10,20,50,100,1000,10000)},
            evaluation_and_export='EMA_ONLY'),
        prerequisite_gates=['Independent review of chosen answers (Tesla/parent)',
            'Parent CPU packer preserves exact final-only labels and independent validation split',
            'Parent accepts merged corpus and actual V1 CPU label validation before readiness receipt',
            'Verify resumed normal weights, optimizer state and unchanged existing EMA state',
            'Seal new disjoint prompt-composition holdout before optimization'],
        dpo=dict(status='data_candidate_only_not_training_ready',
            initial_filter='factual_correction only; omit length-stopped rejections for initial preference experiment',
            requirements=['Pin reference model to the approved EMA source or approved post-SFT policy',
                'Verify completion-only log probabilities on identical history, including EOS handling',
                'CPU loss/gradient and integration tests for the actual DPO trainer before use',
                'Avoid style/precision negatives being treated as factual failures',
                'Fresh approval after corrective SFT semantic review; no automatic chaining']),
        sealed_holdout=dict(status='not_created', scope='New prompt compositions of SAME approved facts, not unseen knowledge',
            plan='Separate author creates20conversations per language with at least10multi-turn per language; '
                 'disambiguated model-weight wording, counterfactual role corrections, component/weight distinctions and arithmetic compositions. '
                 'Deduplicate full user turns against all training/development pools, seal hash and reviewer expectations before tuning. '
                 'No examples generated or added by this preparation. Existing100prompts remain development.'))


def build(source, base, reviews_path, output):
    from transformers import PreTrainedTokenizerFast
    source, base, output = Path(source).resolve(), Path(base).resolve(), Path(output).resolve()
    report, baseline = validate_sources(source, base)
    ledger = yaml.safe_load(Path(reviews_path).read_text())
    if ledger['source_sha256'] != SOURCE_SHA or ledger['base_manifest_sha256'] != BASE_SHA:
        raise ValueError('Review ledger source pin mismatch')
    base_rows = [r for split in ('train','validation') for r in read_rows(base/'chosen-sft'/f'{split}.jsonl')]
    rows = [annotate_ambiguity(r, r['provenance']['review']['case']) for r in base_rows]
    pairs = [annotate_ambiguity(r, r['provenance']['review']['case'])
             for split in ('train','validation') for r in read_rows(base/'dpo'/f'{split}.jsonl')]
    encoded = [r for split in ('train','validation') for r in read_rows(base/'chosen-sft-tokenized'/f'{split}.jsonl')]
    references = {(r['provenance']['review']['case'], r['provenance']['turn']): r for r in base_rows}
    assets = report['runtime_asset_binding']['assets']
    for asset in assets.values():
        if file_hash(asset['path']) != asset['sha256']:
            raise ValueError('Runtime tokenizer/template changed')
    tokenizer = PreTrainedTokenizerFast(tokenizer_file=assets['tokenizer']['path'])
    tokenizer.chat_template = Path(assets['template']['path']).read_text()
    tokenizer.pad_token, tokenizer.bos_token, tokenizer.eos_token = '<pad>', '<bos>', '<turn|>'
    cases = report['cases']
    index = {(i//4, c['sampling_index']): i for i,c in enumerate(cases)}
    seen, reviewed, readable = set(), [], ['# Stochastic EMA semantic review', '',
        'Coverage is explicit and partial. No lexical autopass. All reused prompts are DEVELOPMENT.',
        'Same first-turn chosen reuse is explicitly approved row by row; generated followups receive history-specific authored corrections.',
        'Correct/partial/wrong is a response-level judgment; factual_correction includes unsupported claims and is not a count of proven lies.', '']
    allowed = set(load(base/'facts.json')['facts']) | {'xl-full-bp','current_runtime','continuation'}
    for entry in ledger['reviews']:
        key = (entry['case'],entry['sample'],entry['turn'])
        if key in seen or key[:2] not in index or key[2] < 1:
            raise ValueError('Duplicate/unknown reviewed turn')
        seen.add(key)
        i = index[key[:2]]
        case, convo = cases[i], report['runs'][0]['conversations'][i]
        turn = convo['turns'][key[2]-1]
        review = resolve_review(entry, references[(key[0],key[2])], case, turn)
        if not set(review['facts']) <= allowed:
            raise ValueError('Unknown authority reference')
        sft, pair = previous.make_example(case, turn, review, case['split'], SOURCE_SHA)
        sft['provenance'].update(source_path=str(source), original_case_index=key[0], sampling_index=key[1],
            sampling_seed=case['sampling_seed'], source_case_id=case['source_case_id'],
            history_verified=True, reviewer=ledger['reviewer'])
        sft = annotate_ambiguity(sft, key[0])
        if pair:
            pair['provenance'] = copy.deepcopy(sft['provenance'])
            pairs.append(annotate_ambiguity(pair, key[0]))
        tokens = previous.tokenize_final(tokenizer, sft['messages'][:-1], sft['messages'][-1]['content'],
                                         turn['rendered_prompt'], turn['prompt_token_ids'])
        rows.append(sft)
        encoded.append(dict(id=sft['id'], split=sft['split'], preference_kind=sft['preference_kind'], **tokens))
        reviewed.append(dict(review, id=sft['id'], case_id=case['id'], prompt_sha256=digest(turn['prompt_messages']),
                             response_sha256=digest(turn['response']), preference_kind=sft['preference_kind'],
                             language=case['language'], family=case['family'], prompt_ambiguity=sft['prompt_ambiguity']))
        readable += [f"## Prompt {key[0]} / sample {key[1]} / turn {key[2]} / {case['language']} / {case['split']}",
            f"Verdict: {review['verdict']}; preference: {sft['preference_kind']}; ambiguity: {sft['prompt_ambiguity']}",
            review['reason'], 'Authority: '+', '.join(review['facts']),
            '### Exact history', json.dumps(turn['prompt_messages'], ensure_ascii=False, indent=2),
            '### Original sampled response', turn['response'], '### Reviewed chosen', sft['messages'][-1]['content'], '']
    pending = [dict(case=i//4, sample=c['sampling_index'], case_id=c['id'], turn=t['turn'],
                    family=c['family'], language=c['language']) for i,c in enumerate(cases)
               for t in report['runs'][0]['conversations'][i]['turns']
               if (i//4,c['sampling_index'],t['turn']) not in seen]
    targeted = targeted_rows(rows, encoded)
    output.mkdir(parents=True, exist_ok=False)
    for split in ('train','validation'):
        for folder, items in [('chosen-sft',rows),('chosen-sft-tokenized',encoded),('dpo',pairs),
                              ('targeted-chosen-sft-tokenized',targeted)]:
            previous.jsonl(output/folder/f'{split}.jsonl', [r for r in items if r['split']==split])
        previous.jsonl(output/'dpo-factual-eos'/f'{split}.jsonl', [r for r in pairs if r['split']==split
                       and r['preference_kind']=='factual_correction' and not r['prompt_ambiguity']
                       and r['provenance']['finish_reason']=='eos'])
    write_json(output/'review-ledger.json', dict(source_sha256=SOURCE_SHA, reviewer=ledger['reviewer'],
                                               selection=ledger['selection'], reviews=reviewed))
    write_json(output/'pending-review.json', dict(source_sha256=SOURCE_SHA, rows=pending))
    for name in ('family-splits.json','facts.json','authority-supplement.json','future-evaluation-policy.json'):
        write_json(output/name, load(base/name))
    write_json(output/'corrective-sft-recipe.json', recipe(targeted))
    for folder, subset in [('admitted-sft',encoded),('targeted-sft',targeted)]:
        packer_subset(output/folder,subset,report['runtime_asset_binding'],len(pending),file_hash(output/'review-ledger.json'))
    with atomic(output/'review.md') as handle:
        handle.write('\n\n'.join(readable))
    stats = {split: dict(sft=token_counts([r for r in encoded if r['split']==split]),
                         targeted_sft=token_counts([r for r in targeted if r['split']==split]),
                         dpo_pairs=sum(r['split']==split for r in pairs)) for split in ('train','validation')}
    manifest = dict(schema='dfm12-ema-stochastic-reviewed-preferences-v1', source_mode='EMA_ONLY',
        tag='step_2887261', source=str(source), source_sha256=SOURCE_SHA, base=str(base), base_manifest_sha256=BASE_SHA,
        review_source=str(Path(reviews_path).resolve()), review_source_sha256=file_hash(reviews_path),
        script_sha256=file_hash(__file__), helper_sha256=file_hash(previous.__file__),
        stochastic_total_turns=560, stochastic_reviewed_turns=len(reviewed), stochastic_pending_turns=len(pending),
        stochastic_review_complete=not pending, inherited_reviewed_turns=len(base_rows),
        sft_rows=len(rows), dpo_pairs=len(pairs), split_counts=stats,
        stochastic_verdicts=dict(Counter(r['verdict'] for r in reviewed)),
        stochastic_preference_kinds=dict(Counter(r['preference_kind'] for r in reviewed)),
        per_language={lang:dict(reviewed=sum(r['language']==lang for r in reviewed),
                               pending=sum(r['language']==lang for r in pending)) for lang in ('da','en')},
        prompt_ambiguity_policy='Original first-turn prompts0and1 may mean bodybuilding; exclude from identity-deficit claims and targeted SFT. Unverified physique claims still lack authority.',
        raw_auto_admission=False, same_history_pairs=True, final_only_labels=True, training_launched=False,
        runtime_asset_binding=report['runtime_asset_binding'], checkpoint_pins=report['runs'][0]['checkpoint_pins'],
        files={str(p.relative_to(output)):file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()})
    write_json(output/'manifest.json', manifest)
    print(json.dumps({k:manifest[k] for k in ('stochastic_reviewed_turns','stochastic_pending_turns','sft_rows','dpo_pairs','split_counts')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--reviews',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    build(args.source,args.base,args.reviews,args.output)
