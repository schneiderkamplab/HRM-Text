"""CPU-only, exposure-excluded, all-group 31B calibration preparation."""
import argparse
from collections import Counter
from contextlib import closing
from pathlib import Path
import sqlite3
import json

from . import wave31_production as production
from .io import digest, file_hash, load, rows, write_json
from .wave4_gemma31_download import MODEL, ROOT as DOWNLOAD

ROOT = Path('data/dfm13/gemma31-balanced-calibration-20261003-v2')
FAMILIES = tuple(production.FAMILY_TARGETS)


def identity(spec):
    """Ignore allocation labels; source text/reference/scenario determine novelty."""
    source = spec.get('source')
    if source:
        return digest(['source', source.get('text'), source.get('messages')])
    for key in ('reference', 'scenario'):
        if key in spec:
            return digest([key, spec[key]])
    return digest({k: v for k, v in spec.items()
                   if k not in ('cohort', 'slot', 'variant', 'contract_version')})


def exposure_snapshot(base):
    """Read specifications only, never historical reviewer decisions."""
    specs, inventory = [], []
    for directory in sorted(base.iterdir()):
        if not directory.is_dir():
            continue
        for name, table, column in [('spec-selections.sqlite', 'selections', 'spec'),
                                     ('jobs.sqlite', 'jobs', 'spec_json')]:
            path = directory / name
            if not path.exists():
                continue
            with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)) as db:
                columns = {r[1] for r in db.execute(f'PRAGMA table_info({table})')}
                if column not in columns:
                    continue
                values = [json.loads(r[0]) for r in db.execute(
                    f'SELECT {column} FROM {table} WHERE {column} IS NOT NULL')]
            specs.extend(values)
            inventory.append(dict(path=str(path.resolve()), specs=len(values), snapshot_sha256=digest(values)))
        for name in ('specifications.json', 'generation-requests.jsonl'):
            path = directory / name
            if not path.exists():
                continue
            values = load(path) if name.endswith('.json') else [r['spec'] for r in rows(path)]
            specs.extend(values)
            inventory.append(dict(path=str(path.resolve()), specs=len(values), sha256=file_hash(path)))
    return specs, inventory


def check_groups(specs, languages, per_group):
    counts = Counter((s['language_code'], s['family']) for s in specs)
    expected = {(l, f): per_group for l in languages for f in FAMILIES}
    if counts != expected:
        raise ValueError('Incomplete or unbalanced language/family coverage')
    return {f'{l}/{f}': n for (l, f), n in sorted(counts.items())}


def prepare(root, per_group=3):
    if type(per_group) is not int or per_group < 3:
        raise ValueError('At least three examples per group required')
    root = Path(root).resolve()
    if root.exists():
        raise ValueError('Fresh immutable root required')
    ready = load(DOWNLOAD/'ready.json')
    if ready['model'] != MODEL or ready.get('all_files_verified') is not True:
        raise ValueError('Pinned 31B snapshot required')
    root.mkdir(parents=True)
    all_specs, pins, groups = [], {}, {}
    exposed_roots = [Path('data/dfm13/wave4/gemma31-fresh-comparison30-v3'),
                     Path('data/dfm13/baltic/gemma31-fresh-comparison12')]
    exposed = []
    for old in exposed_roots:
        p = old/'specifications.json'
        exposed.extend(load(p))
        pins[str(p.resolve())] = file_hash(p)
    if len(exposed) != 42:
        raise ValueError('Expected preserved 42 exposed comparisons')
    for wave in ('wave4', 'baltic'):
        base = Path('data/dfm13')/wave
        campaign, provider = production.modules(wave)
        previous, inventory = exposure_snapshot(base)
        blocked = {identity(s) for s in previous + exposed}
        blocked_ids = {s['source']['id'] for s in previous + exposed if s.get('source')}
        directory = root/wave
        write_json(directory/'exposure-snapshot.json', dict(inventory=inventory,
            excluded_identities=sorted(blocked), excluded_source_ids=sorted(blocked_ids),
            scope='Known local calibration and production specifications at preparation time; not global pretraining novelty'))
        config_path = base/'synthetic31-full-staged-v2/config.json'
        config = load(config_path)
        production.quotas(config)
        pins[str(config_path.resolve())] = file_hash(config_path)
        config['campaign'] = 'dfm13-balanced31-calibration-20261003-'+wave
        write_json(directory/'config.json', config)
        seeds = base/'seeds'
        pin = load(seeds/'receipt.json')
        if not pin['ready'] or file_hash(seeds/'seeds.sqlite') != pin['sha256']:
            raise ValueError('Seed inventory changed')
        pins[str((seeds/'receipt.json').resolve())] = file_hash(seeds/'receipt.json')
        pins[str((seeds/'seeds.sqlite').resolve())] = pin['sha256']
        c = production.controller(wave, ready['snapshot'])
        review, generation = c.v6.adapters()
        budget = c.v6.Budget(ready['snapshot'])
        allocator = provider.SourceProvider(seeds, directory, config)
        selected, requests, budgets, exclusions = [], {}, {}, []
        try:
            # Pre-exclude known source IDs in the private allocator, not the seed pool.
            with allocator.db:
                for language in provider.LANGUAGES:
                    scopes = [f'{language}/openhermes', f'{language}/{language}']
                    scopes += [f'{language}/{language}/{f}' for f in FAMILIES]
                    allocator.db.executemany('INSERT OR IGNORE INTO used_sources VALUES (?,?)',
                                            ((scope, sid) for scope in scopes for sid in blocked_ids))
            for language in provider.LANGUAGES:
                for family in FAMILIES:
                    count = 0
                    for slot in range(1000000, 1100000):
                        spec = allocator.next_spec(language, family, slot)
                        fingerprint = identity(spec)
                        if fingerprint in blocked:
                            exclusions.append(dict(language=language, family=family, slot=slot, reason='exposed_or_duplicate'))
                            continue
                        key = c.pilot.slot_key(spec)
                        payload = c.v6.generation_request(spec, generation, endpoint_models={
                            'data': [dict(id=MODEL, max_model_len=32768)]})
                        transport, schema = c.v6.compact_request(payload)
                        measured = budget.measure(transport)
                        selected.append(spec)
                        requests[key] = dict(request=transport, schema=schema)
                        budgets[key] = measured
                        blocked.add(fingerprint)
                        count += 1
                        if count == per_group:
                            break
                    if count != per_group:
                        raise ValueError('Fresh group supply exhausted: '+language+'/'+family)
        finally:
            allocator.close()
        groups.update(check_groups(selected, provider.LANGUAGES, per_group))
        all_specs.extend(selected)
        for name, value in [('specifications.json', selected), ('generation-requests.json', requests),
                            ('prompt-budgets.json', budgets), ('exclusions.json', exclusions)]:
            write_json(directory/name, value)
        dependencies = set(production.european._dependencies(c, provider))
        dependencies |= {Path(production.__file__), Path(campaign.__file__), Path(provider._path),
                         Path('dfm12/wave_synthetic_runtime.py'), Path('dfm12/wave_language_review.py'),
                         Path('dfm12/wave4_gemma31_fresh.py'), Path(__file__)}
        dependencies |= set(production.european._asset_paths(ready['snapshot']))
        pins.update({str(p.resolve()): file_hash(p) for p in dependencies})
    # This is only a native student-template smoke, not generated-answer validation.
    from .baltic_sources_cpu import renderer
    student = renderer()
    smoke = student.count([dict(role='user', content='Template check.'),
                           dict(role='assistant', content='Template response.')])
    pins[str((DOWNLOAD/'ready.json').resolve())] = file_hash(DOWNLOAD/'ready.json')
    for path in sorted(root.glob('*/*')):
        if path.is_file():
            pins[str(path.resolve())] = file_hash(path)
    manifest = dict(model=MODEL, revision=ready['revision'], total=len(all_specs),
        groups=groups, group_count=len(groups), per_group=per_group, pins=pins,
        exposed_comparisons=42, exposed_roots=[str(p.resolve()) for p in exposed_roots],
        admission_authorized=False, production_approved=False, publication_allowed=False,
        independent_review_required=True, cpu_only=True, student_template_smoke_tokens=smoke,
        generated_student_context_check='pending actual generated messages/tools; max4096, no truncation',
        reviewer_context_check='pending full generated candidate; actual31B32K check required before each request',
        treatment='Fresh all-group specifications; production31B generation request and compact transport unchanged')
    if len(groups) != 78 or len(all_specs) != 78*per_group:
        raise ValueError('Require all13 languages and six families')
    write_json(root/'manifest.json', manifest)
    write_json(root/'seal.json', dict(manifest_sha256=file_hash(root/'manifest.json')))
    return verify(root)


def verify(root):
    from .wave4_gemma31_fresh import verify as verify_pins
    manifest = verify_pins(Path(root))
    if (manifest['group_count'] != 78 or manifest['total'] != 78*manifest['per_group']
            or manifest['production_approved'] or manifest['admission_authorized']):
        raise ValueError('Calibration coverage/admission drift')
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare', 'verify'])
    p.add_argument('--root', type=Path, default=ROOT)
    a = p.parse_args()
    result = prepare(a.root) if a.command == 'prepare' else verify(a.root)
    print(json.dumps(dict(total=result['total'], groups=result['group_count'], root=str(a.root))))


if __name__ == '__main__':
    main()
