"""Exact, immutable Persian Wikipedia census subset publication and tokenization."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np

from .io import atomic, digest, file_hash, load, lock, write_json

POLICY = 'fa_minimal_structural_v2'
CENSUS = Path('docs/reports/fa-transform-structural-census-20261003-v2')
REPORT_SHA = '8f3c77afe2558090de312b8632b18e8c952102163d6c819cc57a8673da7369cd'
FLAGS_SHA = '7bba7ec4ec7d0c94d1bdfe4f38763b9e1e4f3ce6033866086c35fd7b9ecd1ddc'
COUNTS = {'denoising': (73802, 2223), 'paragraph-reordering': (31490, 1102),
          'prefix-continuation': (110813, 3281), 'span-filling': (25937, 480)}
REGISTRY = Path('config/dfm13_sources.json')
TOKEN_ROOT = Path('data/dfm13/tokenized_fa_minimal_subsets')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def census():
    require(file_hash(CENSUS / 'report.json') == REPORT_SHA, 'Census report changed')
    require(file_hash(CENSUS / 'flags.jsonl') == FLAGS_SHA, 'Frozen census flags changed')
    return load(CENSUS / 'report.json')


def flags_for(task):
    with (CENSUS / 'flags.jsonl').open() as handle:
        for line in handle:
            row = json.loads(line)
            if row['task'] == task:
                yield row


def selected(flag):
    value = (flag['flags']['category_only'] or flag['flags']['heading_only']
             or (flag['task'] == 'paragraph-reordering'
                 and flag['effective_prose_paragraphs'] < 2 and flag['uncertain_blocks'] == 0))
    require(value == flag['flags']['minimal_filter_candidate'], 'Census selector inconsistency')
    return value


def replay(source, task, retained, excluded, *, checking=False):
    """Consume each original byte line once; never rewrite an accepted record."""
    count = removed = tokens = 0
    flags = iter(flags_for(task))
    seen = set()
    with Path(source).open('rb') as incoming:
        for line in incoming:
            row = json.loads(line)
            flag = next(flags, None)
            require(flag is not None and flag['candidate_id'] == row['id']
                    and flag['record_sha256'] == digest(row) and row['task'] == task,
                    'Census/source identity or record hash mismatch')
            require(row['id'] not in seen, 'Duplicate source candidate')
            seen.add(row['id'])
            require(row['target_message_index'] == len(row['messages']) - 1
                    and row['messages'][-1]['role'] == 'assistant'
                    and row['admission_authorized'] is True, 'Not an accepted final-target row')
            count += 1
            if selected(flag):
                removed += 1
                evidence = (json.dumps(flag, ensure_ascii=False, sort_keys=True) + '\n').encode()
                if checking:
                    require(excluded.readline() == evidence, 'Exclusion evidence mismatch')
                else:
                    excluded.write(evidence)
            else:
                tokens += row['rendered_tokens']
                if checking:
                    require(retained.readline() == line, 'Subset changed order or record bytes')
                else:
                    retained.write(line)
    require(next(flags, None) is None, 'Census has unmatched rows')
    require((count, removed) == COUNTS[task], 'Census population mismatch')
    if checking:
        require(not retained.read(1) and not excluded.read(1), 'Unexpected extra subset records')
    return count - removed, removed, tokens


def build(root):
    root = Path(root).resolve()
    require(not root.exists(), 'Use a fresh immutable subset root')
    report = census()
    registry = load(REGISTRY)
    root.mkdir(parents=True)
    write_json(root / 'parent-registry.json', registry)
    for task, expected in COUNTS.items():
        info = report['results'][task]
        source = Path(info['published_path'])
        require(file_hash(source) == info['published_sha256'], 'Original export changed')
        entry = next(x for x in registry['additions'] if x.get('hf_repo_id') == info['hf_repo_id'])
        require(entry['output_sha256'] == info['published_sha256']
                and entry['hf_revision'] == info['hf_revision'], 'Registry no longer matches census')
        folder = root / task
        (folder / 'data').mkdir(parents=True)
        output = folder / 'data/train.jsonl'
        with output.open('wb') as kept, (folder / 'exclusions.jsonl').open('wb') as excluded:
            rows, removed, tokens = replay(source, task, kept, excluded)
        parent_manifest = Path(entry['manifest'])
        shutil.copyfile(parent_manifest, folder / 'parent-publication.json')
        shutil.copyfile(source.parent.parent / 'manifest.json', folder / 'parent-export-manifest.json')
        shutil.copyfile(source.parent.parent / 'README.md', folder / 'SOURCE_README.md')
        shutil.copyfile(CENSUS / 'report.json', folder / 'census-report.json')
        shutil.copyfile(CENSUS / 'receipt.json', folder / 'census-receipt.json')
        write_json(folder / 'parent-entry.json', entry)
        receipt = dict(schema=POLICY, task=task, parent_rows=expected[0], excluded_rows=removed,
            retained_rows=rows, parent_output=str(source), parent_output_sha256=file_hash(source),
            parent_hf_revision=info['hf_revision'], hf_repo_id=info['hf_repo_id'],
            census_report_sha256=REPORT_SHA, census_flags_sha256=FLAGS_SHA,
            exclusion_sha256=file_hash(folder / 'exclusions.jsonl'), output_sha256=file_hash(output),
            exact_ordered_byte_subset=True, uncertain_filters_applied=False,
            retained_semantic_certification=False)
        write_json(folder / 'subset-receipt.json', receipt)
        text = (folder / 'SOURCE_README.md').read_text()
        text += (f'\n\n## 2026-10-03 accepted-only structural subset\n\n'
                 f'This revision retains {rows:,} of {expected[0]:,} previously audited accepted rows, '
                 f'excluding exactly {removed:,} rows from the pinned v2 census. '
                 'Messages and per-row source attribution are unchanged. '
                 'Only category-only/heading-only windows and certain reordering windows with '
                 'fewer than two prose blocks are removed. Uncertain and empty-field flags '
                 'are not exclusion criteria. Retention is not semantic certification.\n\n'
                 f'Previous dataset revision: `{info["hf_revision"]}`. '
                 'See `subset-receipt.json`, `exclusions.jsonl`, `census-report.json`, '
                 '`parent-publication.json` and `SOURCE_README.md` for provenance, '
                 'original license terms and attribution. No original publication was deleted.\n')
        (folder / 'README.md').write_text(text)
        manifest = copy.deepcopy(load(parent_manifest))
        manifest.update(rows=rows, rendered_tokens=tokens, output=str(output),
            output_sha256=file_hash(output), counts=dict(accepted=rows, excluded_by_subset=removed,
            parent_accepted=expected[0]), uploaded=False, status='subset_prepared',
            tokenization_performed=False, subset_policy=POLICY,
            subset_receipt=str(folder / 'subset-receipt.json'),
            subset_receipt_sha256=file_hash(folder / 'subset-receipt.json'),
            parent_hf_revision=info['hf_revision'])
        manifest.pop('hf_revision', None)
        manifest['files'] = {str(p.relative_to(folder)): file_hash(p)
                             for p in sorted(folder.rglob('*')) if p.is_file()}
        write_json(folder / 'manifest.json', manifest)
        print(task, rows, removed, tokens, flush=True)
    return root


def verify_package(folder):
    folder = Path(folder).resolve()
    census()
    manifest = load(folder / 'manifest.json')
    require(manifest['subset_policy'] == POLICY, 'Unknown subset policy')
    task = manifest['task']
    require(task in COUNTS, 'Unknown subset task')
    mandatory = {'data/train.jsonl', 'exclusions.jsonl', 'subset-receipt.json',
                 'parent-publication.json', 'parent-export-manifest.json', 'parent-entry.json',
                 'SOURCE_README.md', 'README.md', 'census-report.json', 'census-receipt.json'}
    require(set(manifest['files']) == mandatory, 'Missing subset attachments')
    for relative, sha in manifest['files'].items():
        path = (folder / relative).resolve()
        require(path.is_relative_to(folder) and file_hash(path) == sha, 'Subset attachment mismatch')
    receipt = load(folder / 'subset-receipt.json')
    parent = load(folder / 'parent-entry.json')
    parent_publication = load(folder / 'parent-publication.json')
    info = load(CENSUS / 'report.json')['results'][task]
    require(receipt['census_flags_sha256'] == FLAGS_SHA
            and receipt['census_report_sha256'] == REPORT_SHA, 'Receipt census pin mismatch')
    require(parent['hf_repo_id'] == manifest['hf_repo_id'] == info['hf_repo_id']
            and parent['hf_revision'] == receipt['parent_hf_revision'] == info['hf_revision'],
            'Parent publication identity mismatch')
    for field in ('name', 'repo_id', 'revision', 'license', 'input_sha256', 'task', 'target_policy'):
        require(manifest[field] == parent[field] == parent_publication[field],
                'Subset changed source provenance: ' + field)
    require(file_hash(info['published_path']) == receipt['parent_output_sha256']
            == info['published_sha256'] == parent['output_sha256'], 'Parent bytes changed')
    require(file_hash(folder / 'subset-receipt.json') == manifest['subset_receipt_sha256'],
            'Subset receipt pin mismatch')
    require(Path(manifest['output']).resolve() == folder / 'data/train.jsonl'
            and Path(manifest['subset_receipt']).resolve() == folder / 'subset-receipt.json',
            'Subset output path mismatch')
    with (folder / 'data/train.jsonl').open('rb') as kept, (folder / 'exclusions.jsonl').open('rb') as excluded:
        rows, removed, tokens = replay(info['published_path'], task, kept, excluded, checking=True)
    require(rows == manifest['rows'] == receipt['retained_rows']
            and removed == receipt['excluded_rows'] and tokens == manifest['rendered_tokens'],
            'Subset counts mismatch')
    require(file_hash(folder / 'data/train.jsonl') == manifest['output_sha256'] == receipt['output_sha256']
            and file_hash(folder / 'exclusions.jsonl') == receipt['exclusion_sha256'], 'Subset hash mismatch')
    return manifest


def tokenize(folder, *, verifier=None, token_root=None):
    from scripts.tokenize_wave_releases import prepare, TOKENIZER, TEMPLATE
    entry = (verifier or verify_package)(folder)
    pins = dict(source_sha256=entry['output_sha256'], tokenizer_sha256=file_hash(TOKENIZER),
                template_sha256=file_hash(TEMPLATE))
    target = (token_root or TOKEN_ROOT).resolve() / entry['name'] / digest(pins)
    receipt = target / 'verified.json'
    with lock(target / '.lock'):
        if receipt.exists():
            result = load(receipt)
            require(result['pins'] == pins, 'Token receipt changed')
            require(result['rows'] == entry['rows'] and result['array_hashes'], 'Incomplete token receipt')
            for relative, sha in result['array_hashes'].items():
                require(file_hash(Path(result['output']) / relative) == sha, 'Token array changed')
            return result
        stage, output = target / 'input', target / 'tokens'
        require(not output.exists(), 'Incomplete tokenization: choose a fresh root; no overwrite')
        prepare(entry, stage)
        subprocess.run([sys.executable, 'scripts/tokenize_chat_template.py', str(stage),
            '-o', str(output), '--tokenizer-path', str(TOKENIZER), '--chat-template', str(TEMPLATE),
            '--workers', '16', '--max-seq-len', '4096'], check=True)
        summary = load(output / 'completion.json')
        require(summary['rows'] == entry['rows'] and not summary['skipped_rows_this_run'],
                'Tokenization dropped rows')
        count = tokens = 0
        for part in sorted(output.glob('part-*.jsonl')):
            arrays = {k: np.load(part / (k + '.npy'), mmap_mode='r') for k in
                      ('tokens', 'inst_start', 'inst_len', 'resp_start', 'resp_len')}
            n = len(arrays['resp_len'])
            require(all(len(arrays[k]) == n for k in ('inst_start', 'inst_len', 'resp_start')),
                    'Token array shape mismatch')
            lengths = arrays['inst_len'] + arrays['resp_len']
            require(np.all(lengths <= 4096) and int(lengths.sum()) == len(arrays['tokens']),
                    'Token lengths mismatch')
            count += n
            tokens += len(arrays['tokens'])
        require(count == entry['rows'], 'Materialized token rows mismatch')
        result = dict(pins=pins, rows=count, tokens=tokens, output=str(output),
                      array_hashes={str(p.relative_to(output)): file_hash(p)
                                    for p in sorted(output.rglob('*.npy'))})
        write_json(receipt, result)
        return result


def publish(root, *, backend=None, commit_message='Apply pinned 7086-row minimal FA structural subset'):
    from huggingface_hub import HfApi, hf_hub_download
    root = Path(root).resolve()
    api = HfApi()
    backend = backend or sys.modules[__name__]
    entries = []
    for task in backend.COUNTS:
        folder = root / task
        manifest = backend.verify_package(folder)
        parent = load(folder / 'parent-entry.json')
        tokenized = backend.tokenize(folder)
        publication_path = root / (task + '.publication.json')
        upload_path = root / (task + '.upload.json')
        if publication_path.exists():
            publication = load(publication_path)
            require(publication['export_manifest_sha256'] == file_hash(folder / 'manifest.json'),
                    'Existing publication changed')
        elif upload_path.exists():
            publication = load(upload_path)
            require(publication['export_manifest_sha256'] == file_hash(folder / 'manifest.json'),
                    'Unverified upload manifest changed')
        else:
            current = api.repo_info(manifest['hf_repo_id'], repo_type='dataset').sha
            require(current == parent['hf_revision'], 'Remote repo changed; do not overwrite')
            result = api.upload_folder(repo_id=manifest['hf_repo_id'], repo_type='dataset',
                folder_path=str(folder), allow_patterns=list(manifest['files']) + ['manifest.json'],
                parent_commit=current, commit_message=commit_message)
            publication = dict(manifest, uploaded=True, status='accepted_uploaded',
                publication_status='uploaded_pending_verification', hf_revision=result.oid,
                export_manifest=str(folder / 'manifest.json'),
                export_manifest_sha256=file_hash(folder / 'manifest.json'))
            write_json(upload_path, publication)
        attachments = dict(manifest['files'], **{'manifest.json': file_hash(folder / 'manifest.json')})
        for relative, sha in attachments.items():
            downloaded = hf_hub_download(manifest['hf_repo_id'], relative, repo_type='dataset',
                                          revision=publication['hf_revision'])
            require(file_hash(downloaded) == sha, 'Remote attachment hash mismatch: ' + relative)
        publication['remote_verified_files'] = attachments
        publication['publication_status'] = 'verified'
        write_json(publication_path, publication)
        entry = dict(parent, **publication)
        token_receipt = Path(tokenized['output']).parent / 'verified.json'
        entry.update(manifest=str(publication_path), manifest_sha256=file_hash(publication_path),
                     tokenization_performed=True, tokenized_path=tokenized['output'],
                     tokenized_rows=tokenized['rows'], tokenized_tokens=tokenized['tokens'],
                     tokenization_receipt=str(token_receipt), tokenization_receipt_sha256=file_hash(token_receipt))
        if hasattr(backend, 'prepare_entry'):
            entry = backend.prepare_entry(entry)
        entries.append(entry)
    from scripts import assemble_dfm13_additions as assembler
    verifications = []
    for entry in entries:
        pins = {}
        original = load(root / entry['task'] / 'parent-entry.json')
        contract_path = original.get('tokenized_path') or entry['tokenized_path']
        contract = assembler.token_contract(load(Path(contract_path) / 'tokenizer_info.json'), pins)
        verified = assembler.verify_entry(entry, contract, pins)
        verifications.append(dict(verified=verified, pins=pins))
    write_json(root / 'assembly-verification.json', dict(entries=verifications))
    backend.promote_registry(root, entries)
    write_json(root / 'completion.json', dict(status='accepted_uploaded', policy=backend.POLICY,
        excluded_rows=sum(backend.COUNTS[e['task']][1] for e in entries),
        retained_rows=sum(e['rows'] for e in entries), entries=entries,
        assembly_verification_sha256=file_hash(root / 'assembly-verification.json'),
        historical_exports_and_token_arrays_preserved=True))
    return entries


def promote_registry(root, entries):
    with lock(REGISTRY.with_suffix('.lock')):
        registry = load(REGISTRY)
        for entry in entries:
            index = next(i for i, x in enumerate(registry['additions']) if x['name'] == entry['name'])
            current = registry['additions'][index]
            parent = load(Path(root) / entry['task'] / 'parent-entry.json')
            require(current == parent or current == entry, 'Registry changed; preserve concurrent policies')
            registry['additions'][index] = entry
        write_json(REGISTRY, registry)


def verify_assembly_publication(entry, source, pins, api, *, verifier=None):
    """Scoped adapter, retaining the assembler's ordinary row/token checks."""
    folder = source.parent.parent
    export = (verifier or verify_package)(folder)
    api.pin(folder / 'manifest.json', pins, entry['export_manifest_sha256'])
    publication = api.read_json(entry['manifest'], pins, entry['manifest_sha256'])
    for field in ('subset_policy', 'subset_receipt', 'subset_receipt_sha256', 'files',
                  'parent_hf_revision', 'counts'):
        require(entry[field] == publication[field] == export[field], 'Subset publication mismatch: ' + field)
    require(entry['publication_status'] == publication['publication_status'] == 'verified',
            'Subset remote verification missing')
    expected = dict(export['files'], **{'manifest.json': entry['export_manifest_sha256']})
    require(publication['remote_verified_files'] == expected, 'Subset remote attachments incomplete')
    for relative, sha in export['files'].items():
        api.pin(folder / relative, pins, sha)
    return publication, export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'verify', 'tokenize', 'publish'])
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    with lock(args.root.parent / (args.root.name + '.lock')):
        if args.command == 'build':
            build(args.root)
        elif args.command == 'publish':
            publish(args.root)
        else:
            for task in COUNTS:
                result = (verify_package if args.command == 'verify' else tokenize)(args.root / task)
                print(task, result.get('rows'), result.get('tokens'), flush=True)


if __name__ == '__main__':
    main()
