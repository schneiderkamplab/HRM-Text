"""Publish only the 44 manually verified Croatian reordering exclusions."""
import argparse
import json
from pathlib import Path
import shutil
import sys

from . import fa_transform_subset as shared
from .io import digest, file_hash, load, lock, write_json

require = shared.require
POLICY = 'hr_reordering_manual44_v1'
COUNTS = {'paragraph-reordering': (30986, 44)}
NAME = 'dfm13_wave4_wikipedia_hr_paragraph_reordering'
REPO = 'schneiderkamplab/dfm13-wave4-wikipedia-hr-paragraph-reordering'
PARENT_REVISION = 'c44ba953549f6d0c83f38e24504eb4dd78abf3f3'
PARENT_SHA = 'f08fccc4abab05bb5acc95a7954c3c74312e58a0afe33cbb3a49dd57cd2b3d64'
REVIEW = Path('docs/reports/hr-transform-structural-census-20261003-v4')
REVIEW_PINS = {
    'proposed-reordering-ids.json': '29b69b0373fa10e2e1bf3c9e458687767fa29f7ce63d145f4481ecb684e0d131',
    'reviewed44.jsonl': '3cfba448b85c151c7265b5e34d6bb017892025b60ca1089735e675088ddd37ca',
    'receipt.json': '73f0dad9411646ce39ae758eadf8b3a2697f6cae8982e33f40ba0f72eb470ac8',
    'report.json': 'b617546735a2e8649536cbac6545ee7099134578fbf06e0d9029dcf28e442e35'}
TOKEN_ROOT = Path('data/dfm13/tokenized_hr_manual44_subsets')
ATTACHMENTS = {'data/train.jsonl', 'exclusions.jsonl', 'subset-receipt.json',
    'parent-entry.json', 'parent-publication.json', 'parent-export-manifest.json',
    'SOURCE_README.md', 'README.md', 'proposed-reordering-ids.json', 'reviewed44.jsonl',
    'review-receipt.json', 'census-report.json'}


def reviewed():
    for relative, sha in REVIEW_PINS.items():
        require(file_hash(REVIEW / relative) == sha, 'Frozen manual review changed: ' + relative)
    proposal = load(REVIEW / 'proposed-reordering-ids.json')
    require(proposal['source_sha256'] == PARENT_SHA and proposal['task'] == 'paragraph-reordering'
            and len(proposal['ids']) == len(set(proposal['ids'])) == 44, 'Invalid exact-ID proposal')
    evidence = {}
    with (REVIEW / 'reviewed44.jsonl').open() as handle:
        for line in handle:
            row = json.loads(line)
            require(row['id'] not in evidence and row['source_replay_exact'] is True,
                    'Invalid manual review record')
            evidence[row['id']] = row
    require(set(evidence) == set(proposal['ids']), 'Manual review coverage mismatch')
    return evidence


def replay(source, keep, excluded, *, checking=False):
    evidence = reviewed()
    seen = set(); removed = set(); count = tokens = 0
    with Path(source).open('rb') as incoming:
        for raw in incoming:
            row = json.loads(raw)
            require(row['id'] not in seen and row['language'] == 'hr'
                    and row['task'] == 'paragraph-reordering', 'Unexpected source row')
            seen.add(row['id']); count += 1
            require(row['target_message_index'] == len(row['messages'])-1
                    and row['messages'][-1]['role'] == 'assistant'
                    and row['admission_authorized'] is True, 'Invalid accepted target')
            if row['id'] in evidence:
                review = evidence[row['id']]
                require(digest(row) == review['record_sha256'], 'Excluded record hash changed')
                removed.add(row['id'])
                line = (json.dumps(dict(id=row['id'], record_sha256=digest(row),
                    window_sha256=review['window_sha256'], reason=review['note'],
                    review_sha256=REVIEW_PINS['reviewed44.jsonl']), ensure_ascii=False, sort_keys=True)+'\n').encode()
                if checking:
                    require(excluded.readline() == line, 'Exclusion receipt record changed')
                else:
                    excluded.write(line)
            else:
                tokens += row['rendered_tokens']
                if checking:
                    require(keep.readline() == raw, 'Retained bytes/order changed')
                else:
                    keep.write(raw)
    require(count == COUNTS['paragraph-reordering'][0] and removed == set(evidence),
            'Population or exact exclusion coverage mismatch')
    if checking:
        require(not keep.read(1) and not excluded.read(1), 'Unexpected extra records')
    return count-len(removed), tokens


def build(root):
    root = Path(root).resolve()
    require(not root.exists(), 'Use a fresh immutable subset root')
    reviewed()
    registry = load(shared.REGISTRY)
    parent = next(e for e in registry['additions'] if e['name'] == NAME)
    require(parent['hf_repo_id'] == REPO and parent['hf_revision'] == PARENT_REVISION
            and parent['output_sha256'] == PARENT_SHA, 'Original registry pins changed')
    source = Path(parent['output'])
    require(file_hash(source) == PARENT_SHA, 'Original export changed')
    folder = root / 'paragraph-reordering'
    (folder / 'data').mkdir(parents=True)
    write_json(root / 'parent-registry.json', registry)
    output = folder / 'data/train.jsonl'
    with output.open('wb') as keep, (folder / 'exclusions.jsonl').open('wb') as excluded:
        rows, tokens = replay(source, keep, excluded)
    write_json(folder / 'parent-entry.json', parent)
    for src, dest in ((Path(parent['manifest']), 'parent-publication.json'),
            (source.parent.parent / 'manifest.json', 'parent-export-manifest.json'),
            (source.parent.parent / 'README.md', 'SOURCE_README.md'),
            (REVIEW / 'proposed-reordering-ids.json', 'proposed-reordering-ids.json'),
            (REVIEW / 'reviewed44.jsonl', 'reviewed44.jsonl'),
            (REVIEW / 'receipt.json', 'review-receipt.json'),
            (REVIEW / 'report.json', 'census-report.json')):
        shutil.copyfile(src, folder / dest)
    receipt = dict(schema=POLICY, parent_rows=30986, excluded_rows=44, retained_rows=rows,
        parent_output=str(source), parent_output_sha256=PARENT_SHA,
        parent_hf_revision=PARENT_REVISION, hf_repo_id=REPO, review_pins=REVIEW_PINS,
        output_sha256=file_hash(output), exclusion_sha256=file_hash(folder / 'exclusions.jsonl'),
        exact_ordered_byte_subset=True, selection='only_frozen_manually_reviewed_44_ids',
        broad_regex_applied=False, other_tasks_unchanged=True, retained_semantic_certification=False)
    write_json(folder / 'subset-receipt.json', receipt)
    text = (folder / 'SOURCE_README.md').read_text()
    text += ('\n\n## 2026-10-03 exact manually reviewed reordering subset\n\n'
        'This revision supersedes the historical row count above: 30,942 retained '
        'accepted conversations, excluding only 44 individually read and source-replayed '
        'candidate IDs with one substantive shuffled unit plus headings/citations/categories. '
        'All retained messages and attribution are byte-identical. No broad regex, list '
        'filter or change to the other Croatian tasks was applied. Retention is not factual '
        'certification. Source license conditions and attribution above remain applicable.\n\n'
        f'Parent revision: `{PARENT_REVISION}`. See `subset-receipt.json`, `exclusions.jsonl`, '
        '`reviewed44.jsonl`, `proposed-reordering-ids.json`, `parent-publication.json` '
        'and `SOURCE_README.md`. Original exports and publication history are preserved.\n')
    (folder / 'README.md').write_text(text)
    manifest = load(Path(parent['manifest']))
    manifest.pop('hf_revision', None)
    manifest.update(rows=rows, rendered_tokens=tokens, output=str(output), output_sha256=file_hash(output),
        counts=dict(parent_accepted=30986, excluded_by_subset=44, accepted=rows),
        subset_policy=POLICY, subset_receipt=str(folder / 'subset-receipt.json'),
        subset_receipt_sha256=file_hash(folder / 'subset-receipt.json'), parent_hf_revision=PARENT_REVISION,
        status='subset_prepared', uploaded=False, tokenization_performed=False,
        files={relative:file_hash(folder / relative) for relative in sorted(ATTACHMENTS)})
    write_json(folder / 'manifest.json', manifest)
    print('prepared', rows, tokens, flush=True)


def verify_package(folder):
    folder = Path(folder).resolve()
    reviewed()
    m = load(folder / 'manifest.json')
    require(m['name'] == NAME and m['hf_repo_id'] == REPO and m['subset_policy'] == POLICY
            and m['task'] == 'paragraph-reordering', 'Wrong scoped publication')
    require(set(m['files']) == ATTACHMENTS, 'Missing subset attachments')
    for relative, sha in m['files'].items():
        require(file_hash(folder / relative) == sha, 'Subset attachment changed: '+relative)
    for src, dest in (('proposed-reordering-ids.json','proposed-reordering-ids.json'),
                      ('reviewed44.jsonl','reviewed44.jsonl'), ('receipt.json','review-receipt.json'),
                      ('report.json','census-report.json')):
        require(file_hash(folder / dest) == REVIEW_PINS[src], 'Review attachment pin changed')
    p = load(folder / 'parent-entry.json'); pub = load(folder / 'parent-publication.json')
    for field in ('name','repo_id','revision','license','input_sha256','task','target_policy','hf_repo_id'):
        require(m[field] == p[field] == pub[field], 'Source provenance changed: '+field)
    require(p['output_sha256'] == pub['output_sha256'] == PARENT_SHA
            and p['hf_revision'] == pub['hf_revision'] == m['parent_hf_revision'] == PARENT_REVISION,
            'Parent publication pins mismatch')
    require(file_hash(p['output']) == PARENT_SHA, 'Original data changed')
    require(Path(m['output']).resolve() == folder / 'data/train.jsonl'
            and Path(m['subset_receipt']).resolve() == folder / 'subset-receipt.json', 'Output path mismatch')
    receipt = load(folder / 'subset-receipt.json')
    require(file_hash(folder / 'subset-receipt.json') == m['subset_receipt_sha256']
            and receipt['review_pins'] == REVIEW_PINS and receipt['schema'] == POLICY,
            'Subset receipt pin mismatch')
    with (folder / 'data/train.jsonl').open('rb') as keep, (folder / 'exclusions.jsonl').open('rb') as excluded:
        rows, tokens = replay(p['output'], keep, excluded, checking=True)
    require(rows == m['rows'] == receipt['retained_rows'] == 30942
            and receipt['excluded_rows'] == 44 and tokens == m['rendered_tokens'], 'Subset count mismatch')
    require(file_hash(folder / 'data/train.jsonl') == receipt['output_sha256'] == m['output_sha256']
            and file_hash(folder / 'exclusions.jsonl') == receipt['exclusion_sha256'], 'Subset hashes mismatch')
    return m


def tokenize(folder):
    return shared.tokenize(folder, verifier=verify_package, token_root=TOKEN_ROOT)


def promote_registry(root, entries):
    require(len(entries) == 1 and entries[0]['name'] == NAME, 'Only HR reordering may change')
    shared.promote_registry(root, entries)


def verify_assembly_publication(entry, source, pins, api):
    return shared.verify_assembly_publication(entry, source, pins, api, verifier=verify_package)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build','verify','tokenize','publish'])
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    with lock(args.root.parent / (args.root.name+'.lock')):
        if args.command == 'build': build(args.root)
        elif args.command == 'publish':
            shared.publish(args.root, backend=sys.modules[__name__],
                           commit_message='Exclude only 44 manually reviewed Croatian reordering IDs')
        elif args.command == 'tokenize': print(tokenize(args.root / 'paragraph-reordering'))
        else: print(verify_package(args.root / 'paragraph-reordering')['rows'])


if __name__ == '__main__':
    main()
