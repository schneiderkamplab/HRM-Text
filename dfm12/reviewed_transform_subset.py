"""Exact four reviewed SL/SQ exclusions; immutable same-repository successors."""
import argparse
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

from . import fa_transform_subset as shared
from . import wave_manual_exclusion as manual
from .io import digest, file_hash, load, lock, write_json

POLICY = 'sl_sq_reviewed_exact4_v1'
TOKEN_ROOT = Path('data/dfm13/tokenized_sl_sq_exact4_subsets')
PARENTS = {
    ('sl', 'prefix-continuation'): (60100, '5964d460dd114eaaff522d395f71734eb20cc9a4', 'b0d17297375f8bcc97eb0b29a701efc58767a04a0b86b1522b935b3810203a5f', 1),
    ('sl', 'paragraph-reordering'): (31015, 'b1bcb2789ac08c34fbe170469ce0a681a15641e5', '9319a41f3c512f0ee15fb691772c06c08efaccb0d0097c7213ece677fd9345a2', 14),
    ('sq', 'paragraph-reordering'): (22930, 'a2c0a718781e4f339cf63f15e8334ad3f3b098f7', '79dc044209085e49cd040c442c86fdd8511744286e397fcfe25e8b8495784f1f', 18),
    ('sq', 'prefix-continuation'): (24997, '604c6e64b4c880a02edda0bd14e219f3fdb030e3', 'f84b7db688d86dce2ebe44d9a94b8a98e53f31e87797b56d54e040849f9c397a', 28),
}
ATTACHMENTS = {'data/train.jsonl', 'exclusions.jsonl', 'subset-receipt.json',
    'parent-entry.json', 'parent-publication.json', 'parent-export-manifest.json',
    'SOURCE_README.md', 'README.md', 'review.json', 'review-receipt.json', 'review-report.md'}
require = shared.require


def name_for(language, task):
    return f'dfm13_wave4_wikipedia_{language}_' + task.replace('-', '_')


def hold(root):
    root = Path(root).resolve()
    decisions = manual.reviewed_decisions()
    receipt = root / 'quality-hold.json'
    payload = dict(policy=POLICY, scope='four_affected_entries_only', decisions=decisions,
        review_receipt_sha256=manual.RECEIPT_SHA, reason='Exact reviewed rows pending verified successor subsets')
    if receipt.exists():
        require(load(receipt) == payload, 'Hold receipt changed')
    else:
        write_json(receipt, payload)
    with lock(shared.REGISTRY.with_suffix('.lock')):
        registry = load(shared.REGISTRY)
        for (lang, task), (_, revision, sha, _) in PARENTS.items():
            entry = next(e for e in registry['additions'] if e['name'] == name_for(lang, task))
            require(entry['hf_revision'] == revision and entry['output_sha256'] == sha, 'Parent changed')
            value = dict(receipt=str(receipt), receipt_sha256=file_hash(receipt), scope='exact_reviewed_id_successor_pending')
            require(not entry.get('quality_hold') or entry['quality_hold'] == value, 'Unrelated quality hold')
            entry['quality_hold'] = value
        write_json(shared.REGISTRY, registry)


def verify_excluded(row, evidence):
    original = evidence['record']
    # Publication adds attribution, target metadata and the captured judge result;
    # it must not change any pre-admission content or original provenance fields.
    expected = dict(original)
    provenance = dict(original['provenance'])
    require(set(row['provenance']) == set(provenance) | {'license', 'license_card_sha256'}, 'Unexpected attribution fields')
    provenance.update({k: row['provenance'][k] for k in ('license', 'license_card_sha256')})
    expected.update(provenance=provenance, admission_authorized=True,
        target_message_index=len(original['messages'])-1, quality_status='accepted',
        audit=evidence['acceptance_review'])
    require(row == expected and digest(original) == evidence['record_sha256'], 'Reviewed pre-admission/export mapping changed')


def replay(source, language, task, keep, excluded, checking=False):
    manual.reviewed_decisions()
    count, _, _, case = PARENTS[(language, task)]
    evidence = next(x for x in load(manual.REVIEW / 'evidence.json') if x['case'] == case)
    decision = next(x for x in manual.reviewed_decisions() if x['id'] == evidence['id'])
    seen = set(); found = 0; rows = tokens = 0
    with Path(source).open('rb') as handle:
        for raw in handle:
            row = json.loads(raw)
            require(row['id'] not in seen and row['language'] == language and row['task'] == task, 'Unexpected/duplicate source row')
            seen.add(row['id']); rows += 1
            if row['id'] == evidence['id']:
                verify_excluded(row, evidence)
                found += 1
                event = dict(decision, prior_status='accepted', status=manual.STATUS,
                    published_record_sha256=digest(row), original_published_record=row,
                    original_preadmission_record=evidence['record'], original_model_review=evidence['acceptance_review'])
                line = (json.dumps(event, ensure_ascii=False, sort_keys=True)+'\n').encode()
                if checking:
                    require(excluded.readline() == line, 'Exclusion receipt changed')
                else:
                    excluded.write(line)
            else:
                tokens += row['rendered_tokens']
                if checking:
                    require(keep.readline() == raw, 'Retained bytes/order changed')
                else:
                    keep.write(raw)
    require(rows == count and found == 1, 'Exact exclusion/count mismatch')
    if checking:
        require(not keep.read(1) and not excluded.read(1), 'Extra subset rows')
    return rows - 1, tokens


def build(root, language, task):
    root = Path(root).resolve(); folder = root / task
    require(not folder.exists(), 'Use fresh immutable package')
    count, revision, sha, _ = PARENTS[(language, task)]
    parent = next(e for e in load(shared.REGISTRY)['additions'] if e['name'] == name_for(language, task))
    require(parent['hf_revision'] == revision and parent['output_sha256'] == sha and parent['rows'] == count, 'Parent changed')
    source = Path(parent['output'])
    require(file_hash(source) == sha, 'Published original changed')
    (folder / 'data').mkdir(parents=True)
    with (folder / 'data/train.jsonl').open('wb') as keep, (folder / 'exclusions.jsonl').open('wb') as excluded:
        rows, tokens = replay(source, language, task, keep, excluded)
    write_json(folder / 'parent-entry.json', parent)
    for src, dest in ((Path(parent['manifest']), 'parent-publication.json'),
        (source.parent.parent/'manifest.json', 'parent-export-manifest.json'),
        (source.parent.parent/'README.md', 'SOURCE_README.md'),
        (manual.REVIEW/'review.json', 'review.json'), (manual.REVIEW/'receipt.json', 'review-receipt.json'),
        (manual.REVIEW/'report.md', 'review-report.md')):
        shutil.copyfile(src, folder / dest)
    output = folder / 'data/train.jsonl'
    receipt = dict(schema=POLICY, language=language, task=task, parent_rows=count,
        excluded_rows=1, retained_rows=rows, parent_output_sha256=sha, parent_hf_revision=revision,
        output_sha256=file_hash(output), exclusion_sha256=file_hash(folder/'exclusions.jsonl'),
        exact_ordered_byte_subset=True, broad_regex_applied=False, review_receipt_sha256=manual.RECEIPT_SHA)
    write_json(folder/'subset-receipt.json', receipt)
    (folder/'README.md').write_text((folder/'SOURCE_README.md').read_text() +
        f'\n\n## Exact manual-review successor (2026-10-03)\n\nThis revision supersedes the count above: {rows:,} retained conversations, '
        'with only one explicitly authorized, hash-bound reviewed ID excluded. Retained bytes, order, attribution and license conditions are unchanged. '
        'See exclusions.jsonl for original messages, model review, manual reason and review pins; subset-receipt.json and parent-publication.json preserve lineage. '
        'No broad filter or semantic certification of retained rows is implied.\n')
    manifest = load(folder/'parent-publication.json')
    for key in ('hf_revision', 'quality_hold', 'tokenized_path', 'tokenization_receipt', 'tokenization_receipt_sha256'):
        manifest.pop(key, None)
    manifest.update(rows=rows, rendered_tokens=tokens, output=str(output), output_sha256=file_hash(output),
        counts=dict(parent_accepted=count, excluded_manual_review=1, accepted=rows),
        subset_policy=POLICY, subset_receipt=str(folder/'subset-receipt.json'),
        subset_receipt_sha256=file_hash(folder/'subset-receipt.json'), parent_hf_revision=revision,
        status='subset_prepared', uploaded=False, tokenization_performed=False,
        files={p:file_hash(folder/p) for p in sorted(ATTACHMENTS)})
    write_json(folder/'manifest.json', manifest)


def verify_package(folder):
    folder = Path(folder).resolve(); m = load(folder/'manifest.json')
    r = load(folder/'subset-receipt.json'); language, task = r['language'], r['task']
    count, revision, sha, _ = PARENTS[(language, task)]
    require(m['name'] == name_for(language, task) and m['task'] == task and m['subset_policy'] == POLICY, 'Wrong scope')
    require(set(m['files']) == ATTACHMENTS, 'Missing attachments')
    for relative, pin in m['files'].items():
        require(file_hash(folder/relative) == pin, 'Attachment changed: '+relative)
    require(file_hash(folder/'review-receipt.json') == manual.RECEIPT_SHA and file_hash(folder/'review-report.md') == manual.REPORT_SHA, 'Review changed')
    require(file_hash(folder/'review.json') == load(manual.REVIEW/'receipt.json')['pins']['review.json'], 'Review rows changed')
    p = load(folder/'parent-entry.json'); pub = load(folder/'parent-publication.json')
    for field in ('name','repo_id','revision','license','input_sha256','task','target_policy','hf_repo_id'):
        require(m[field] == p[field] == pub[field], 'Provenance changed: '+field)
    require(p['hf_revision'] == pub['hf_revision'] == m['parent_hf_revision'] == revision, 'Parent revision changed')
    require(p['output_sha256'] == pub['output_sha256'] == sha == file_hash(p['output']), 'Parent data changed')
    require(Path(m['output']).resolve() == folder/'data/train.jsonl' and Path(m['subset_receipt']).resolve() == folder/'subset-receipt.json', 'Paths changed')
    require(file_hash(folder/'subset-receipt.json') == m['subset_receipt_sha256'] and r['schema'] == POLICY, 'Subset receipt changed')
    with (folder/'data/train.jsonl').open('rb') as keep, (folder/'exclusions.jsonl').open('rb') as excluded:
        rows, tokens = replay(p['output'], language, task, keep, excluded, checking=True)
    require(rows == count-1 == m['rows'] == r['retained_rows'] and tokens == m['rendered_tokens'] and r['excluded_rows'] == 1, 'Counts changed')
    require(file_hash(folder/'data/train.jsonl') == r['output_sha256'] == m['output_sha256'] and file_hash(folder/'exclusions.jsonl') == r['exclusion_sha256'], 'Data changed')
    return m


def tokenize(folder):
    return shared.tokenize(folder, verifier=verify_package, token_root=TOKEN_ROOT)


def prepare_entry(entry):
    # Shared publisher starts from the held parent entry. Clear only our own hold
    # after every attachment, token array and assembler check succeeds.
    value = entry.pop('quality_hold', None)
    require(value and value['scope'] == 'exact_reviewed_id_successor_pending', 'Missing scoped parent hold')
    return entry


def promote_registry(root, entries):
    shared.promote_registry(root, entries)


def verify_assembly_publication(entry, source, pins, api):
    return shared.verify_assembly_publication(entry, source, pins, api, verifier=verify_package)


def publish(root, language, task):
    backend = SimpleNamespace(POLICY=POLICY, COUNTS={task:(PARENTS[(language, task)][0],1)},
        verify_package=verify_package, tokenize=tokenize, promote_registry=promote_registry, prepare_entry=prepare_entry)
    return shared.publish(root, backend=backend, commit_message='Exclude one exact independently reviewed transform ID; preserve source lineage')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('hold','build','verify','publish'))
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--language', choices=('sl','sq'))
    p.add_argument('--task', choices=('prefix-continuation','paragraph-reordering'))
    args = p.parse_args()
    with lock(args.root.parent/(args.root.name+'.lock')):
        if args.command == 'hold': hold(args.root)
        elif args.command == 'build': build(args.root,args.language,args.task)
        elif args.command == 'verify': print(verify_package(args.root/args.task)['rows'])
        else: publish(args.root,args.language,args.task)
