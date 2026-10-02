"""Prepare a new pilot from unused seed windows, preserving the previous cohort."""
import argparse
from pathlib import Path
import json
import shutil
import sqlite3

from .io import file_hash, load, lock, write_json
from .multilingual_seeds import LANGUAGES
from .multilingual_tasks import spec_for

QUOTAS = {'grounded-instruct': 1900, 'summary-rewrite': 1100, 'multiturn': 1000,
          'openhermes': 500, 'math-code': 300, 'tool-dialogue': 200}


def prepare(previous, root):
    root.mkdir(parents=True, exist_ok=True)
    with lock(root / '.prepare.lock'):
        if (root / 'ready.json').exists() or (root / 'pilot.sqlite').exists():
            raise ValueError('Refusing to overwrite prepared/running pilot')
        completion = load(previous / 'completion.json')
        if completion['interrupted'] or any(c['status'] == 'pending' for c in completion['counts']):
            raise ValueError('Previous pilot must have finished')
        used = {k: set() for k in (*LANGUAGES, 'openhermes')}
        old_seeds = {language: load(previous / f'seeds-{language}.json') for language in used}
        old_config = load(previous / 'pilot-config.json') if (previous / 'pilot-config.json').exists() else {}
        with sqlite3.connect(f'file:{previous / "pilot.sqlite"}?mode=ro', uri=True) as db:
            db.execute('BEGIN')
            # Reserve even sources whose generations failed before assembly.
            # Seed selection is constant across attempts for each slot.
            for language, family, slot in db.execute('SELECT language,family,slot FROM slots'):
                spec = spec_for(language, family, slot, 0, old_seeds, old_config)
                if 'source' in spec:
                    key = 'openhermes' if family == 'openhermes' else language
                    used[key].add(spec['source']['id'])
            # Include rejected seeds as well as accepted seeds, not just successes.
            for (payload,) in db.execute("SELECT candidate FROM slots WHERE candidate IS NOT NULL UNION ALL "
                                        "SELECT json_extract(detail,'$.candidate') FROM events "
                                        "WHERE json_extract(detail,'$.candidate') IS NOT NULL"):
                row = json.loads(payload)
                spec = row.get('provenance', {})
                source = spec.get('source')
                if source:
                    key = 'openhermes' if row['family'] == 'openhermes' else row['language']
                    used[key].add(source['id'])
            hashes = [r[0] for r in db.execute('SELECT hash FROM accepted_hashes')]
        supply = {}
        for language in used:
            pool = old_seeds[language]
            pool = [s for s in pool if s['id'] not in used[language]]
            required = 3500
            if len(pool) < required:
                raise ValueError(f'Insufficient UNUSED {language} seeds: {len(pool)} < {required}')
            write_json(root / f'seeds-{language}.json', pool)
            supply[language] = len(pool)
        shutil.copy2(previous / 'training-template.json', root / 'training-template.json')
        write_json(root / 'previous-hashes.json', hashes)
        write_json(root / 'pilot-config.json', {
            'contract_version': 3, 'cohort': root.name, 'quotas': QUOTAS,
            'second_review': True, 'previous_pilot': str(previous.resolve()),
            'native_review': 'pending', 'bulk_authorized': False})
        write_json(root / 'seeds-ready.json', {p.name: file_hash(p) for p in root.glob('seeds-*.json')
                                              if p.name != 'seeds-ready.json'})
        write_json(root / 'ready.json', {'target_slots': 7 * sum(QUOTAS.values()),
            'quotas_per_language': QUOTAS, 'unused_seed_supply': supply,
            'previous_accepted_hashes': len(hashes), 'resume_training_after': True,
            'bulk_authorized': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.previous, args.root)
