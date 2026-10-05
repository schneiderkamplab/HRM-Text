"""Publish only terminal, rights-separated Latvian P3 partitions."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import time

from . import latvian_p3_export as source
from .io import file_hash, load, lock, write_json
from .jobs import validate_audit
from .prepare import Renderer

LICENSES = ('cc-by-4.0', 'cc-by-sa-4.0')


def folder_name(license_id):
    return 'dfm13-wave3-latvian-p3-' + license_id.replace('.', '-')


def checked(path, sha):
    source.check(file_hash(Path(path)) == sha, f'Publication hash mismatch: {path}')


def safe_file(folder, name):
    path = (folder / name).resolve()
    source.check(path.is_relative_to(folder.resolve()), 'Package file escapes root')
    return path


def build(preparation, output, renderer=None):
    preparation = Path(preparation).resolve(); output = Path(output).resolve()
    source.check(not output.exists(), 'Publication output already exists')
    manifest = load(preparation/'manifest.json'); preparation_sha = file_hash(preparation/'manifest.json')
    source.check(manifest['schema'] == 'dfm13-latvian-p3-rights-preview-v1' and
        manifest['partial'] is False and manifest['unfinished_rows'] == 0, 'Require terminal preparation')
    source.check(set(manifest['packages']) == set(LICENSES), 'Unexpected license inventory')
    for path, sha in manifest['inputs'].items(): checked(path, sha)
    checked(preparation/'ledger-snapshot.jsonl', manifest['ledger_snapshot_sha256'])
    checked(preparation/'dispositions.jsonl', manifest['dispositions_sha256'])
    receipts = [p for p in manifest['inputs'] if p.endswith('/audit-ready/latvian-p3/receipt.json')]
    source.check(len(receipts) == 1, 'Missing sealed input receipt')
    sealed = load(receipts[0])
    for field, sha in (('tokenizer_path', 'tokenizer_sha256'), ('chat_template_path', 'template_sha256')):
        checked(sealed['tokenizer_info'][field], sealed[sha])
    if renderer is None: renderer = Renderer(sealed['tokenizer_info'])
    output.parent.mkdir(parents=True, exist_ok=True)
    packages = []; seen = set()
    with tempfile.TemporaryDirectory(prefix=output.name+'.', dir=output.parent) as tmp:
        stage = Path(tmp)
        for license_id in LICENSES:
            package = manifest['packages'][license_id]; original = preparation/license_id
            source.check(load(original/'manifest.json') == package, 'Preparation package manifest changed')
            for name, sha in package['files'].items(): checked(safe_file(original, name), sha)
            checked(original/'LICENSE.txt', manifest['evidence'][license_id]['sha256'])
            name = folder_name(license_id); folder = stage/name; (folder/'data').mkdir(parents=True)
            for relative in package['files']:
                if relative == 'data/train.jsonl': continue
                dest = folder/relative; dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original/relative, dest)
            counts = {}; tokens = rows = 0
            with (original/'data/train.jsonl').open() as incoming, (folder/'data/train.jsonl').open('w') as outgoing:
                for line in incoming:
                    row = json.loads(line); family = source.rights_family(row)
                    source.check(source.GRANTS.get(family, (None,))[0] == license_id, 'Held/wrong-license constituent')
                    source.check(row['id'] not in seen and row['quality_status'] in ('accepted', 'accepted_repair'), 'Duplicate/unaccepted row')
                    seen.add(row['id']); validate_audit(row['audit'])
                    source.check(row['audit']['keep'] is True and row['target_message_index'] == len(row['messages'])-1,
                                 'Wrong audit/target')
                    count = renderer.count(row['messages'])
                    source.check(count == row['rendered_tokens'], 'Native render count changed')
                    row['admission_authorized'] = True
                    row['publication_license'] = license_id
                    outgoing.write(json.dumps(row, ensure_ascii=False)+'\n')
                    rows += 1; tokens += count; counts[family] = counts.get(family, 0)+1
            source.check(rows == package['rows'] and rows > 0, 'Empty/count-mismatched partition')
            with (folder/'NOTICE.txt').open('a') as notice:
                notice.write('\nPublication supersession: the preview-only admission notice above describes the '
                    'preparation artifact. This new publication is authorized by the project owner; only metadata '
                    'changes, no conversation text changes. No additional license restrictions are imposed.\n')
            (folder/'README.md').write_text(
                f'---\nlicense: {license_id}\nlanguage:\n- lv\ntask_categories:\n- text-generation\n'
                'configs:\n- config_name: default\n  data_files:\n  - split: train\n    path: data/train.jsonl\n---\n\n'
                f'# Latvian P3: {license_id}\n\n{rows} accepted conversations, grouped by verified constituent terms. '
                f'Constituent counts: {json.dumps(counts, sort_keys=True)}.\n\n'
                f'Translated source: [{source.P3_REPO}](https://huggingface.co/datasets/{source.P3_REPO}/tree/{source.P3_REVISION}). '
                'Per-row provenance preserves constituent, source file hash/ordinal, train membership and repair lineage. '
                'See LICENSE.txt, NOTICE.txt and evidence/ for full terms, primary notices and attribution. '
                'ARC adaptations are ShareAlike; no blanket license is asserted for other P3 constituents.\n\n'
                'MRPC, WikiQA, OpenBookQA and QuaRel are excluded. Unaccepted rows are excluded. '
                'Automated quality review and separate repair re-audit are fallible, not native/human gold. '
                'No exhaustive benchmark decontamination claim is made. Preserve native messages and supervise '
                'target_message_index only, with thinking disabled. No conversation truncation was performed.\n')
            files = {str(p.relative_to(folder)): file_hash(p) for p in sorted(folder.rglob('*')) if p.is_file()}
            record = dict(name=name.replace('-', '_'), repo_id=source.P3_REPO, revision=source.P3_REVISION,
                hf_repo_id='schneiderkamplab/'+name, license=license_id, task='instruction', rows=rows,
                rendered_tokens=tokens, rendered_tokens_basis='all_assistant_targets_with_repeated_prefixes',
                output=str(output/name/'data/train.jsonl'), output_sha256=files['data/train.jsonl'],
                input_sha256=sealed['sha256'], preparation_sha256=preparation_sha, families=counts,
                repeat=1, target_policy='final_assistant_only_native_gemma', tokenization_performed=False,
                uploaded=False, files=files, attribution_files={sha: p for p, sha in files.items() if p != 'data/train.jsonl'},
                publisher_sha256=file_hash(__file__), exporter_sha256=file_hash(source.__file__))
            write_json(folder/'manifest.json', record)
            packages.append(dict(path=name, manifest_sha256=file_hash(folder/'manifest.json')))
        checked(preparation/'manifest.json', preparation_sha)
        write_json(stage/'publication.json', dict(packages=packages, preparation=str(preparation),
            preparation_sha256=preparation_sha, held_constituents=source.HOLDS,
            held_counts={k:v for k,v in manifest['counts'].items() if not k.startswith('prepared:')}))
        stage.rename(output)
    return load(output/'publication.json')


def publish(output, registry, api=None, download=None):
    if api is None:
        from huggingface_hub import HfApi, hf_hub_download
        api, download = HfApi(), hf_hub_download
    output = Path(output).resolve(); registry = Path(registry).resolve()
    with lock(output/'.publish.lock'):
        publication = load(output/'publication.json')
        expected = {folder_name(x) for x in LICENSES}
        source.check(len(publication['packages']) == 2 and {p['path'] for p in publication['packages']} == expected,
                     'Unexpected publication inventory')
        records = []
        for item in publication['packages']:
            folder = output/item['path']; checked(folder/'manifest.json', item['manifest_sha256'])
            record = load(folder/'manifest.json'); license_id = record['license']
            source.check(license_id in LICENSES and item['path'] == folder_name(license_id)
                and record['hf_repo_id'] == 'schneiderkamplab/'+item['path']
                and record['repo_id'] == source.P3_REPO and record['revision'] == source.P3_REVISION,
                'Unexpected publication source/license')
            files = dict(record['files'], **{'manifest.json':item['manifest_sha256']})
            for name, sha in files.items(): checked(safe_file(folder, name), sha)
            receipt_path = output/(item['path']+'.verified.json')
            if receipt_path.exists():
                previous = load(receipt_path)
                source.check(previous['export_manifest_sha256'] == item['manifest_sha256'], 'Publication receipt changed')
                revision = previous['hf_revision']
            else:
                api.create_repo(record['hf_repo_id'], repo_type='dataset', exist_ok=True)
                revision = api.upload_folder(repo_id=record['hf_repo_id'], repo_type='dataset',
                    folder_path=folder, allow_patterns=list(files),
                    commit_message='Publish terminal audited Latvian P3 with separated constituent licenses').oid
            for name, sha in files.items():
                remote = download(repo_id=record['hf_repo_id'], filename=name, repo_type='dataset',
                    revision=revision, force_download=True)
                checked(remote, sha)
            record.update(uploaded=True, status='accepted_uploaded', publication_status='verified', hf_revision=revision,
                export_manifest=str(folder/'manifest.json'), export_manifest_sha256=item['manifest_sha256'],
                manifest=str(receipt_path), remote_verified_files=files)
            write_json(receipt_path, record); records.append(record)
        # Both license packages must verify before either becomes tokenization-eligible.
        deadline = time.monotonic()+120
        while True:
            try:
                with lock(registry.with_suffix('.lock')):
                    config = load(registry); names = {r['name'] for r in records}
                    for old in config['additions']:
                        if old['name'] not in names: continue
                        source.check(old.get('status') != 'quality_hold_source_fidelity',
                                     'Source-quality hold cannot be cleared by republishing')
                        new = next(r for r in records if r['name'] == old['name'])
                        source.check(old['output_sha256'] == new['output_sha256'] and old['hf_revision'] == new['hf_revision'],
                                     'Registry collision with different publication')
                        # Preserve completed tokenization if this idempotent integration is repeated.
                        for key, value in old.items():
                            if key.startswith(('tokenized_', 'tokenization_')): new[key] = value
                    config['additions'] = [r for r in config['additions'] if r['name'] not in names]+records
                    write_json(registry, config)
                break
            except BlockingIOError:
                source.check(time.monotonic() < deadline, 'Registry lock timeout')
                time.sleep(1)
        write_json(output/'integrated.json', dict(records=records, registry=str(registry),
            registry_sha256=file_hash(registry), held_constituents=source.HOLDS))
    return records


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/dfm13/baltic'))
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence-manifest', type=Path, required=True)
    parser.add_argument('--change-date', required=True)
    parser.add_argument('--registry', type=Path, default=Path('config/dfm13_sources.json'))
    parser.add_argument('--wait-terminal', action='store_true')
    parser.add_argument('--upload', action='store_true')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with lock(args.output.parent/(args.output.name+'.runner.lock')):
        if not args.preparation.exists():
            if args.wait_terminal: source.wait_for_quality(args.root)
            source.export(args.root, args.preparation, args.evidence_manifest, args.change_date)
        if not args.output.exists(): build(args.preparation, args.output)
        result = publish(args.output, args.registry) if args.upload else load(args.output/'publication.json')
        print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
