"""Scoped NewGenLTU BLKT publication, remote verification and registry integration."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from . import blkt_export as source
from .io import file_hash, load, lock, rows, write_json

PREPARATION_SHA = '068974342030797c40f233a296c81e59072b3f0dffa2dd8c752cde5232b36587'
TASKS = {'denoising': 15019, 'prefix-continuation': 22635, 'span-filling': 10547}
LICENSE_URL = f'https://huggingface.co/datasets/{source.REPO}/blob/{source.REVISION}/LICENSE.txt'
MODEL_CONDITIONS = {
    'license': 'NewGenLTU Open RAIL-D 1.0', 'license_url': LICENSE_URL,
    'mandatory_use_restrictions': 'Section 3 and Attachment A apply to all recipients and derivatives.',
    'permitted_purposes': 'Section 5(v): model training, language technology development, training datasets.',
    'personal_data_extraction': 'Attachment A10(a): artifact may not be used to extract or obtain personal data.',
    'trained_model_privacy': 'Attachment A10(b): trained models must adequately limit output of artifact personal information.',
    'model_outputs': 'Section 4: output use must not contravene the license.',
    'scope': 'Model obligations apply to model training/use; not an additional dataset-publication approval gate.'}


def build(preparation, output):
    preparation, output = Path(preparation).resolve(), Path(output).resolve()
    source.checked(preparation / 'manifest.json', PREPARATION_SHA)
    manifest = load(preparation / 'manifest.json')
    if (manifest['component'] != source.COMPONENT or manifest['accepted_rows'] != sum(TASKS.values())
            or len(manifest['packages']) != len(TASKS)):
        raise ValueError('Unexpected BLKT preparation population')
    if output.exists():
        raise ValueError('Use a fresh publication directory')
    receipt_paths = [Path(x) for x in manifest['inputs'] if x.endswith('/receipts/baltic_lt_blkt.json')]
    if len(receipt_paths) != 1:
        raise ValueError('Missing pinned source receipt')
    receipt = source.checked(receipt_paths[0], source.RECEIPT_SHA)
    card_pin = next(x for x in load(receipt)['files'] if Path(x['path']).name == 'README.md')
    card = source.checked(card_pin['path'], card_pin['sha256'])
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.' + output.name, dir=output.parent))
    packages, seen, tasks = [], set(), set()
    try:
        for package in manifest['packages']:
            task = package['task']
            if (task not in TASKS or task in tasks or package['rows'] != TASKS[task]
                    or package['license_bucket'] != 'newgenltu'
                    or (package['repo'], package['revision']) != (source.REPO, source.REVISION)
                    or package['path'] != task + '--newgenltu'):
                raise ValueError('Unapproved task/license partition')
            tasks.add(task)
            original = preparation / package['path']
            source.checked(original / 'manifest.json', package['manifest_sha256'])
            for name, sha in package['files'].items():
                p = (original / name).resolve()
                if not p.is_relative_to(original):
                    raise ValueError('Unsafe package path')
                source.checked(p, sha)
            source.checked(original / 'LICENSE.txt', source.LICENSE_SHA)
            name = 'dfm13-wave3-transform-baltic-lt-blkt-' + task + '-newgenltu'
            repo = 'schneiderkamplab/' + name
            folder = stage / name
            (folder / 'data').mkdir(parents=True)
            for attachment in ('LICENSE.txt', 'attribution.jsonl', 'NOTICE.txt'):
                shutil.copyfile(original / attachment, folder / attachment)
            shutil.copyfile(card, folder / 'SOURCE_README.md')
            with (folder / 'data/train.jsonl').open('w') as out:
                count = 0
                for row in rows(original / 'data/train.jsonl'):
                    audit = row['export_preparation']
                    if (row['id'] in seen or row['task'] != task or row['language'] != 'lt'
                            or row['provenance']['license'] != 'NewGenLTU OpenRAIL-D'
                            or audit['audit'].get('keep') is not True
                            or audit['quality_status'] not in ('accepted', 'accepted_repair')):
                        raise ValueError('Invalid accepted row')
                    seen.add(row['id'])
                    # A new publication artifact; sealed preparation and messages remain untouched.
                    row.update(admission_authorized=True, audit_status=audit['quality_status'],
                               quality_status=audit['quality_status'], audit=audit['audit'])
                    row['publication_conditions'] = 'USE_CONDITIONS.md and LICENSE.txt'
                    out.write(json.dumps(row, ensure_ascii=False) + '\n')
                    count += 1
            if count != TASKS[task]:
                raise ValueError('Partition count mismatch')
            conditions = ('# Mandatory Downstream Conditions\n\n'
                'This artifact and its derivatives are distributed ONLY under the attached '
                'NewGenLTU Open RAIL-D 1.0 LICENSE.txt in full. Section 3 and every restriction '
                'in Attachment A are conditions precedent to this license and any downstream '
                'use/distribution agreement, not optional guidance. All recipients and users '
                'must comply and pass these conditions, the full license and notices onward. '
                'No broader rights or endorsement are granted.\n\n'
                'Section 5(v) limits purposes to model training, language technology development '
                'and production of model-training datasets. Section 4 governs model output use. '
                'Attachment A10(a) forbids extracting or obtaining personal data; A10(b) requires '
                'adequate limitations on trained models to prevent output of artifact personal '
                'information. These are binding use/model obligations, not a claim that a model '
                'has been assessed by this dataset publication. All other Attachment A terms '
                'remain in force.\n')
            (folder / 'USE_CONDITIONS.md').write_text(conditions)
            with (folder / 'NOTICE.txt').open('a') as f:
                f.write('\nPublication changes data/train.jsonl metadata to authorize accepted rows; '
                        'conversation content is unchanged. Full mandatory terms: LICENSE.txt and '
                        'USE_CONDITIONS.md. attribution.jsonl is derived source metadata.\n')
            (folder / 'README.md').write_text(
                '---\nlicense: other\nlicense_name: newgenltu-openrail-d-1.0\n'
                f'license_link: {LICENSE_URL}\nlanguage:\n- lt\n'
                'task_categories:\n- text-generation\nconfigs:\n- config_name: default\n'
                '  data_files:\n  - split: train\n    path: data/train.jsonl\n---\n\n'
                f'# BLKT {task}\n\n{count} accepted conversations from '
                f'[{source.REPO}](https://huggingface.co/datasets/{source.REPO}/tree/{source.REVISION}). '
                f'Pinned revision: `{source.REVISION}`.\n\n'
                'MANDATORY: use/distribution is licensed only subject to the full [LICENSE](LICENSE.txt) '
                'and [downstream conditions](USE_CONDITIONS.md), including all Attachment A restrictions. '
                'Redistribute these files and [notices](NOTICE.txt) together.\n\n'
                'Data files are modified derivatives: source-window selection, mechanical task '
                'transformations and automated Gemma review selection; repaired rows, if any, are '
                'identified individually. Automated review is fallible, not certified gold or '
                'exhaustive manual review. No exhaustive decontamination or privacy certification '
                'is asserted. Exact source authors/titles/URLs/IDs are in attribution.jsonl; '
                'upstream missing URLs remain null.\n\n'
                'Preserve native messages and supervise target_message_index only. No truncation '
                'or retokenization was performed. Source preparation hashes are recorded in manifest.json.\n')
            files = {str(p.relative_to(folder)): file_hash(p) for p in folder.rglob('*') if p.is_file()}
            record = dict(name=name.replace('-', '_'), repo_id=source.REPO, revision=source.REVISION,
                hf_repo_id=repo, license='NewGenLTU Open RAIL-D 1.0', task=task, rows=count,
                rendered_tokens=package['rendered_tokens'], repeat=1, files=files,
                output=str(output / name / 'data/train.jsonl'), output_sha256=files['data/train.jsonl'],
                preparation_sha256=PREPARATION_SHA,
                preparation_data_sha256=package['files']['data/train.jsonl'],
                target_policy='final_assistant_only_native_gemma', tokenization_performed=False,
                admission_authorized=True, model_use_conditions=MODEL_CONDITIONS,
                uploaded=False, publisher_sha256=file_hash(__file__))
            write_json(folder / 'manifest.json', record)
            packages.append(dict(path=name, manifest_sha256=file_hash(folder / 'manifest.json')))
        source.checked(preparation / 'manifest.json', PREPARATION_SHA)
        write_json(stage / 'publication.json', dict(packages=packages, preparation_sha256=PREPARATION_SHA))
        stage.rename(output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return load(output / 'publication.json')


def publish(output, registry, api=None, download=None):
    """Only integrate after every attachment at each returned HF commit verifies."""
    if api is None:
        from huggingface_hub import HfApi, hf_hub_download
        api, download = HfApi(), hf_hub_download
    output, registry = Path(output).resolve(), Path(registry)
    with lock(output / '.publish.lock'):
        publication = load(output / 'publication.json')
        expected = {'dfm13-wave3-transform-baltic-lt-blkt-' + task + '-newgenltu' for task in TASKS}
        if (publication.get('preparation_sha256') != PREPARATION_SHA
                or len(publication['packages']) != len(expected)
                or {x['path'] for x in publication['packages']} != expected):
            raise ValueError('Unexpected publication inventory')
        records = []
        for package in publication['packages']:
            folder = output / package['path']
            source.checked(folder / 'manifest.json', package['manifest_sha256'])
            record = load(folder / 'manifest.json')
            if (record['repo_id'] != source.REPO or record['revision'] != source.REVISION
                    or record['preparation_sha256'] != PREPARATION_SHA
                    or record['task'] not in TASKS or record['rows'] != TASKS[record['task']]
                    or record['hf_repo_id'] != 'schneiderkamplab/' + package['path']
                    or record['model_use_conditions'] != MODEL_CONDITIONS):
                raise ValueError('Unexpected publication scope')
            source.checked(folder / 'LICENSE.txt', source.LICENSE_SHA)
            files = dict(record['files'], **{'manifest.json': package['manifest_sha256']})
            for name, sha in files.items():
                source.checked(folder / name, sha)
            api.create_repo(record['hf_repo_id'], repo_type='dataset', exist_ok=True)
            commit = api.upload_folder(repo_id=record['hf_repo_id'], repo_type='dataset',
                folder_path=folder, allow_patterns=list(files),
                commit_message='Publish accepted BLKT with mandatory NewGenLTU terms and attribution')
            for name, sha in files.items():
                remote = download(repo_id=record['hf_repo_id'], filename=name,
                                  repo_type='dataset', revision=commit.oid)
                source.checked(remote, sha)
            record.update(uploaded=True, status='accepted_uploaded', publication_status='verified', hf_revision=commit.oid,
                          export_manifest=str(folder / 'manifest.json'),
                          export_manifest_sha256=package['manifest_sha256'])
            write_json(output / (package['path'] + '.verified.json'), record)
            records.append(record)
        with lock(registry.with_suffix('.lock')):
            config = load(registry)
            names = {r['name'] for r in records}
            config['additions'] = [r for r in config['additions'] if r['name'] not in names] + records
            write_json(registry, config)
        write_json(output / 'integrated.json', dict(records=records, registry=str(registry.resolve()),
                   registry_sha256=file_hash(registry)))
    return records


def repair_registry_status(output, registry):
    """Normalize only verified BLKT statuses; never replace watcher-added fields."""
    output, registry = Path(output).resolve(), Path(registry)
    with lock(output / '.publish.lock'), lock(registry.with_suffix('.lock')):
        config = load(registry)
        expected = {'dfm13_wave3_transform_baltic_lt_blkt_' + t.replace('-', '_') + '_newgenltu'
                    for t in TASKS}
        entries = [r for r in config['additions'] if r['name'] in expected]
        if len(entries) != len(expected) or {r['name'] for r in entries} != expected:
            raise ValueError('Missing or duplicate BLKT registry entries')
        verified = []
        for entry in entries:
            folder = output / entry['name'].replace('_', '-')
            receipt_path = output / (folder.name + '.verified.json')
            receipt = load(receipt_path)
            source.checked(folder / 'manifest.json', entry['export_manifest_sha256'])
            export = load(folder / 'manifest.json')
            if (receipt.get('publication_status') != 'verified' or receipt.get('uploaded') is not True
                    or entry.get('uploaded') is not True or not entry.get('hf_revision')):
                raise ValueError('Unverified BLKT publication')
            for field in ('name', 'hf_repo_id', 'hf_revision', 'output', 'output_sha256',
                          'export_manifest_sha256', 'model_use_conditions'):
                if receipt.get(field) != entry.get(field):
                    raise ValueError('Registry/verified receipt mismatch: ' + field)
            for field in ('name', 'output', 'output_sha256', 'repo_id', 'revision', 'files',
                          'model_use_conditions', 'preparation_sha256'):
                if export.get(field) != entry.get(field):
                    raise ValueError('Registry/export mismatch: ' + field)
            if ((entry['repo_id'], entry['revision']) != (source.REPO, source.REVISION)
                    or entry['model_use_conditions'] != MODEL_CONDITIONS
                    or entry['preparation_sha256'] != PREPARATION_SHA):
                raise ValueError('Wrong BLKT scope')
            for name, sha in export['files'].items():
                path = (folder / name).resolve()
                if not path.is_relative_to(folder):
                    raise ValueError('Unsafe attachment')
                source.checked(path, sha)
            verified.append((entry, receipt_path, receipt))
        for entry, receipt_path, receipt in verified:
            receipt['status'] = 'accepted_uploaded'
            write_json(receipt_path, receipt)
            entry['status'] = 'accepted_uploaded'
        write_json(registry, config)
    return [e['name'] for e, _, _ in verified]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--preparation', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--upload', action='store_true')
    p.add_argument('--registry', type=Path, default=Path('config/dfm13_sources.json'))
    args = p.parse_args()
    if args.preparation:
        build(args.preparation, args.output)
    if args.upload:
        publish(args.output, args.registry)


if __name__ == '__main__':
    main()
