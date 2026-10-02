"""Seal completed screened components for audit only, independently of other holds."""
import argparse
import json
from pathlib import Path

from scripts import screen_dfm13_pending_arena as screen
from scripts.prepare_dfm13_pending_arena import ROOT, json_write, sha256 as file_sha256

ALLOWED = {'comparia', 'helpsteer3_edit', 'helpsteer3_preference', 'expert5k'}


def sha256(path):
    return file_sha256(Path(path))


def prepare(screened, original, names, output):
    screened, original, output = map(lambda p: Path(p).resolve(), (screened, original, output))
    if not names or len(names) != len(set(names)) or set(names) - ALLOWED:
        raise ValueError('Explicit non-PRISM components required')
    inventory = json.loads((original/'manifest.json').read_text())
    if sha256(original/'manifest.json') != json.loads((original/'seal.json').read_text())['manifest_sha256']:
        raise ValueError('Original seal mismatch')
    screen.verify_pins(inventory['pins'])
    completed_manifest = screened/'manifest.json'
    if completed_manifest.exists():
        if sha256(completed_manifest) != json.loads((screened/'seal.json').read_text())['manifest_sha256']:
            raise ValueError('Screened seal mismatch')
        screen.verify_pins(json.loads(completed_manifest.read_text())['pins'])
    known = {s['name']: s for s in inventory['sources']}
    preparation = json.loads((screened/'preparation.json').read_text())
    if preparation['validation_sources'] != screen.validation_inventory():
        # The completed inventory adds counts; verify fields without discarding those counts.
        for before, current in zip(preparation['validation_sources'], screen.validation_inventory(), strict=True):
            if any(before[k] != v for k, v in current.items()):
                raise ValueError('Validation inventory drift')
    entries, evidence_records = [], []
    for name in names:
        directory = screened/name
        result = json.loads((directory/'manifest.json').read_text())
        source = known[name]
        if result['input'] != source or sha256(source['path']) != source['sha256']:
            raise ValueError('Component input drift')
        original_manifest = Path(source['manifest_path'])
        if sha256(original_manifest) != source['manifest_sha256']:
            raise ValueError('Source manifest drift')
        source_pin = json.loads(original_manifest.read_text())['source_pin']
        for path_key, hash_key in [('path', 'sha256'), ('card_path', 'card_sha256'), ('receipt_path', 'receipt_sha256')]:
            if sha256(source_pin[path_key]) != source_pin[hash_key]:
                raise ValueError('Pinned source evidence drift')
        files = {'candidates.jsonl': 'output_sha256', 'preflight.jsonl': 'preflight_sha256',
                 'excluded.jsonl': 'exclusions_sha256'}
        for file, key in files.items():
            if sha256(directory/file) != result[key]:
                raise ValueError('Screened component drift')
        measured = {}
        for line in (directory/'preflight.jsonl').open():
            budget = json.loads(line)
            if budget['id'] in measured:
                raise ValueError('Duplicate preflight ID')
            measured[budget['id']] = budget
        ids = set()
        for line in (directory/'candidates.jsonl').open():
            row = json.loads(line)
            budget = measured[row['id']]
            if row['id'] in ids or not budget['eligible'] or budget['truncation']:
                raise ValueError('Invalid eligible row preflight')
            if budget['prompt_tokens']+budget['max_tokens'] > budget['context_limit']:
                raise ValueError('Context overflow')
            ids.add(row['id'])
        if len(ids) != result['counts'].get('audit_eligible', 0) or not ids:
            raise ValueError('Eligible count mismatch or empty source')
        evidence = dict(component=name, scope='audit_only_no_training_no_redistribution',
            license_decision='Eligible for the requested source audit under pinned source terms; no grant beyond auditing inferred.',
            source_pin=source_pin, counts=result['counts'],
            heldout_scope='Exact contexts and adjacent user/answer pairs, including earlier turns, against all five pinned HelpSteer3 validation subsets.',
            unresolved=['Exhaustive inherited DFM11/12 overlap', 'Other benchmark prompt/text overlap',
                        'Provider-output terms and training/redistribution admission remain separate gates'],
            expert_policy='Expert5K is upstream train, not a designated evaluation split; train does not prove benchmark cleanliness.',
            no_admission=True, no_upload=True,
            pins={str(directory/file): sha256(directory/file) for file in [*files, 'manifest.json']})
        evidence_records.append((name, evidence))
        entries.append(dict(name=name, status='ready', license_cleared=True, heldout_overlap_cleared=True,
            clearance_scope='audit_only; explicitly bounded overlap coverage in evidence',
            input_sha256=source['sha256'], eligible_source=dict(path=str(directory/'candidates.jsonl'),
            sha256=result['output_sha256'], rows=len(ids))))
    output.mkdir(parents=True, exist_ok=False)
    for entry, (name, evidence) in zip(entries, evidence_records):
        path = output/(name+'-clearance.json')
        json_write(path, evidence)
        entry['evidence'] = [dict(path=str(path), sha256=sha256(path))]
        if completed_manifest.exists():
            entry['evidence'].append(dict(path=str(completed_manifest), sha256=sha256(completed_manifest)))
    entries.extend(dict(name=n, status='held', reason='license_pending' if n == 'prism' else 'not_in_this_completed_batch')
                   for n in known if n not in names)
    receipt = dict(version=1, inventory_sha256=sha256(original/'manifest.json'), sources=entries,
                   no_admission=True, no_upload=True, total=sum(e['eligible_source']['rows'] for e in entries if e['status']=='ready'))
    json_write(output/'eligibility.json', receipt)
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--screened', type=Path, default=ROOT/'data/dfm13/pending-arena-screened-20261001')
    p.add_argument('--original', type=Path, default=ROOT/'data/dfm13/pending-arena-candidates-20261001')
    p.add_argument('--sources', nargs='+', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(prepare(args.screened, args.original, args.sources, args.output), indent=2))
