"""Finalize NL/FA baseline pools, excluding admitted recovery inputs."""
import gzip
import json
from pathlib import Path
from types import FunctionType
from dfm12 import dala_compact_finalize as f


def run():
    root = Path('data/dfm13/dala-baseline-delta-finalized-20261004-v1')
    recovery = Path('data/dfm13/dala-v2-compact-finalized-20261004-v1/groups')
    with f.lock(root/'.lock'):
        config = f.load(f.AUDITS[1]/'config.json')
        if f.file_hash(config['manifest']) != config['manifest_sha256']:
            raise ValueError('Audit manifest drift')
        sources = f.sources_from(f.load(config['manifest']))
        universe = f.load(f.ALL_INPUTS)['sources']
        entries = []
        for language in ('nl', 'fa'):
            target = root/'groups'/(language+'-baseline')
            group = [s for s in sources if s['language'] == language]
            if f.snapshot(f.AUDITS[1], group, target) is None:
                raise ValueError('Baseline not terminal')
            pins = []
            def heldout(inputs, path):
                db, count = f.build_heldout(inputs, path)
                for file in sorted((recovery/(language+'-recovery')/'train/acceptability').glob('*.gz')):
                    pins.append(f.pin(file))
                    with gzip.open(file, 'rt') as stream:
                        for line in stream:
                            row = json.loads(line); source = row['provenance']
                            kind = 'clean_control' if row['variant'] == 'clean' else 'pair'
                            text = source['original'] if kind == 'clean_control' else source['corrupted']
                            db.execute('INSERT OR IGNORE INTO seen VALUES(?,?)', (kind, f.text_key(text)))
                db.commit()
                return db, count
            finalize = FunctionType(f.finalize.__code__, dict(f.finalize.__globals__, build_heldout=heldout))
            result = finalize((target, universe, True))
            export = f.load(target/'export.json')
            export['recovery_training_exclusion_pins'] = pins
            export['additional_exclusion_implementation'] = f.pin(__file__)
            f.write_json(target/'export.json', export)
            result['export'] = f.pin(target/'export.json')
            for entry in result['components']:
                entry['export_receipt'] = result['export']
            f.write_json(target/'integration.json', result)
            entries.extend(result['components'])
            f.write_json(root/'registry.json', dict(inherits='dfm12', additions=entries))
            print('FINALIZED', language, flush=True)
        f.write_json(root/'complete.json', dict(success=True, registry=f.pin(root/'registry.json'), waiting=[]))


if __name__ == '__main__':
    run()
