"""Revision-guarded replacement of owned XXL-wide identity packages only."""
from pathlib import Path
import time

from huggingface_hub import HfApi, CommitOperationAdd, CommitOperationDelete, hf_hub_download
from huggingface_hub.errors import RepositoryNotFoundError

from .export_validator import validate
from .io import file_hash, load, lock, write_json
from .identity_multilingual_queue import LANGUAGES


def publish(root, only=None):
    root = Path(root)
    api = HfApi()
    api.whoami()
    prior = load('exports_dfm12/identity-xxl-wide/metadata/upload-receipts.json')
    with lock(root / '.publish.lock'):
        receipt_path = root / 'metadata/upload-receipts.json'
        receipts = load(receipt_path) if receipt_path.exists() else {}
        packages = load(root / 'manifest.json')['packages']
        expected_names = {'dfm12-identity-xxl-wide-full-bp-' + lang for lang in LANGUAGES}
        if {p['name'] for p in packages} != expected_names or len(packages) != 21:
            raise ValueError('Expected exactly the 21 authorized identity repositories')
        if only is not None:
            if only not in expected_names:
                raise ValueError('Unknown identity package selection')
            packages = [p for p in packages if p['name'] == only]
        for entry in packages:
            folder = root / entry['name']
            validate(folder)
            repo = 'schneiderkamplab/' + entry['name']
            sha = file_hash(folder / 'metadata/manifest.json')
            saved = receipts.get(repo)
            if saved and saved['manifest_sha256'] != sha:
                raise ValueError('Published package changed locally')
            if saved and saved['status'] == 'verified':
                continue
            try:
                info = api.repo_info(repo, repo_type='dataset')
            except RepositoryNotFoundError:
                info = None
            if info and not saved:
                owned = prior.get(repo)
                if not owned or owned['status'] != 'verified' or info.sha != owned['revision']:
                    raise ValueError('Unowned or concurrently changed repository: ' + repo)
            manifest = load(folder / 'metadata/manifest.json')
            files = {x['file'] for x in manifest['data_files'] + manifest['metadata_files']}
            files.update({'README.md', 'metadata/manifest.json', 'validate_dataset.py'})
            if not saved:
                saved = dict(status='prepared', manifest_sha256=sha, rows=entry['rows'],
                             previous_revision=info.sha if info else None, started=time.time())
                receipts[repo] = saved
                write_json(receipt_path, receipts)
            if saved['status'] != 'committed':
                if info and saved['previous_revision'] and info.sha != saved['previous_revision']:
                    raise ValueError('Remote changed since preparation: ' + repo)
                api.create_repo(repo, repo_type='dataset', private=False, exist_ok=True)
                parent = api.repo_info(repo, repo_type='dataset').sha
                remote = set(api.list_repo_files(repo, repo_type='dataset', revision=parent))
                operations = [CommitOperationAdd(path_in_repo=n, path_or_fileobj=str(folder / n)) for n in sorted(files)]
                operations.extend(CommitOperationDelete(path_in_repo=n) for n in sorted(remote - files - {'.gitattributes'}))
                commit = api.create_commit(repo, repo_type='dataset', parent_commit=parent,
                    operations=operations, commit_message='Expand audited XXL-wide identity to complete 21-language source corpus')
                saved.update(status='committed', revision=commit.oid)
                write_json(receipt_path, receipts)
            revision = saved['revision']
            if set(api.list_repo_files(repo, repo_type='dataset', revision=revision)) - {'.gitattributes'} != files:
                raise ValueError('Remote inventory mismatch')
            for name in sorted(files):
                remote_path = hf_hub_download(repo, name, repo_type='dataset', revision=revision)
                if file_hash(remote_path) != file_hash(folder / name):
                    raise ValueError('Remote hash mismatch: ' + name)
            saved.update(status='verified', completed=time.time(), public=True)
            write_json(receipt_path, receipts)
            print('VERIFIED', repo, entry['rows'], revision, flush=True)
