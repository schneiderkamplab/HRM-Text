"""Local-only, immutable audit candidates; never training admission or publication."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path

from scripts.prepare_dfm13_arena import message, sha256
from scripts.prepare_dfm13_ai_arenaen import selected_examples
from scripts.review_dfm13_arena_candidates import parse_numpy_repr

ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = ROOT / 'data/downloads/arena_review'
HUB = Path('/work/mimir/.home/.cache/huggingface/hub')
SPECS = {
    'comparia': dict(repo='ministere-culture/comparia-fr-arena', directory='comparia-fr-arena',
        file='comparia-fr-arena_samples.jsonl', split='publisher_sample_of_train',
        license='Etalab-2.0 and CC-BY-4.0; third-party model-output terms apply'),
    'helpsteer3_edit': dict(repo='nvidia/HelpSteer3', directory='HelpSteer3',
        file='edit/train.jsonl.gz', split='train', license='CC-BY-4.0'),
    'helpsteer3_preference': dict(repo='nvidia/HelpSteer3', directory='HelpSteer3',
        file='preference/train.jsonl.gz', split='train', license='CC-BY-4.0'),
    'expert5k': dict(repo='lmarena-ai/arena-expert-5k', directory='arena-expert-5k',
        file='data/train-00000-of-00001.parquet', split='train',
        license='CC-BY-4.0 prompts; model outputs subject to provider terms'),
    'prism': dict(repo='HannahRoseKirk/prism-alignment', directory='prism-alignment',
        file='conversations.jsonl', split='unsplit_conversation_release',
        license='CC-BY-4.0 human text; CC-BY-NC-4.0 model responses plus provider terms'),
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     allow_nan=False).encode()).hexdigest()


def json_write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def records(path):
    if path.suffix == '.parquet':
        import pyarrow.parquet as pq
        for batch in pq.ParquetFile(path).iter_batches(batch_size=64):
            yield from batch.to_pylist()
    else:
        with (gzip.open(path, 'rt') if path.suffix == '.gz' else path.open()) as stream:
            for line in stream:
                yield json.loads(line)


def text_messages(raw):
    if not isinstance(raw, list):
        raise ValueError('messages_not_list')
    for m in raw:
        if not isinstance(m, dict) or any(m.get(k) for k in ('tool_calls', 'tool_call_id', 'images')):
            raise ValueError('unsupported_tool_or_media_message')
    return [message(m) for m in raw]


def validate_dialogue(messages):
    if not messages:
        raise ValueError('empty_history')
    body = messages[1:] if messages[0]['role'] == 'system' else messages
    if len(body) < 2 or len(body) % 2 or any(
            m['role'] != ('user' if i % 2 == 0 else 'assistant') for i, m in enumerate(body)):
        raise ValueError('nonalternating_history')
    if any(not isinstance(m['content'], str) or not m['content'].strip() for m in messages):
        raise ValueError('empty_message')


def fingerprint(row):
    # Exact supervised example, not target text or shared-document overlap.
    return digest(dict(messages=row['messages'], target_message_index=row['target_message_index'],
        tools=row.get('tools', []), chat_template_kwargs=row.get('chat_template_kwargs', {})))


def build_example(name, sid, messages, metadata):
    validate_dialogue(messages)
    return dict(id=f'{name}:{sid}', messages=messages, target_message_index=len(messages)-1,
        chat_template_kwargs={'enable_thinking': False}, metadata=dict(metadata,
            source_id=str(sid), audit_status='unaudited', admission_authorized=False,
            license_policy='held_noncommercial' if name == 'prism' else 'source_terms_review_required',
            content_sha256=digest(messages)))


def convert(name, row, line, revision, prism_min_score=80):
    spec = SPECS[name]
    metadata = dict(source=spec['repo'], revision=revision, source_file=spec['file'],
        source_line=line, split=spec['split'], license=spec['license'], raw_row_sha256=digest(row))
    if name == 'comparia':
        # Reuse the Danish turn locator, preserving only visible selected-turn text.
        safe = dict(row)
        for key in ('response_a', 'response_b', 'full_conversation_a', 'full_conversation_b'):
            safe[key] = text_messages(row[key])
        result = []
        for example in selected_examples(safe, revision):
            provenance = {k:v for k,v in example['metadata'].items()
                          if k not in ('source', 'revision', 'license')}
            result.append(build_example(name, example['id'], example['messages'],
                dict(metadata, **provenance, language=row.get('metadata', {}).get('languages', 'unspecified'))))
        return result
    if name.startswith('helpsteer3'):
        history = text_messages(row['context'])
        if not history or history[-1]['role'] != 'user':
            raise ValueError('context_does_not_end_in_user')
        if name.endswith('preference'):
            score = row['overall_preference']
            if type(score) not in (int, float) or not math.isfinite(score) or not -3 <= score <= 3:
                raise ValueError('invalid_preference_score')
            if score == 0:
                return []
            side = 'response1' if score < 0 else 'response2'
            answer = row[side]
            extra = dict(selected_side=side, preference=score,
                         individual_preference=row['individual_preference'])
        else:
            answer = row['edited_response']
            extra = dict(selected_side='human_edit', original_response_sha256=digest(row['original_response']),
                         feedback=row['feedback'], change_summary=row['change_summary'])
        return [build_example(name, str(line), history + [message(dict(role='assistant', content=answer))],
            dict(metadata, **extra, language=row['language'], domain=row['domain']))]
    if name == 'expert5k':
        if row['winner'] not in ('model_a', 'model_b'):
            if row['winner'] not in ('tie', 'both_bad', 'tie (bothbad)'):
                raise ValueError('unknown_vote')
            return []
        side = row['winner'][-1]
        current = text_messages(parse_numpy_repr(row['conversation_' + side]))
        full = []
        for turn in parse_numpy_repr(row['full_conversation']):
            full.extend(text_messages([turn['user'], turn['model_' + side]]))
        matches = [i for i in range(0, len(full)-len(current)+1, 2)
                   if full[i:i+len(current)] == current]
        if not current or len(matches) != 1:
            raise ValueError('ambiguous_or_missing_history_match')
        return [build_example(name, row['id']+':'+side, full[:matches[0]+len(current)],
            dict(metadata, selected_side=side, winner=row['winner'], model=row['model_'+side],
                 language=row['language'], evaluation_order=row['evaluation_order'],
                 occupational_tags=row['occupational_tags']))]
    if name != 'prism':
        raise ValueError('unknown_component')
    groups = {}
    for m in row['conversation_history']:
        if type(m.get('turn')) is not int or m['turn'] < 0 or m.get('role') not in ('user', 'model'):
            raise ValueError('invalid_prism_turn')
        groups.setdefault(m['turn'], []).append(m)
    if list(groups) != list(range(len(groups))):
        raise ValueError('noncontiguous_prism_turns')
    history, result, lineage = [], [], []
    for turn, entries in groups.items():
        users = [m for m in entries if m['role'] == 'user']
        chosen = [m for m in entries if m['role'] == 'model' and m.get('if_chosen') is True]
        if len(users) != 1 or not chosen or len({m['content'] for m in chosen}) != 1:
            raise ValueError('ambiguous_prism_branch')
        history += text_messages(users)
        target = message(dict(role='assistant', content=chosen[0]['content']))
        lineage.append(dict(turn=turn, chosen_within_turn_ids=[m['within_turn_id'] for m in chosen],
                            identical_chosen_collapsed=len(chosen)-1))
        for m in chosen:
            score = m['score']
            if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 100:
                raise ValueError('invalid_prism_score')
            if score >= prism_min_score:
                sid = f"{row['conversation_id']}:{turn}:{m['within_turn_id']}"
                result.append(build_example(name, sid, history+[target],
                    dict(metadata, conversation_id=row['conversation_id'], turn=turn,
                         within_turn_id=m['within_turn_id'], chosen_score=score, model=m['model_name'],
                         model_provider=m['model_provider'], language='unspecified',
                         conversation_type=row['conversation_type'], branch_lineage=list(lineage))))
        # Multiple chosen labels in the release can point to identical responses.
        # They are one context turn, never consecutive assistant messages.
        history.append(target)
    return result


def source_pin(downloads, name, hub):
    spec = SPECS[name]
    directory = downloads/spec['directory']
    path = directory/spec['file']
    receipt = directory/'.cache/huggingface/download'/(spec['file']+'.metadata')
    revision, etag, *_ = receipt.read_text().splitlines()
    if len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision):
        raise ValueError('invalid_source_revision')
    actual = sha256(path)
    if len(etag) == 64 and actual != etag:
        raise ValueError('download_receipt_hash_mismatch')
    card = hub/('datasets--'+spec['repo'].replace('/', '--'))/'snapshots'/revision/'README.md'
    return dict(path=str(path.resolve()), sha256=actual, revision=revision,
        receipt_path=str(receipt.resolve()), receipt_sha256=sha256(receipt),
        card_path=str(card), card_sha256=sha256(card), **spec)


def prepare(output, downloads=DOWNLOADS, prior_config=ROOT/'config/dfm13_sources.json', hub=HUB):
    output = output.resolve()
    if output.exists():
        raise ValueError('Fresh output root required; originals are immutable')
    pins = {name:source_pin(downloads, name, hub) for name in SPECS}
    output.mkdir(parents=True)
    seen, prior = {}, []
    for spec in json.loads(prior_config.read_text())['additions']:
        path = ROOT/spec['output']
        before = sha256(path)
        count = 0
        for row in records(path):
            count += 1
            seen.setdefault(fingerprint(row), dict(source=spec['name'], id=row['id'], path=str(path)))
        prior.append(dict(path=str(path), rows=count, sha256=before))
    sources = []
    for name, pin in pins.items():
        component = output/name
        component.mkdir()
        counts, languages = Counter(), Counter()
        ids = set()
        with (component/'candidates.jsonl').open('x') as stream, (component/'exclusions.jsonl').open('x') as ledger:
            for line, row in enumerate(records(Path(pin['path'])), 1):
                counts['source_rows'] += 1
                try:
                    candidates = convert(name, row, line, pin['revision'])
                except (ValueError, KeyError, TypeError, SyntaxError, RecursionError) as exc:
                    counts['invalid_source_rows'] += 1
                    ledger.write(json.dumps(dict(source_line=line, raw_row_sha256=digest(row),
                        reason=str(exc), disposition='structural_hold'), ensure_ascii=False)+'\n')
                    continue
                if not candidates:
                    counts['unselected_source_rows'] += 1
                for example in candidates:
                    counts['selected_before_dedup'] += 1
                    if example['id'] in ids:
                        raise ValueError('Duplicate source identity: '+example['id'])
                    ids.add(example['id'])
                    key = fingerprint(example)
                    if key in seen:
                        counts['exact_duplicates'] += 1
                        ledger.write(json.dumps(dict(id=example['id'], source_line=line,
                            reason='exact_supervised_example_duplicate', fingerprint=key,
                            duplicate_of=seen[key], attribution=example['metadata']), ensure_ascii=False)+'\n')
                        continue
                    seen[key] = dict(source=name, id=example['id'], path=str(component/'candidates.jsonl'))
                    stream.write(json.dumps(example, ensure_ascii=False, allow_nan=False)+'\n')
                    counts['candidate_rows'] += 1
                    counts['multiturn_rows'] += len(example['messages']) > 2
                    language = example['metadata']['language']
                    languages[json.dumps(language, ensure_ascii=False) if not isinstance(language,str) else language] += 1
        manifest = dict(version=1, component=name, source_pin=pin, counts=dict(counts), languages=dict(languages),
            no_admission=True, no_upload=True, audit_status='unaudited', prism_min_score=80 if name=='prism' else None,
            prior_source_coverage=prior, output_sha256=sha256(component/'candidates.jsonl'),
            exclusion_sha256=sha256(component/'exclusions.jsonl'),
            coverage_gaps=['No inherited DFM11/DFM12 exhaustive overlap scan',
                           'No benchmark prompt/text overlap scan',
                           'No tokenizer context-length or quality audit; no truncation applied'],
            heldout_policy=('Only local train files selected. Validation files absent; train/validation text overlap untested.'
                            if name.startswith('helpsteer3') else 'No evaluation split manufactured or selected.'))
        json_write(component/'manifest.json', manifest)
        sources.append(dict(name=name, path=str(component/'candidates.jsonl'), rows=counts['candidate_rows'],
            sha256=manifest['output_sha256'], manifest_path=str(component/'manifest.json'),
            manifest_sha256=sha256(component/'manifest.json')))
        print(name, json.dumps(dict(counts)), flush=True)
    for pin in pins.values():
        if sha256(Path(pin['path'])) != pin['sha256'] or sha256(Path(pin['card_path'])) != pin['card_sha256']:
            raise ValueError('Source or card changed during conversion')
    for entry in prior:
        if sha256(Path(entry['path'])) != entry['sha256']:
            raise ValueError('Prior comparison source changed during conversion')
    dependencies = [Path(__file__), ROOT/'scripts/prepare_dfm13_arena.py',
                    ROOT/'scripts/prepare_dfm13_ai_arenaen.py', ROOT/'scripts/review_dfm13_arena_candidates.py']
    manifest = dict(version='dfm13-pending-audit-candidates-v1', sources=sources,
        total=sum(s['rows'] for s in sources), no_admission=True, no_upload=True,
        source_registry_modified=False, status='cpu_conversion_complete',
        pins={str(p):sha256(p) for p in dependencies}, prior_config_sha256=sha256(prior_config),
        selection_policy='Explicit preference winners; both_good sides; human edits; PRISM chosen score>=80 inherited inspection policy, not a quality verdict.',
        deduplication='Exact complete messages plus target index/tools/template kwargs; prior four DFM13 additions then component order. Attribution ledger retained.',
        integration_blocker='Existing bulk prepare hardcodes total=205242 and source calibration manifest. Do not run it unchanged on this inventory.',
        license_hold=['prism: noncommercial output license unresolved for broadly reusable training/publication'],
        admission_blockers=['absolute_quality_audit', 'license_policy', 'heldout_overlap_coverage', 'template_context_preflight'])
    json_write(output/'manifest.json', manifest)
    json_write(output/'seal.json', dict(manifest_sha256=sha256(output/'manifest.json')))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'data/dfm13/pending-arena-candidates-20261001')
    parser.add_argument('--downloads', type=Path, default=DOWNLOADS)
    args = parser.parse_args()
    result = prepare(args.output, args.downloads)
    print(json.dumps(dict(root=str(args.output), total=result['total'])))


if __name__ == '__main__':
    main()
