#!/usr/bin/env python3
"""Convert the three pinned Arena releases into deduplicated selected-target SFT."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile


def message(raw):
    if not isinstance(raw, dict) or raw.get('role') not in ('user', 'assistant', 'system'):
        raise ValueError('unsupported_message')
    content = raw.get('content')
    if isinstance(content, list):
        if not all(isinstance(x, dict) and x.get('type') == 'text'
                   and isinstance(x.get('text'), str) and not x.get('image') for x in content):
            raise ValueError('non_text_content')
        content = ''.join(x['text'] for x in content)
    if not isinstance(content, str) or not content.strip():
        raise ValueError('empty_or_nonstring_content')
    return {'role': raw['role'], 'content': content}


def winner(row):
    if 'winner' in row:
        value = row['winner']
        if value in ('model_a', 'model_b'):
            return value[-1], value
        if value in ('tie', 'both_bad', 'tie (bothbad)'):
            return None, value
        raise ValueError('unknown_vote')
    flags = [int(row[k]) for k in ('winner_model_a', 'winner_model_b', 'winner_tie')]
    if any(x not in (0, 1) for x in flags) or sum(flags) != 1:
        raise ValueError('invalid_vote_flags')
    side = ('a', 'b', None)[flags.index(1)]
    return side, 'model_' + side if side else 'tie_or_both_bad'


def conversation(row, side):
    if 'prompt' in row:
        prompts = json.loads(row['prompt'])
        answers = json.loads(row['response_' + side])
        if not isinstance(prompts, list) or not isinstance(answers, list) or len(prompts) != len(answers):
            raise ValueError('unaligned_turn_lists')
        messages = [message({'role': role, 'content': content})
                    for p, a in zip(prompts, answers)
                    for role, content in (('user', p), ('assistant', a))]
    else:
        messages = [message(m) for m in row['conversation_' + side]]
    if row.get('full_conversation'):
        # Match the current evaluation's complete block, not evaluation_order:
        # an evaluation can contain multiple conversation turns.
        full = []
        for turn in row['full_conversation']:
            full.extend((message(turn['user']), message(turn['model_side_' + side])))
        starts = [i for i in range(0, len(full) - len(messages) + 1, 2)
                  if full[i:i + len(messages)] == messages]
        if len(starts) != 1:
            raise ValueError('ambiguous_or_missing_history_match')
        messages = full[:starts[0] + len(messages)]
    if not messages or messages[-1]['role'] != 'assistant':
        raise ValueError('missing_final_assistant')
    dialogue = messages[1:] if messages[0]['role'] == 'system' else messages
    if len(dialogue) % 2 or any(m['role'] != ('user' if i % 2 == 0 else 'assistant')
                               for i, m in enumerate(dialogue)):
        raise ValueError('nonalternating_roles')
    return messages


def fingerprint(messages):
    return hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def rows(path):
    if path.suffix == '.csv':
        csv.field_size_limit(sys.maxsize)
        with path.open() as handle:
            yield from csv.DictReader(handle)
    else:
        import pyarrow.parquet as pq
        for batch in pq.ParquetFile(path).iter_batches(batch_size=128):
            yield from batch.to_pylist()


def sha256(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=Path('config/dfm13_sources.json'))
    args = p.parse_args()
    from huggingface_hub import snapshot_download
    specs = json.loads(args.config.read_text())['additions']
    seen = set()
    for spec in specs:
        if spec['name'] == 'ai_arenaen_preferred':
            with Path(spec['output']).open() as handle:
                seen.update(fingerprint(json.loads(line)['messages']) for line in handle)
    for spec in specs:
        if spec['converter'] != 'scripts/prepare_dfm13_arena.py':
            continue
        source = Path(snapshot_download(spec['repo_id'], repo_type='dataset', revision=spec['revision'],
                      allow_patterns=['README.md', '*.parquet', '*.csv'],
                      local_dir=Path('data/downloads/datasets') / spec['name'], max_workers=4))
        files = sorted(source.rglob('*.parquet')) + sorted(source.glob('*.csv'))
        if not files:
            raise ValueError('No source files')
        output = Path(spec['output'])
        output.parent.mkdir(parents=True, exist_ok=True)
        counts, votes, languages = Counter(), Counter(), Counter()
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent, delete=False) as out, \
                 (output.parent / 'rejected.jsonl').open('w') as rejected:
                temporary = Path(out.name)
                for path in files:
                    for row in rows(path):
                        counts['source_rows'] += 1
                        row_id = str(row.get('id', row.get('question_id')))
                        try:
                            side, vote = winner(row)
                            votes[vote] += 1
                            if side is None:
                                counts['excluded_vote'] += 1
                                continue
                            counts['winner_rows'] += 1
                            messages = conversation(row, side)
                        except (ValueError, KeyError, TypeError) as error:
                            counts['invalid_rows'] += 1
                            rejected.write(json.dumps({'id': row_id, 'reason': str(error)}) + '\n')
                            continue
                        digest = fingerprint(messages)
                        if digest in seen:
                            counts['exact_duplicates'] += 1
                            continue
                        seen.add(digest)
                        language = row.get('language') or 'unspecified'
                        result = {'id': spec['name'] + ':' + row_id + ':' + side,
                                  'messages': messages, 'target_message_index': len(messages) - 1,
                                  'chat_template_kwargs': {'enable_thinking': False},
                                  'metadata': {'source': spec['repo_id'], 'revision': spec['revision'],
                                      'source_id': row_id, 'selected_side': side, 'winner': vote,
                                      'model': row['model_' + side], 'language': language,
                                      'license': spec['license'], 'content_sha256': digest}}
                        out.write(json.dumps(result, ensure_ascii=False) + '\n')
                        counts['training_examples'] += 1
                        counts['multiturn_examples'] += int(len(messages) > 2)
                        languages[language] += 1
            temporary.replace(output)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
        manifest = dict(spec, counts=dict(counts), votes=dict(votes), languages=dict(languages),
                        source_files={str(f.relative_to(source)): sha256(f) for f in files},
                        output_sha256=sha256(output), output_bytes=output.stat().st_size,
                        deduplication='Exact normalized complete messages; Danish source then 140k, 100k, 55k',
                        supervision='Final winning assistant only; earlier turns context, ties excluded')
        output.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        print(spec['name'], json.dumps(dict(counts)), flush=True)


if __name__ == '__main__':
    main()
