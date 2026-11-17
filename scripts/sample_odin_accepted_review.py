"""Reproducible stratified prose review; no new API calls or acceptance changes."""
from collections import defaultdict
import json
import random

from dfm12.io import atomic
from scripts.queue_dfm16_stories_qwen import DEFAULT, audited_records


def main():
    by_unit = {}
    for source, result in audited_records(DEFAULT/'odin-text-units/probe'):
        key = (source['parent_id'], source['turn_index'])
        item = by_unit.setdefault(key, dict(source=source, decisions={}))
        item['decisions'][source['aspect']] = result['review']['decision']
    groups = defaultdict(list)
    for item in by_unit.values():
        if set(item['decisions'].values()) == {'accept'}:
            source = item['source']
            groups[(source['language'], source['task'])].append(source)
    rng = random.Random(20261028)
    selected = []
    for group, candidates in sorted(groups.items()):
        # Pick a parent first to avoid overweighting multi-version conversations.
        parents = defaultdict(list)
        for source in candidates:
            parents[source['parent_id']].append(source)
        parent = rng.choice(sorted(parents))
        source = rng.choice(sorted(parents[parent], key=lambda r: r['turn_index']))
        selected.append(dict(label='/'.join(group), parent_id=parent,
            turn_index=source['turn_index'], cohort=source['comparison_cohort'],
            text=source['text'], language_decision='accept', coherence_decision='accept'))
    path = DEFAULT/'odin-accepted-manual-sample.jsonl'
    with atomic(path) as handle:
        handle.write(''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in selected))
    print(path)


if __name__ == '__main__':
    main()
