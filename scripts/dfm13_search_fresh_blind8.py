"""Fresh nonheld candidate bytes, prioritizing never-manually-seen task IDs."""
from collections import Counter
import hashlib
from pathlib import Path
import random
import re

from scripts import dfm13_search_postbatch_accounting as accounting

base = accounting.base
read = accounting.read
ROOT = Path('data/dfm13/search-fresh-nonheld-blind8-20261001')
INVENTORY = Path('data/dfm13/search-postbatch-accounting-20261001-v4/inventory.json')
SEED = 2026100108


def references(row):
    candidate = row.get('candidate', {})
    hashes = set()
    if isinstance(candidate, dict) and candidate.get('sha256'):
        hashes.add(candidate['sha256'])
    if row.get('candidate_sha256'):
        hashes.add(row['candidate_sha256'])
    hashes.update(p['sha256'] for p in row.get('pins', []) if p['path'].endswith('/candidate.json'))
    return hashes


def select(pool, seen_prefixes, seen_hashes, size=8):
    eligible = [r for r in pool if r['sha256'] not in seen_hashes and not r['held']]
    rng = random.Random(SEED)
    fresh_ids = sorted([r for r in eligible if not any(r['id'].startswith(p) for p in seen_prefixes)], key=lambda r:r['id'])
    fresh_versions = sorted([r for r in eligible if any(r['id'].startswith(p) for p in seen_prefixes)], key=lambda r:r['id'])
    rng.shuffle(fresh_ids); rng.shuffle(fresh_versions)
    chosen = []; ids = set(); contents = set()
    for row in fresh_ids + fresh_versions:
        if row['id'] in ids or row['training_sha256'] in contents:
            continue
        chosen.append(dict(row, never_manually_seen_id=not any(row['id'].startswith(p) for p in seen_prefixes)))
        ids.add(row['id']); contents.add(row['training_sha256'])
        if len(chosen) == size:
            return chosen
    raise ValueError('not enough distinct fresh nonheld candidate bytes')


def main():
    if ROOT.exists():
        raise ValueError('new packet root required')
    inventory = read(INVENTORY)
    pins = {str(INVENTORY.resolve()):base.file_hash(INVENTORY), str(Path(__file__).resolve()):base.file_hash(Path(__file__))}
    seen_prefixes = set(); seen_hashes = set()
    reports = set(accounting.REPORTS)
    reports.update(Path('docs/reports').glob('dfm13_search*receipt*.json'))
    reports.update(Path('docs/reports').glob('dfm13_search*assessment*.json'))
    for path in sorted(reports):
        receipt = read(path)
        pins[str(path.resolve())] = base.file_hash(path)
        for row in accounting.receipt_rows(receipt):
            if row.get('id'):
                seen_prefixes.add(row['id'])
            seen_hashes.update(references(row))
    early = Path('docs/reports/dfm13_search_trajectory_assessment_20261001.md')
    seen_prefixes.update(re.findall(r'^\| `([0-9a-f]{8,64})`', early.read_text(), flags=re.MULTILINE))
    pins[str(early.resolve())] = base.file_hash(early)
    # Metadata-only revisions of held training messages must not evade a hold.
    all_paths = list(Path('data/dfm13').glob('search*/records/*/candidate.json'))
    all_paths += list(Path('data/dfm13').glob('search-heldout-cpu-corrections*/*/candidate.json'))
    held_hashes = {h.get('candidate_sha256') for h in inventory['holds']}
    held_contents = {h.get('candidate_content_sha256') for h in inventory['holds']}
    held_training = set()
    for path in all_paths:
        candidate = read(path)
        if base.file_hash(path) in held_hashes or base.digest(candidate) in held_contents:
            held_training.add(base.digest(dict(messages=candidate['messages'],tools=candidate['tools'])))
    rows = {r['id']:r for r in inventory['rows']}
    pool = []
    for path in sorted((accounting.campaign.ROOT / 'records').glob('*/candidate.json')):
        key = path.parent.name
        version = next(v for v in rows[key]['versions'] if v['candidate'] == str(path))
        if version['automated_verdict'] != 'keep' or not version['student_fit_verified']:
            continue
        candidate = read(path)
        training_sha = base.digest(dict(messages=candidate['messages'],tools=candidate['tools']))
        pool.append(dict(id=key,path=str(path),sha256=base.file_hash(path),training_sha256=training_sha,
            held=version['exact_hold'] or bool(version['negative_same_content_reviews']) or training_sha in held_training))
    chosen = select(pool,seen_prefixes,seen_hashes)
    jobs = {j['id']:j for j in read(accounting.campaign.ROOT / 'jobs.json')}
    cases = []
    for row in chosen:
        path = Path(row['path'])
        candidate = read(path)
        packet = accounting.packets.packet(candidate,jobs[row['id']]['sample'])
        packet.update(source_candidate=str(path),source_sha256=row['sha256'])
        target = ROOT / 'packets' / row['id'] / 'packet.json'
        base.atomic(target,packet)
        pins[str(path.resolve())] = row['sha256']
        pins[str(target.resolve())] = base.file_hash(target)
        cases.append(dict(id=row['id'],packet=str(target),packet_sha256=base.file_hash(target),
            candidate_sha256=row['sha256'],never_manually_seen_id=row['never_manually_seen_id'],
            exact_candidate_previously_reviewed=False))
    base.atomic(ROOT / 'selection-private.json',dict(seed=SEED,pool=pool,selected=chosen,
        known_manual_id_prefixes=sorted(seen_prefixes),known_manual_candidate_hashes=sorted(seen_hashes),
        selection='Prioritize unreviewed IDs, then unreviewed bytes of prior IDs; deterministic shuffle within each group.',
        no_exact_hash_overlap=True,excludes_known_holds=True,admission_authorized=False))
    base.atomic(ROOT / 'queue.json',dict(cases=cases,pins=pins,admission_authorized=False,
        review_instructions='Assess exact original question/date and delivered evidence. Separate supported useful cores from unsupported claims, completion gaps and source/date mismatches. No model verdict supplied. Record candidate-hash-bound disposition; no admission.'))
    print(dict(queue=str(ROOT / 'queue.json'),cases=len(cases),
        never_manually_seen_ids=sum(r['never_manually_seen_id'] for r in chosen),
        fresh_versions_of_prior_ids=sum(not r['never_manually_seen_id'] for r in chosen),
        exact_candidate_overlap=0))


if __name__ == '__main__':
    main()
