"""Read-only NL/FA baseline accepted-decision versus admitted recovery overlap."""
from collections import Counter
import gzip
import json
from pathlib import Path
from dfm12 import dala_compact_finalize as f


def run():
    root = Path('data/dfm13/dala-baseline-recovery-reconciliation-20261004-v1')
    recovery = Path('data/dfm13/dala-v2-compact-finalized-20261004-v1/groups')
    config = f.load(f.AUDITS[1]/'config.json')
    if f.file_hash(config['manifest']) != config['manifest_sha256']:
        raise ValueError('Audit manifest drift')
    sources = f.sources_from(f.load(config['manifest']))
    for language in ('nl', 'fa'):
        seen = set(); pins = []
        for path in sorted((recovery/(language+'-recovery')/'train/acceptability').glob('*.gz')):
            pins.append(f.pin(path))
            with gzip.open(path, 'rt') as stream:
                for line in stream:
                    row = json.loads(line)
                    provenance = row['provenance']
                    kind = 'clean_control' if row['variant'] == 'clean' else 'pair'
                    value = provenance['original'] if kind == 'clean_control' else provenance['corrupted']
                    seen.add((kind, f.text_key(value)))
        counts = Counter()
        with f.readonly(f.AUDITS[1]/'jobs.sqlite') as db:
            for source in sources:
                if source['language'] != language:
                    continue
                query = 'SELECT j.record,j.status,j.result FROM aliases a JOIN jobs j ON j.id=a.id WHERE a.component=?'
                for record, status, result in db.execute(query, (source['component'],)):
                    record = json.loads(record)
                    counts['baseline_aliases'] += 1
                    if not f.accepted(record, json.loads(result) if result else None, status):
                        counts['not_accepted'] += 1
                        continue
                    kind = record['kind']
                    value = record['original'] if kind == 'clean_control' else record['corrupted']
                    counts['accepted_overlapping_recovery' if (kind, f.text_key(value)) in seen
                           else 'accepted_requires_remaining_source_and_split_gates'] += 1
        f.write_json(root/(language+'.json'), dict(language=language, counts=dict(counts),
            recovery_pins=pins, audit_config=f.pin(f.AUDITS[1]/'config.json'),
            admission_performed=False, remaining_source_split_checks_required=True))
        print(language, dict(counts), flush=True)


if __name__ == '__main__':
    run()
