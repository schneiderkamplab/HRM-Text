"""Summarize pilot results and select five accepted conversations per cell."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
from dfm12.io import atomic, load, rows, file_hash, write_json


def report(root):
    root = Path(root)
    if load(root/'audit/pipeline/state.json')['phase'] != 'complete':
        raise ValueError('Pilot is not complete')
    rng = random.Random(20261029)
    counts, accepted, sample = defaultdict(Counter), Counter(), defaultdict(list)
    for chunk in load(root/'manifest.json')['chunks']:
        inputs = {r['audit_id']: r for r in rows(root/chunk['input'])}
        folder = root/'audit'/chunk['job_id']
        receipt = load(folder/'receipt.json')
        if receipt['input_sha256'] != chunk['sha256'] or receipt['results_sha256'] != file_hash(folder/'results.jsonl'):
            raise ValueError('Pilot receipt mismatch')
        seen = set()
        for row in rows(folder/'results.jsonl'):
            key = row['audit_id']
            if key not in inputs or key in seen:
                raise ValueError('Invalid result ID')
            seen.add(key)
            source = inputs[key]
            group = f'{source["language"]}/{source["task"]}'
            verdict = row.get('review', {}).get('decision', 'unresolved')
            counts[group][verdict] += 1
            if verdict == 'accept':
                accepted[group] += 1
                record = dict(candidate=row['candidate'], specification=source['specification'])
                if len(sample[group]) < 5:
                    sample[group].append(record)
                else:
                    position = rng.randrange(accepted[group])
                    if position < 5:
                        sample[group][position] = record
        if seen != set(inputs):
            raise ValueError('Incomplete pilot')
    with atomic(root/'manual-review-100.jsonl') as f, atomic(root/'manual-review-100.md') as md:
        md.write('# Pilot manual review: pending\n\nProduction remains blocked until these are reviewed.\n')
        for group in sorted(sample):
            for i, record in enumerate(sample[group], 1):
                f.write(json.dumps(record, ensure_ascii=False)+'\n')
                md.write(f'\n## {group} sample {i}\n\n')
                md.write('Specification: '+json.dumps(record['specification'], ensure_ascii=False)+'\n\n')
                for m in record['candidate']['messages']:
                    md.write('**'+m['role']+'**\n\n'+m['content']+'\n\n')
    write_json(root/'quality-summary.json', dict(groups={k: dict(v) for k,v in counts.items()},
        selected=sum(map(len, sample.values())), manual_review_complete=False, production_authorized=False))


if __name__ == '__main__':
    report('data/dfm16/expansion-v1/stories/quality-v2/pilot')
