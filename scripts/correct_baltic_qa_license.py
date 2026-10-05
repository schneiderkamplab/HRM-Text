"""Correct nested source-license metadata without rewriting released examples."""
from pathlib import Path

import yaml
from huggingface_hub import HfApi, hf_hub_download

from dfm12.io import atomic, file_hash, load, lock, write_json
from dfm12.wave_release import source_attribution


def main():
    root = Path('data/dfm13/baltic')
    component = 'baltic_lt_qa'
    ledger = root / 'release' / component
    with lock(ledger / '.lock'):
        receipt_path = ledger / 'publication.json'
        receipt = load(receipt_path)
        if receipt['license'] == 'cc-by-4.0' and receipt.get('license_metadata_corrected'):
            return
        source = source_attribution(root, component,
            dict(repo=receipt['repo_id'], revision=receipt['revision']), 'instruction')
        assert source['license'] == 'cc-by-4.0'
        data = Path(receipt['output'])
        if file_hash(data) != receipt['output_sha256']:
            raise ValueError('Released data changed')
        folder = data.parent.parent
        card = folder / 'README.md'
        _, front, body = card.read_text().split('---', 2)
        metadata = yaml.safe_load(front)
        metadata['license'] = 'cc-by-4.0'
        body = body.replace('Source license metadata: not supplied upstream; no additional license grant is asserted.',
                            'Source license metadata: CC BY 4.0 (nested declaration in the pinned upstream card).')
        with atomic(card) as out:
            out.write('---\n' + yaml.safe_dump(metadata, sort_keys=False) + '---' + body)
            out.write('\nLicense metadata corrected without changing training rows. The upstream author is '
                      'Neurotechnology (curator Arturas Nakvosas). Original row-level null license fields '
                      'reflect the earlier parser omission; this card records the pinned source declaration.\n')
        receipt.update(license='cc-by-4.0', license_metadata_corrected=True,
                       license_source_card_sha256=source['license_card_sha256'])
        write_json(folder / 'manifest.json', receipt)
        commit = HfApi().upload_folder(repo_id=receipt['hf_repo_id'], repo_type='dataset',
            folder_path=folder, allow_patterns=['README.md', 'manifest.json'],
            commit_message='Correct nested CC BY 4.0 source metadata; training data unchanged')
        for name in ('README.md', 'manifest.json', 'data/train.jsonl'):
            remote = hf_hub_download(receipt['hf_repo_id'], name, repo_type='dataset', revision=commit.oid)
            if file_hash(remote) != file_hash(folder / name):
                raise ValueError('Remote metadata/data verification failed')
        receipt['hf_revision'] = commit.oid
        registry = Path('config/dfm13_sources.json')
        with lock(registry.with_suffix('.lock')):
            state = load(registry)
            entry = next(x for x in state['additions'] if x['name'] == receipt['name'])
            if entry['output_sha256'] != receipt['output_sha256']:
                raise ValueError('Registry data changed')
            entry.update(license=receipt['license'], hf_revision=commit.oid,
                         license_metadata_corrected=True,
                         license_source_card_sha256=source['license_card_sha256'])
            write_json(registry, state)
        write_json(receipt_path, receipt)
        print(commit.oid, 'data unchanged', receipt['output_sha256'], flush=True)


if __name__ == '__main__':
    main()
