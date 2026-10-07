"""Add the Tatoeba pes English bridge without rewriting the v2 evidence."""
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sqlite3

from dfm12.baltic_opus import prepare_one
from dfm12.io import load, lock, rows, write_json
from dfm14.parallel import discover_one
from dfm14.parallel_expand import eligible, pivot, texts
from dfm14.parallel_report import run as report


def run():
    original = Path('data/dfm14/parallel-v1').resolve()
    previous = Path('data/dfm14/parallel-expansion-v2').resolve()
    root = Path('data/dfm14/parallel-expansion-v3').resolve()
    with lock(root / '.controller.lock'):
        cfg = load(previous / 'config.json')
        cfg.setdefault('opus_codes', {})['fa'] = 'pes'
        write_json(root / 'config.json', cfg)
        _, item = discover_one(root, cfg, ['en', 'fa'])
        write_json(root / 'opus/inventory.json', {'pairs': {'en-fa': item}})
        state = prepare_one((root, 'en-fa', item, cfg))
        if state['state'] != 'bridge_only':
            raise RuntimeError(state)
        # Reuse immutable prior outputs; only Persian pivots need recomputation.
        for kind in ('candidates', 'pivots'):
            (root / kind).mkdir(exist_ok=True)
            for source in (previous / kind).iterdir():
                if kind == 'pivots' and 'fa' in source.name.split('-'):
                    continue
                target = root / kind / source.name
                if not target.exists():
                    target.symlink_to(source, target_is_directory=True)
        if not (root / 'legs-ready.json').exists():
            with sqlite3.connect(f'file:{previous / "legs.sqlite"}?mode=ro', uri=True) as src:
                with sqlite3.connect(root / 'legs.sqlite') as dst:
                    src.backup(dst)
                    count = 0
                    path = root / 'candidates/opus-en-fa/candidates.jsonl'
                    for row in rows(path):
                        values = texts(row)
                        if not eligible(values['en']):
                            continue
                        evidence = json.dumps(dict(id=row['id'], provenance=row['provenance'], input=str(path)))
                        dst.execute('''INSERT INTO legs(language,anchor,text,evidence) VALUES(?,?,?,?)
                            ON CONFLICT(language,anchor) DO UPDATE SET
                            ambiguous=MAX(legs.ambiguous,legs.text != excluded.text)''',
                            ('fa', values['en'], values['fa'], evidence))
                        count += 1
                    dst.commit()
            write_json(root / 'legs-ready.json', dict(new_input_legs=count, predecessor=str(previous)))
        pairs = ['-'.join(p) for p in cfg['requested_pairs'] if 'fa' in p]
        with ProcessPoolExecutor(max_workers=16) as pool:
            receipts = list(pool.map(pivot, [(root, original, p, cfg) for p in pairs]))
        write_json(root / 'persian-bridge.json', dict(bridge=state, pivots=receipts, training_ready=False))
        report(original=original, expanded=root)


if __name__ == '__main__':
    run()
