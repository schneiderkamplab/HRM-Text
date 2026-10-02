#!/usr/bin/env python3
"""Deterministically sample candidate sources for manual review, not training."""
import ast
from collections import Counter
import gzip
import hashlib
import io
import json
from pathlib import Path
import tokenize

import pyarrow.parquet as pq

ROOT = Path('data/downloads/arena_review')
OUT = Path('logs/arena_review/20261001')


def parse_numpy_repr(text):
    # NumPy object-array repr omits commas between adjacent dictionaries.
    tokens = []
    previous = None
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
            continue
        if previous == '}' and tok.string == '{':
            tokens.append((tokenize.OP, ','))
        tokens.append((tok.type, tok.string))
        if tok.type != tokenize.ENDMARKER:
            previous = tok.string
    tree = ast.parse(tokenize.untokenize(tokens), mode='eval')

    def decode(node):
        if isinstance(node, ast.Constant) and node.value is not Ellipsis:
            return node.value
        if isinstance(node, (ast.List, ast.Tuple)):
            return [decode(v) for v in node.elts]
        if isinstance(node, ast.Dict):
            return {decode(k): decode(v) for k, v in zip(node.keys, node.values)}
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -decode(node.operand)
        if isinstance(node, ast.Name) and node.id == 'nan':
            return None
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'array' and len(node.args) == 1
                and all(k.arg == 'dtype' and isinstance(k.value, ast.Name)
                        and k.value.id == 'object' for k in node.keywords)):
            return decode(node.args[0])
        raise ValueError('Unsupported or truncated representation: ' + ast.dump(node)[:100])
    return decode(tree.body)


def messages(raw):
    result = []
    for m in raw:
        content = m['content']
        if isinstance(content, list):
            if any(x.get('type') != 'text' for x in content):
                raise ValueError('Nontext message')
            content = ''.join(x['text'] for x in content)
        result.append({'role': m['role'], 'content': content})
    return result


def load_jsonl(path):
    with (gzip.open(path, 'rt') if path.suffix == '.gz' else path.open()) as handle:
        for i, line in enumerate(handle):
            yield i, json.loads(line)


def candidates():
    for i, r in load_jsonl(ROOT / 'comparia-fr-arena/comparia-fr-arena_samples.jsonl'):
        sides = {'a_better': ['a'], 'b_better': ['b'], 'both_good': ['a', 'b']}.get(r['choice'], [])
        for side in sides:
            pair = messages(r['response_' + side])
            full = messages(r['full_conversation_' + side])
            loc = [j for j in range(len(full)-1) if full[j:j+2] == pair]
            if len(loc) != 1:
                continue
            yield {'source': 'comparia', 'id': r['response_id'] + ':' + side,
                   'vote': r['choice'], 'messages': full[:loc[0]+2]}
    for i, r in load_jsonl(ROOT / 'HelpSteer3/preference/train.jsonl.gz'):
        score = r['overall_preference']
        if score == 0:
            continue
        answer = r['response1' if score < 0 else 'response2']
        yield {'source': 'helpsteer3_preference', 'id': str(i), 'vote': score,
               'domain': r['domain'], 'language': r['language'],
               'messages': r['context'] + [{'role': 'assistant', 'content': answer}],
               'feedback': r['individual_preference']}
    for i, r in load_jsonl(ROOT / 'HelpSteer3/edit/train.jsonl.gz'):
        yield {'source': 'helpsteer3_edit', 'id': str(i), 'vote': 'human_edit',
               'messages': r['context'] + [{'role': 'assistant', 'content': r['edited_response']}],
               'change_summary': r['change_summary']}
    for batch in pq.ParquetFile(ROOT / 'arena-expert-5k/data/train-00000-of-00001.parquet').iter_batches(batch_size=64):
        for r in batch.to_pylist():
            if r['winner'] not in ('model_a', 'model_b'):
                continue
            side = r['winner'][-1]
            # Parse only sampled records later: expensive reprs may be very long.
            yield {'source': 'expert5k', 'id': r['id'], 'vote': r['winner'],
                   'language': r['language'], 'raw_conversation': r['conversation_' + side],
                   'raw_history': r['full_conversation'], 'side': side}
    for i, r in load_jsonl(ROOT / 'prism-alignment/conversations.jsonl'):
        history = []
        for m in r['conversation_history']:
            if m['role'] == 'user':
                history.append({'role': 'user', 'content': m['content']})
            elif m.get('if_chosen'):
                history.append({'role': 'assistant', 'content': m['content']})
                if m.get('score', 0) >= 80:
                    yield {'source': 'prism', 'id': f"{r['conversation_id']}:{m['turn']}:{m['within_turn_id']}",
                           'vote': m['score'], 'messages': list(history),
                           'conversation_type': r['conversation_type']}


def main():
    selected, counts = {}, Counter()
    for row in candidates():
        source = row['source']
        counts[source] += 1
        rank = hashlib.sha256(('20261001:' + source + ':' + row['id']).encode()).hexdigest()
        selected.setdefault(source, []).append((rank, row))
        selected[source] = sorted(selected[source], key=lambda x: x[0])[:3]
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / 'quality_samples.jsonl').open('w') as handle:
        for source, items in selected.items():
            for rank, row in items:
                if source == 'expert5k':
                    current = messages(parse_numpy_repr(row.pop('raw_conversation')))
                    raw_history = parse_numpy_repr(row.pop('raw_history'))
                    full = []
                    for turn in raw_history:
                        full.extend(messages([turn['user'], turn['model_' + row['side']]]))
                    loc = [j for j in range(0, len(full)-len(current)+1, 2) if full[j:j+len(current)] == current]
                    if len(loc) != 1:
                        raise ValueError('Expert history ambiguous')
                    row['messages'] = full[:loc[0]+len(current)]
                row['sampling_rank'] = rank
                handle.write(json.dumps(row, ensure_ascii=False) + '\n')
    (OUT / 'sampling.json').write_text(json.dumps({'seed': '20261001', 'eligible': counts,
        'per_source': 3, 'comparia_scope': 'upstream sample file, not full 675K',
        'prism_policy': 'chosen and score >=80; includes only chosen previous assistant context'}, indent=2))
    print(dict(counts))


if __name__ == '__main__':
    main()
