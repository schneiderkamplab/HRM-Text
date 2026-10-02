"""Prepare the isolated 700-slot trial on CPU; never launch models or training."""
import argparse
from collections import Counter
from pathlib import Path
import shutil
import sqlite3

from .audit_pilot_gpu import TOKENIZER_DIR
from .identity_gpu import training_renderer
from .io import file_hash, load, write_json
from .multilingual_calibration import calibration_cases, prepare as prepare_calibration
from .multilingual_seeds import LANGUAGES
from .multilingual_tasks import MODEL, spec_for
from .multilingual_trial import POLICY, verify_inputs

QUOTAS = {'grounded-instruct': 30, 'summary-rewrite': 20, 'multiturn': 20,
          'openhermes': 10, 'math-code': 10, 'tool-dialogue': 10}
IMPLEMENTATIONS = ('multilingual_prepare_calibrated.py', 'multilingual_trial.py',
    'multilingual_pilot.py', 'multilingual_calibration.py', 'multilingual_review.py',
    'multilingual_tasks.py', 'multilingual_tool_dialogue.py', 'multilingual_references.py', 'multilingual_run.py',
    'identity_gpu.py', 'jobs.py', 'prepare.py', 'records.py', 'multilingual_diagnose.py',
    'multilingual_review_evidence.py', 'multilingual_calibration_probe.py',
    'multilingual_review_structured.py', 'multilingual_review_tools.py', 'multilingual_review_routed.py')


def unused_snapshot(previous):
    """Only the fully unstarted failed cohort can donate its complete reservoirs."""
    with sqlite3.connect((previous / 'pilot.sqlite').resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.execute('BEGIN')
        slots = db.execute('SELECT count(*) FROM slots').fetchone()[0]
        used = db.execute("SELECT count(*) FROM slots WHERE attempts != 0 OR candidate IS NOT NULL OR status != 'pending'").fetchone()[0]
        events = db.execute('SELECT count(*) FROM events').fetchone()[0]
        if slots != 35000 or used or events:
            raise ValueError('Donor is not the unused failed 35000-slot cohort')
        hashes = sorted(r[0] for r in db.execute('SELECT hash FROM accepted_hashes'))
    if sorted(load(previous / 'previous-hashes.json')) != hashes:
        raise ValueError('Inherited dedup ledger changed')
    checks = load(previous / 'review-calibration.json')['checks']
    if not any(c['expected_keep'] != c['actual_keep'] for c in checks):
        raise ValueError('Expected failed donor calibration')
    return {'slots': slots, 'used_slots': used, 'events': events, 'inherited_hashes': len(hashes)}


def prepare(previous, root, tokenizer_dir=TOKENIZER_DIR, review_variant=None):
    previous, root = Path(previous), Path(root)
    if root.exists():
        raise FileExistsError('Refusing to overwrite trial root')
    snapshot = unused_snapshot(previous)
    for name, expected in load(previous / 'seeds-ready.json').items():
        if file_hash(previous / name) != expected:
            raise ValueError('Donor seed pin mismatch: ' + name)
    names = [f'seeds-{lang}.json' for lang in (*LANGUAGES, 'openhermes')]
    names += ['previous-hashes.json', 'training-template.json']
    donor_pins = {name: file_hash(previous / name) for name in names}
    root.mkdir(parents=True)
    for name in names:
        shutil.copyfile(previous / name, root / name)
    training_renderer(root)  # Requires exact current raw student template receipt.
    config = dict(contract_version=3, cohort=root.name, quotas=QUOTAS, languages=list(LANGUAGES),
        second_review=True, calibration_policy=POLICY, generator_model=MODEL, reviewer_model=MODEL,
        previous_pilot=str(previous.resolve()), native_review='pending', bulk_authorized=False,
        max_candidate_attempts=6, target_slots=700, no_automatic_bulk_resume=True)
    if review_variant is not None:
        from .multilingual_diagnose import VARIANTS
        if review_variant not in VARIANTS:
            raise ValueError('Unknown diagnostic followup review variant')
        config.update(diagnostic_followup=True, raw_response_logging=True,
                      review_options={'variant': review_variant}, calibration_concurrency=2)
    write_json(root / 'pilot-config.json', config)
    seeds = {lang: load(root / f'seeds-{lang}.json') for lang in (*LANGUAGES, 'openhermes')}
    if any(len(seeds[lang]) < 3010 for lang in LANGUAGES) or len(seeds['openhermes']) < 70:
        raise ValueError('Insufficient nonwrapping source reservoir')
    specs = [spec_for(lang, family, slot, 0, seeds, config)
             for lang in LANGUAGES for family, count in QUOTAS.items() for slot in range(count)]
    write_json(root / 'slot-specifications.json', specs)
    coverage = []
    seen_sources = set()
    for language in LANGUAGES:
        for family in QUOTAS:
            selected = [s for s in specs if s['language_code'] == language and s['family'] == family]
            if len(selected) != QUOTAS[family]:
                raise ValueError('Incomplete allocation coverage')
            for spec in selected:
                if 'source' in spec:
                    key = ('openhermes' if family == 'openhermes' else language, spec['source']['id'])
                    if key in seen_sources:
                        raise ValueError('Repeated allocated source: ' + str(key))
                    seen_sources.add(key)
            coverage.append(dict(language=language, family=family, slots=len(selected),
                subtypes=dict(Counter(s['subtype'] for s in selected)),
                reference_types=dict(Counter(s['reference'].get('type', 'unspecified') for s in selected if 'reference' in s)),
                tool_domains=dict(Counter(s['scenario']['domain'] for s in selected if 'scenario' in s))))
    write_json(root / 'allocation-coverage.json', {'groups': coverage, 'unique_allocated_sources': len(seen_sources)})
    prepare_calibration(root / 'calibration', tokenizer_dir)
    if review_variant is not None:
        from .multilingual_diagnose import PromptBudget, configured_review_request
        budget = PromptBudget(tokenizer_dir)
        selected_requests = []
        for case in calibration_cases():
            payload = configured_review_request(case['record'], config)
            selected_requests.append(dict(name=case['name'], split=case['split'],
                request=payload, prompt_tokens=budget.measure(payload)))
        write_json(root / 'calibration/selected-review-requests.json', selected_requests)
    write_json(root / 'donor-evidence.json', dict(root=str(previous.resolve()), snapshot=snapshot, pins=donor_pins,
        reason='Failed startup calibration; no generation events or attempts. First-cohort exclusions and accepted hashes retained.'))
    if snapshot != unused_snapshot(previous) or any(file_hash(previous / n) != h for n, h in donor_pins.items()):
        raise ValueError('Donor changed during preparation')
    write_json(root / 'ready.json', dict(target_slots=700, quotas_per_language=QUOTAS,
        slots_per_language=dict(Counter(s['language_code'] for s in specs)),
        unused_seed_supply={k: len(v) for k, v in seeds.items()},
        maximum_candidate_attempts=4200, calibration_status='not_model_evaluated',
        accepted_rows=0, accepted_tokens=0, native_review='pending', bulk_authorized=False, cpu_only=True))
    write_json(root / 'implementation-pins.json', {name: file_hash(Path(__file__).parent / name) for name in IMPLEMENTATIONS})
    write_json(root / 'seeds-ready.json', {str(p.relative_to(root)): file_hash(p)
        for p in sorted(root.rglob('*')) if p.is_file()})
    verify_inputs(root, require_receipt=False)


def certify(root, test_report):
    """Publish the watcher trigger last, after the caller supplies passing tests."""
    root, test_report = Path(root), Path(test_report)
    import xml.etree.ElementTree as ET
    suites = ET.parse(test_report).getroot()
    suites = [suites] if suites.tag == 'testsuite' else list(suites.iter('testsuite'))
    if not suites or sum(int(s.get('tests', 0)) for s in suites) < 1 or any(
            int(s.get(k, 0)) for s in suites for k in ('failures', 'errors', 'skipped')):
        raise ValueError('Tests did not all pass')
    verify_inputs(root, require_receipt=False)
    training_renderer(root)
    inspection = load(root / 'calibration/render-inspection/inspection.json')
    if inspection['cases'] != len(calibration_cases()) or inspection['model'] != MODEL:
        raise ValueError('Incomplete CPU calibration inspection')
    write_json(root / 'cpu-preflight-passed.json', dict(passed=True, cpu_only=True,
        seeds_ready_sha256=file_hash(root / 'seeds-ready.json'),
        tests={'path': str(test_report.resolve()), 'sha256': file_hash(test_report),
               'count': sum(int(s.get('tests', 0)) for s in suites)},
        model=MODEL, calibration_model_passed=False, generation_requires_all_controls_pass=True,
        bulk_authorized=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--certify-tests', type=Path)
    from .multilingual_diagnose import VARIANTS
    parser.add_argument('--review-variant', choices=VARIANTS)
    args = parser.parse_args()
    if args.certify_tests:
        certify(args.root, args.certify_tests)
    else:
        if args.previous is None:
            parser.error('--previous is required for preparation')
        prepare(args.previous, args.root, review_variant=args.review_variant)
