#!/usr/bin/env python3
"""Prepare vote-selected AI-Arenaen SFT examples; never supervise unselected turns."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile

SELECTION = {'a_better': ['a'], 'b_better': ['b'], 'both_good': ['a', 'b']}


def clean(messages):
    result = []
    for message in messages:
        role, content = message.get('role'), message.get('content')
        if role not in ('user', 'assistant') or not isinstance(content, str) or not content.strip():
            raise ValueError('Non-text, empty or unsupported message')
        result.append({'role': role, 'content': content})
    return result


def selected_examples(row, revision):
    examples = []
    for side in SELECTION.get(row.get('choice'), []):
        pair = clean(row['response_' + side])
        history = clean(row['full_conversation_' + side])
        if len(pair) != 2 or [m['role'] for m in pair] != ['user', 'assistant']:
            raise ValueError('Expected a user/assistant response pair')
        position = 2 * row['turn']
        if history[position:position+2] != pair:
            matches = [i for i in range(len(history)-1) if history[i:i+2] == pair]
            if len(matches) != 1:
                raise ValueError('Cannot uniquely locate selected turn in full history')
            position = matches[0]
        messages, repaired = [], 0
        for message in history[:position+2]:
            if messages and message['role'] == messages[-1]['role']:
                if message['role'] != 'user' or message['content'] != messages[-1]['content']:
                    raise ValueError('Unsupported consecutive roles; refusing silent reconstruction')
                repaired += 1
                continue
            messages.append(message)
        if messages[0]['role'] != 'user' or messages[-1] != pair[-1]:
            raise ValueError('Invalid conversation boundary')
        examples.append({
            'id': str(row['response_id']) + ':' + side,
            'messages': messages,
            'target_message_index': len(messages)-1,
            'chat_template_kwargs': {'enable_thinking': False},
            'metadata': {'source': 'danish-foundation-models/ai-arenaen', 'revision': revision,
                'response_id': row['response_id'], 'comparison_id': row['comparison_id'],
                'turn': row['turn'], 'choice': row['choice'], 'selected_side': side,
                'model': row['model_' + side], 'duplicate_user_messages_removed': repaired,
                'license': 'cc-by-4.0'}})
    return examples


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=Path('config/dfm13_sources.json'))
    p.add_argument('--download-dir', type=Path, default=Path('data/downloads/datasets/ai_arenaen'))
    args = p.parse_args()
    spec = next(s for s in json.loads(args.config.read_text())['additions'] if s['name']=='ai_arenaen_preferred')
    if spec['selection'] != SELECTION:
        raise ValueError('Selection policy differs from implemented rules')
    from huggingface_hub import hf_hub_download
    import pyarrow.parquet as pq
    source = Path(hf_hub_download(spec['repo_id'], spec['file'], repo_type='dataset',
                  revision=spec['revision'], local_dir=args.download_dir))
    output = Path(spec['output'])
    output.parent.mkdir(parents=True, exist_ok=True)
    counts, choices, seen = Counter(), Counter(), set()
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent, delete=False) as f:
            temp = Path(f.name)
            for batch in pq.ParquetFile(source).iter_batches(batch_size=256):
                for row in batch.to_pylist():
                    choices[str(row['choice'])] += 1
                    examples = selected_examples(row, spec['revision'])
                    counts['source_rows'] += 1
                    counts['excluded_rows' if not examples else 'selected_rows'] += 1
                    for example in examples:
                        if example['id'] in seen:
                            raise ValueError('Duplicate response/side ID')
                        seen.add(example['id'])
                        counts['training_examples'] += 1
                        counts['by_choice_' + row['choice']] += 1
                        counts['history_repairs'] += example['metadata']['duplicate_user_messages_removed']
                        counts['multiturn_examples'] += int(len(example['messages']) > 2)
                        f.write(json.dumps(example, ensure_ascii=False)+'\n')
        temp.replace(output)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()
    report = dict(spec, counts=dict(counts), source_choices=dict(choices),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        reasoning_policy='Use visible content only; do not inject reasoning_content',
        warning='Human preference is relative, not a factual-correctness certificate. Prior nonselected answers are context only.')
    output.with_suffix('.manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report['counts'], indent=2))
    print(output)


if __name__ == '__main__':
    main()
