#!/usr/bin/env python3
"""Read-only structural inventory of Search Arena and RepoChat context."""
from collections import Counter, defaultdict
import json
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path('data/downloads/arena_review')
OUT = Path('logs/arena_review/20261001')


def main():
    counts = Counter()
    roles = Counter()
    configs = Counter()
    models = defaultdict(Counter)
    unusual = []
    for batch in pq.ParquetFile(ROOT / 'search-arena-24k/data/search-arena-chat-24k.parquet').iter_batches(batch_size=64):
        for r in batch.to_pylist():
            counts['rows'] += 1
            for side in 'ab':
                md = r['system_' + side + '_metadata']
                trace = md.get('llm_trace') or []
                web = md.get('web_search_trace') or []
                entries = [item for turn in web for item in turn]
                record = models[r['model_' + side]]
                record['sides'] += 1
                preferred = r['winner'] == 'model_' + side
                record['preferred_sides'] += preferred
                record['with_url_entries'] += bool(entries)
                config = md.get('web_search_config') or {}
                configs[json.dumps(config, sort_keys=True)] += 1
                for m in trace:
                    roles[m['role']] += 1
                has_tool = any(m['role'] in ('tool', 'function') for m in trace)
                counts['sides_with_tool_role'] += has_tool
                counts['sides_with_structured_tool_call'] += any(m.get('tool_calls') or m.get('function_call') for m in trace)
                counts['sides_with_tool_definitions'] += bool(md.get('tools'))
                counts['preferred_sides'] += preferred
                counts['preferred_sides_with_url_entries'] += preferred and bool(entries)
                for entry in entries:
                    counts['web_entries'] += 1
                    counts['web_entries_label_url_only'] += len(entry) == 2 and entry[1].startswith(('http:', 'https:'))
                    if len(entry) != 2 or not entry[1].startswith(('http:', 'https:')):
                        if len(unusual) < 8:
                            unusual.append({'conv_id': md['conv_id'], 'entry': entry})
                # Metadata/schema inventory only; prose mentioning a tool is not an observed call.
    report = {'search': {'counts': counts, 'llm_trace_roles': roles, 'configs': configs,
                         'models': models, 'unusual_web_entries': unusual}}
    rows = json.loads((ROOT / 'repochat-arena-preference-4k/repochat_battles.json').read_text())
    counts = Counter()
    keys = Counter()
    roles = Counter()
    lengths = []
    for r in rows:
        counts['rows'] += 1
        keys.update(r.keys())
        side = r['winner'][-1] if r['winner'] in ('model_a', 'model_b') else None
        if side is None:
            continue
        counts['preferred_rows'] += 1
        messages = r['full_conversation_' + side]
        roles.update(m['role'] for m in messages)
        user = '\n'.join(m['content'] for m in messages if m['role'] == 'user')
        counts['with_embedded_file_marker'] += '<summary>File:' in user
        counts['with_github_link'] += bool(r.get('github_link'))
        counts['with_structured_tool_call'] += any(m.get('tool_calls') or m.get('function_call') for m in messages)
        counts['with_tool_role'] += any(m['role'] in ('tool', 'function') for m in messages)
        counts['with_redaction_in_context'] += '[Redacted' in user
        lengths.append(sum(len(m['content']) for m in messages))
    lengths.sort()
    report['repochat'] = {'counts': counts, 'keys': dict(keys), 'roles': roles,
                          'preferred_conversation_chars': {str(q): lengths[int((len(lengths)-1)*q)] for q in (0, .5, .9, .99, 1)}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'tool_context_inventory.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
