"""Publish completed, independently audited single-source instruction components."""
import argparse
import json
import re
from pathlib import Path
import sqlite3
from functools import lru_cache

from .io import atomic, file_hash, load, lock, write_json
from .records import validate_messages
from .wave_publication_holds import require_publication_allowed


@lru_cache(maxsize=2)
def farsinstruct_attribution(relative_file):
    import pyarrow.parquet as pq
    base=Path('data/dfm13/wave4/downloads/ParsiAI--FarsInstruct').resolve()
    path=(base/relative_file).resolve()
    if not path.is_relative_to(base):
        raise ValueError('Invalid source path')
    return pq.read_table(path,columns=['dataset','template']).to_pydict()


TRANSFORM_TASKS = {'denoising', 'prefix-continuation', 'span-filling', 'paragraph-reordering'}
BALTIC_RELEASE_COMPONENTS = {'baltic_lt_aya', 'baltic_lt_qa', 'baltic_lv_qa', 'baltic-euroblocks'}
BALTIC_TRANSFORM_COMPONENTS = {'transform-' + name for name in
    ('Wikipedia_lt', 'Wikipedia_lv', 'parlamint_lt', 'parlamint_lv')}


@lru_cache(maxsize=8)
def baltic_transform_pin(root, component):
    name = component.removeprefix('transform-')
    if component not in BALTIC_TRANSFORM_COMPONENTS:
        raise ValueError('Unreviewed Baltic transformation source')
    if name.startswith('Wikipedia_'):
        receipt = root / 'local-sources.json'
        entry = next(x for x in load(receipt) if x['name'] == name)
        path = Path(entry['path'])
        result = dict(repo='wikimedia/wikipedia', revision=entry['revision'],
                      license=['cc-by-sa-3.0', 'gfdl'], source_receipt_sha256=file_hash(receipt))
    else:
        receipt = root / 'parlamint' / name.rsplit('_', 1)[1] / 'receipt.json'
        entry = load(receipt)
        path = receipt.parent / 'documents.jsonl'
        if entry['license'] != 'CC-BY-4.0':
            raise ValueError('Unexpected ParlaMint terms')
        result = dict(repo=entry['url'], revision=entry['version'], license='cc-by-4.0',
                      archive_sha256=entry['archive_sha256'], source_receipt_sha256=file_hash(receipt))
    if file_hash(path) != entry['sha256']:
        raise ValueError('Baltic transformation source changed')
    return dict(result, file=str(path.resolve()), file_sha256=entry['sha256'])


def source_attribution(root, component, source, task):
    source = dict(source)
    if root.name == 'baltic':
        import yaml
        if component == 'baltic-euroblocks' and task == 'instruction':
            base = Path('data/dfm12/european-expansion-20260926')
            pin = load(base / 'sources.lock.json')['sources']['euroblocks']
            if (source['repo'], source['revision']) != (pin['repo'], pin['revision']):
                raise ValueError('Baltic EuroBlocks source pin mismatch')
            if source['file'] not in pin['files'] or source.get('split') != 'train':
                raise ValueError('Baltic EuroBlocks file/split mismatch')
            card_root = Path('data/dfm13/wave4/downloads/utter-project--EuroBlocks-SFT-2512')
            card_pin = load(card_root / 'wave4-download.json')
            if (card_pin['repo'], card_pin['revision']) != (pin['repo'], pin['revision']):
                raise ValueError('EuroBlocks source card revision mismatch')
            card = card_root / 'README.md'
            source['license'] = yaml.safe_load(card.read_text().split('---', 2)[1]).get('license')
            source['license_card_sha256'] = file_hash(card)
            return source
        if component in BALTIC_TRANSFORM_COMPONENTS and task in TRANSFORM_TASKS:
            pin = baltic_transform_pin(root, component)
            if (source['source'] != component.removeprefix('transform-')
                    or Path(source['file']).resolve() != Path(pin['file'])
                    or source['file_sha256'] != pin['file_sha256']):
                raise ValueError('Baltic transformation row provenance mismatch')
            return dict(source, **pin)
        if component not in BALTIC_RELEASE_COMPONENTS or task != 'instruction':
            raise ValueError('Baltic component requires separate source-hold review')
        pin = load(root / 'receipts' / (component + '.json'))
        if (source['repo'], source['revision']) != (pin['repo'], pin['revision']):
            raise ValueError('Baltic source pin mismatch')
        card = root / 'downloads' / component / 'README.md'
        expected = next(f['sha256'] for f in pin['files'] if Path(f['path']).name == 'README.md')
        if file_hash(card) != expected:
            raise ValueError('Pinned Baltic source card changed')
        content = card.read_text()
        if not content.startswith('---\n'):
            raise ValueError('Missing Baltic source-card metadata')
        metadata = yaml.safe_load(content.split('---', 2)[1])
        source['license'] = metadata.get('license')
        if component == 'baltic_lt_qa' and source['license'] is None:
            declaration = metadata.get('dataset', {}).get('usage_and_licensing', {}).get('licensing_information', '')
            if 'International (CC BY 4.0) license' not in declaration:
                raise ValueError('Lithuanian QA nested license declaration changed')
            source['license'] = 'cc-by-4.0'
        source['license_card_sha256'] = expected
    elif task in TRANSFORM_TASKS:
        import yaml
        directory = root / 'downloads' / component
        pin = load(directory / 'wave4-download.json')
        if (source['repo'], source['revision']) != (pin['repo'], pin['revision']):
            raise ValueError('Transformation source pin mismatch')
        card = (directory / 'README.md').read_text()
        if not card.startswith('---\n'):
            raise ValueError('Missing pinned source-card metadata')
        metadata = yaml.safe_load(card.split('---', 2)[1])
        source['license'] = metadata['license']
        source['license_card_sha256'] = file_hash(directory / 'README.md')
    return source


def release(root, component, upload=False, task=None):
    if component in {'wikipedia-sl', 'wikipedia-sq'} and task in {'prefix-continuation', 'paragraph-reordering'}:
        raise ValueError('Exact reviewed-ID successor required; old finalizer must not overwrite corrected revisions')
    if component == 'wikipedia-hr' and task == 'paragraph-reordering':
        raise ValueError('Croatian reordering publication superseded by hr_transform_subset; '
                         'unfiltered finalizer must not overwrite the accepted subset')
    if component == 'wikipedia-fa':
        raise ValueError('Persian Wikipedia publication superseded by fa_transform_subset; '
                         'unfiltered finalizer must not rewrite historical exports or current Hub data')
    require_publication_allowed(component)
    if task is not None and task not in TRANSFORM_TASKS:
        raise ValueError('Unsupported transformation task')
    if root.name == 'baltic' and component not in BALTIC_RELEASE_COMPONENTS | BALTIC_TRANSFORM_COMPONENTS:
        raise ValueError('Baltic component requires separate source-hold review')
    ledger = root / 'release' / component
    with lock(ledger / '.lock'):
        status = load(ledger / 'status.json')
        if not status['export_ready']:
            raise ValueError('Component has unfinished or failed reviews')
        sealed = load(root / 'audit-ready' / component / 'receipt.json')
        if file_hash(sealed['path']) != status['input_sha256']:
            raise ValueError('Sealed input changed')
        suffix = component + ('-' + task if task else '')
        wave = 'wave3' if root.name == 'baltic' else 'wave4'
        folder = Path('exports_dfm13') / (f'dfm13-{wave}-' + re.sub('-+', '-', suffix))
        path = folder / 'data/train.jsonl'
        sources, languages, count, tokens = set(), set(), 0, 0
        license_cache = {}
        with sqlite3.connect(ledger / 'ledger.sqlite') as db, atomic(path) as out:
            counts = dict(db.execute('SELECT status,count(*) FROM rows GROUP BY status'))
            if counts != status['counts']:
                raise ValueError('Ledger changed since completion check')
            for encoded, verdict, review in db.execute(
                    "SELECT record,status,review FROM rows WHERE status IN ('accepted','accepted_repair') ORDER BY id"):
                row = json.loads(encoded)
                if task is not None and row['task'] != task:
                    continue
                if not json.loads(review).get('keep'):
                    raise ValueError('Missing positive review')
                if row['task'] != (task or 'instruction') or row.get('tools') or row.get('reverse_messages'):
                    raise ValueError('This publisher handles plain instruction components only')
                validate_messages(row['messages'])
                if row['messages'][-1]['role'] != 'assistant':
                    raise ValueError('Missing assistant target')
                source = dict(row['provenance'])
                if root.name == 'baltic' and component in BALTIC_TRANSFORM_COMPONENTS:
                    source = source_attribution(root, component, source, task)
                elif task is not None or root.name == 'baltic':
                    pin = (source['repo'], source['revision'])
                    if pin not in license_cache:
                        attributed = source_attribution(root, component, source, task or 'instruction')
                        license_cache[pin] = {k: attributed[k] for k in ('license', 'license_card_sha256')}
                    source.update(license_cache[pin])
                row['provenance'] = source
                if source['repo']=='ParsiAI/FarsInstruct':
                    attribution=farsinstruct_attribution(source['file'])
                    source['underlying_dataset']=attribution['dataset'][source['row']]
                    source['source_template']=attribution['template'][source['row']]
                sources.add((source['repo'], source['revision'], json.dumps(source['license'])))
                languages.add(row['language'])
                row['admission_authorized'] = True
                row['target_message_index'] = len(row['messages']) - 1
                row['quality_status'] = verdict
                row['audit'] = json.loads(review)
                out.write(json.dumps(row, ensure_ascii=False) + '\n')
                count += 1
                tokens += row['rendered_tokens']
        if len(sources) != 1 or not count:
            raise ValueError('Require one nonempty, pinned source')
        source, revision, license_json = next(iter(sources))
        license_id = json.loads(license_json)
        # Missing upstream metadata must not become the invalid literal "None"
        # or an invented grant borrowed from the separately licensed model.
        hf_license = json.dumps(license_id or 'unknown')
        repo = 'schneiderkamplab/' + folder.name
        source_url = source if source.startswith('https://') else f'https://huggingface.co/datasets/{source}'
        receipt = dict(name=folder.name.replace('-', '_'), repo_id=source,
            revision=revision, hf_repo_id=repo, license=license_id, rows=count,
            rendered_tokens=tokens, output=str(path.resolve()), output_sha256=file_hash(path),
            counts=counts, repeat=1, tokenization_performed=False,
            target_policy='final_assistant_only_native_gemma', uploaded=False,
            input_sha256=status['input_sha256'])
        receipt['task'] = task or 'instruction'
        if component == 'wikipedia-sr':
            from .sr_manual_exclusion import publication_evidence
            with sqlite3.connect(ledger / 'ledger.sqlite') as db:
                receipt['attribution_files'] = publication_evidence(db, folder)
        publication = ledger / (task or '') / 'publication.json'
        write_json(folder / 'manifest.json', receipt)
        with atomic(folder / 'README.md') as out:
            out.write(f'---\nlicense: {hf_license}\nlanguage: {json.dumps(sorted(languages))}\n'
                'task_categories:\n- text-generation\nconfigs:\n- config_name: default\n'
                '  data_files:\n  - split: train\n    path: data/train.jsonl\n---\n\n'
                f'# {folder.name}\n\nDerived from [{source}]({source_url}) '
                f'at revision `{revision}`. Source license metadata: {license_id or "not supplied upstream; no additional license grant is asserted"}.\n\n'
                f'{count} accepted training conversations. Every retained conversation passed '
                'Gemma 4 26B A4B automated review; repairs passed a separate fresh-context review. '
                'Automated review is fallible. Rejected and unresolved rows are not included.\n\n'
                'Render structured messages with the native Gemma 4 chat template, thinking disabled. '
                'Supervise target_message_index only. Preserve source attribution and provenance. '
                'No exhaustive benchmark decontamination claim is made.\n')
            if component == 'wikipedia-sr':
                out.write('\nFour exact component-level candidate IDs were excluded by main-agent manual review '
                    'before publication, separately from automated rejection. Original records, model reviews, '
                    'reasons and hash-bound review provenance are preserved in `manual-review-decisions.json`. '
                    'Case45 is retained: meaningful native introduction/cast table/coherent gap; markup alone '
                    'is not an exclusion rule. No language-wide regex or semantic certification is implied.\n')
        if upload:
            from huggingface_hub import HfApi, hf_hub_download
            api = HfApi()
            api.create_repo(repo, repo_type='dataset', exist_ok=True)
            commit = api.upload_folder(repo_id=repo, repo_type='dataset', folder_path=folder,
                allow_patterns=['README.md', 'manifest.json', 'data/train.jsonl'] + list(receipt.get('attribution_files', {}).values()),
                commit_message=f'Publish accepted-only audited {wave} data')
            downloaded = hf_hub_download(repo, 'data/train.jsonl', repo_type='dataset', revision=commit.oid)
            if file_hash(downloaded) != receipt['output_sha256']:
                raise ValueError('Remote content verification failed')
            for expected, relative in receipt.get('attribution_files', {}).items():
                attached = hf_hub_download(repo, relative, repo_type='dataset', revision=commit.oid)
                if file_hash(attached) != expected:
                    raise ValueError('Remote manual review attachment verification failed')
            receipt.update(uploaded=True, hf_revision=commit.oid, status='accepted_uploaded')
            registry = Path('config/dfm13_sources.json')
            with lock(registry.with_suffix('.lock')):
                data = load(registry)
                data['additions'] = [r for r in data['additions'] if r['name'] != receipt['name']]
                data['additions'].append(dict(receipt, manifest=str(publication.resolve())))
                write_json(registry, data)
        write_json(publication, receipt)
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--component', required=True)
    parser.add_argument('--upload', action='store_true')
    parser.add_argument('--task', choices=sorted(TRANSFORM_TASKS))
    args = parser.parse_args()
    release(args.root, args.component, args.upload, args.task)
