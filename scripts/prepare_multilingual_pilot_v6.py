"""Prepare the authorized 35K pilot using the retained native-schema contract."""
import argparse
from collections import Counter
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dfm12.io import load, write_json, file_hash
from dfm12 import multilingual_calibration_v6 as v6
from dfm12.multilingual_tasks import spec_for
from dfm12.multilingual_prepare_next import QUOTAS
from dfm12.multilingual_prepare_calibrated import unused_snapshot
from dfm12.multilingual_seeds import LANGUAGES


def prepare(root, donor):
    root.mkdir(parents=True, exist_ok=False)
    snapshot = unused_snapshot(donor)
    paths = [donor/f'seeds-{lang}.json' for lang in (*LANGUAGES, 'openhermes')]
    paths += [donor/'previous-hashes.json', donor/'training-template.json']
    pins = {str(p.resolve()): file_hash(p) for p in paths}
    for name, expected in load(donor/'seeds-ready.json').items():
        if file_hash(donor/name) != expected:
            raise ValueError('Donor pin drift: '+name)
    seeds = {lang: load(donor/f'seeds-{lang}.json') for lang in (*LANGUAGES, 'openhermes')}
    cursors = Counter()
    config = dict(contract_version=4, cohort=root.name, quotas=QUOTAS)
    _, generation = v6.adapters()
    budget = v6.Budget(v6.TOKENIZER_DIR)
    specs, excluded, coverage = [], [], Counter()
    for slot in range(max(QUOTAS.values())):
        for lang in LANGUAGES:
            for family, count in QUOTAS.items():
                if slot >= count:
                    continue
                spec = spec_for(lang, family, slot, 0, seeds, config)
                while True:
                    if 'source' in spec:
                        key = 'openhermes' if family == 'openhermes' else lang
                        pos = cursors[key]
                        if pos >= len(seeds[key]):
                            raise ValueError(f'Exhausted {key} at {len(specs)} specs')
                        spec['source'] = seeds[key][pos]
                        cursors[key] += 1
                    try:
                        payload = v6.generation_request(spec, generation)
                        budget.measure(payload)
                    except ValueError as exc:
                        if 'source' not in spec:
                            raise
                        excluded.append(dict(language=lang, family=family, slot=slot,
                            source_id=spec['source']['id'], error=str(exc)))
                        continue
                    break
                specs.append(spec)
                coverage[f'{lang}/{family}'] += 1
        if slot % 100 == 0:
            print(f'slot={slot} prepared={len(specs)} excluded_sources={len(excluded)}', flush=True)
    assert len(specs) == 35000
    for lang in LANGUAGES:
        for family, count in QUOTAS.items():
            assert coverage[f'{lang}/{family}'] == count
    if any(file_hash(Path(p)) != h for p,h in pins.items()):
        raise ValueError('Donor changed during preparation')
    write_json(root/'specifications.json', specs)
    shutil.copy2(donor/'previous-hashes.json', root/'previous-hashes.json')
    write_json(root/'selection.json', dict(donor=str(donor.resolve()), donor_snapshot=snapshot,
        quotas_per_language=QUOTAS, coverage=dict(coverage), consumed_sources=dict(cursors),
        exclusions=excluded, exclusion_count=len(excluded), no_truncation=True,
        calibration_passed=False, user_authorized_35000_pilot=True,
        source_note='Unused failed cohort reservoir; diagnostic exposures are not held out.'))
    write_json(root/'preparation.json', dict(tokenizer_dir=str(Path(v6.TOKENIZER_DIR).resolve()),
        external_pins=pins, target_slots=35000, admission_authorized=False))
    print('Prepared all 35000 slots; runner manifest must be sealed before launch.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--donor', type=Path, default=Path('data/dfm12/multilingual-pilot-20260926-v3'))
    args = parser.parse_args()
    prepare(args.root, args.donor)
