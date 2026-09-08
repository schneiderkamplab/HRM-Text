"""Reviewed post-only source budgets and whole-conversation selection."""
from collections import defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np

REPEAT_ONE = {
    'dfm11-synthetic-native-tool-calling-repaired',
    'dfm8-synthetic-multiturn-danish-english-chat',
}
BEHAVIOR_FRACTIONS = {
    'nemotron_agentic': .5,
    'nemotron_instruction_reasoning_off': .5,
    'dfm11-fineinstructions-en-controlled': .5,
}
ANCHOR_WEIGHTS = {
    'flan': .5, 'flan_factual': .5, 'SYNTH': .5, 'dfm_dyna_instruct': .5,
    'nemotron_swe_repaired': .5, 'nemotron_terminal_corpus_native': .25,
}


def conversation_selection(rows, seed):
    """Half of each stratum, preserving every assistant target of a conversation."""
    groups = defaultdict(list)
    cursor = 0
    for row in rows:
        count = sum(m['role'] == 'assistant' for m in row['messages'])
        if count != row['actual_exchanges']:
            raise ValueError(f"Exchange count mismatch: {row['id']}")
        diversity = row['diversity']
        key = (diversity['topic_id'], diversity['interaction_mode'],
               row['complexity'], row['length_band'])
        order = hashlib.sha256(f"{seed}:{row['id']}".encode()).digest()
        groups[key].append((order, cursor, count))
        cursor += count
    indices = []
    selected_conversations = 0
    for group in groups.values():
        # Round up odd strata to avoid losing rare strata completely.
        chosen = sorted(group)[:math.ceil(len(group) / 2)]
        selected_conversations += len(chosen)
        for _, start, count in chosen:
            indices.extend(range(start, start + count))
    return np.asarray(sorted(indices), dtype=np.int64), cursor, selected_conversations


def prepare_koolbardi_selections(root, family, destination):
    package = root / 'exports_dfm11' / family
    manifest = json.loads((package / 'metadata/manifest.json').read_text())
    entries = sorted(manifest['data_files'], key=lambda e: e['file'])
    signature = [(e['file'], (package / e['file']).stat().st_size,
                  (package / e['file']).stat().st_mtime_ns) for e in entries]
    signature = hashlib.sha256(json.dumps(signature).encode()).hexdigest()
    completion = destination / f'{family}.complete.json'
    if completion.exists() and json.loads(completion.read_text()).get('signature') == signature:
        return
    boundaries = []
    starts = []
    def rows():
        cursor = 0
        for entry in entries:
            before = cursor
            with gzip.open(package / entry['file'], 'rt') as handle:
                for line in handle:
                    row = json.loads(line)
                    starts.append(cursor)
                    cursor += row['actual_exchanges']
                    yield row
            boundaries.append((before, cursor))
    # Stratify across the whole language, not individual shards: per-shard
    # rounding would keep most conversations in many tiny strata.
    indices, targets, conversations = conversation_selection(rows(), 'dfm11-post-quality-20260908')
    selected_starts = np.intersect1d(np.asarray(starts), indices, assume_unique=True)
    for entry, (start, end) in zip(entries, boundaries):
        task = family + '__' + entry['file'].replace('/', '__')
        selected = indices[np.searchsorted(indices, start):np.searchsorted(indices, end)] - start
        target = destination / f'{task}.npy'
        np.save(target, selected)
        receipt = dict(signature=signature, original_targets=end-start, selected_targets=len(selected),
                       selected_conversations=int(np.searchsorted(selected_starts, end) -
                                                  np.searchsorted(selected_starts, start)))
        target.with_suffix('.json').write_text(json.dumps(receipt, indent=2) + '\n')
    result = dict(signature=signature, original_targets=targets, selected_targets=len(indices),
                  selected_conversations=conversations, original_conversations=manifest['rows'])
    completion.write_text(json.dumps(result, indent=2) + '\n')
    print(f'{family}: {result}', flush=True)


def reviewed_stats(root, task, masks):
    family = task['family']
    if family not in BEHAVIOR_FRACTIONS and 'koolbardi' not in family:
        return
    path = root / 'data/tokenized_dfm11' / task['name']
    inst = np.load(path / 'inst_len.npy', mmap_mode='r')
    resp = np.load(path / 'resp_len.npy', mmap_mode='r')
    original_rows = len(inst)
    if family.startswith('dfm11-koolbardi-'):
        prepare_koolbardi_selections(root, family, masks)
        mask = masks / f"{task['name']}.npy"
        indices = np.load(mask)
        receipt = json.loads(mask.with_suffix('.json').read_text())
        if receipt['original_targets'] != original_rows:
            raise ValueError(f"Source/target mapping mismatch: {task['name']}")
        task['selection_indices_path'] = str(masks / f"{task['name']}.npy")
        inst, resp = inst[indices], resp[indices]
        task['selected_conversations'] = receipt['selected_conversations']
    if family == 'nemotron_agentic':
        task['long_context'] = 'drop'
    allowed = 4097 - np.minimum(inst, 4097)
    keep = (resp >= 2) & ((resp <= allowed) if task['long_context'] == 'drop' else (allowed >= 1))
    lengths = inst[keep] + np.minimum(resp[keep], allowed[keep])
    task['pre_review_rows'] = task['rows']
    task['rows'] = int(keep.sum())
    task['tokens'] = int(lengths.sum())
    task['mean_tokens'] = float(lengths.mean()) if len(lengths) else 0.
    task['cap'] = math.floor(min(task['cap'], task['rows']) * BEHAVIOR_FRACTIONS.get(family, 1.))
