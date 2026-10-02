"""Publish verified multilingual packages without altering their sealed contents."""
import argparse
import gzip
import json
from pathlib import Path
import time

from .catalog import selected_source
from .export_multilingual_completed import ALL_LANGUAGES, language_target
from .io import file_hash, load, lock, write_json

NAMESPACE = 'schneiderkamplab'
AUTHORIZATION = ('2026-09-29 explicit user authorization: export/upload all 19 completed '
                 'multilingual campaign packages; supersedes historical local-only export policy.')


def validated_packages(root):
    root = Path(root)
    manifest, verification = load(root/'manifest.json'), load(root/'verification.json')
    completion = load(root/'completion.json')
    if (verification['manifest_sha256'] != file_hash(root/'manifest.json') or
        verification['completion_sha256'] != file_hash(root/'completion.json') or
        verification.get('all_package_hashes_verified') is not True or
        verification.get('all_training_audit_pairs_verified') is not True):
        raise ValueError('Unverified or changed export root')
    checked = {p['language']:p for p in verification['packages']}
    packages = manifest['packages']
    if len(checked) != len(packages) or completion['packages'] != len(packages):
        raise ValueError('Verification package mismatch')
    if completion['rows'] != verification['rows'] or completion['rows'] != sum(p['rows'] for p in packages):
        raise ValueError('Verification row count mismatch')
    seen = set()
    for package in packages:
        language = package['language']
        expected_name = 'dfm12-multilingual-synthetic-' + language
        if language in seen or package['name'] != expected_name:
            raise ValueError('Duplicate or unsafe package name')
        seen.add(language)
        folder = root/expected_name
        metadata = load(folder/'metadata/manifest.json')
        if (file_hash(folder/'metadata/manifest.json') != checked[language]['manifest_sha256'] or
            metadata['rows'] != language_target(language) or package['rows'] != metadata['rows']):
            raise ValueError('Package manifest drift')
        for relative, pin in metadata['files'].items():
            path = folder/relative
            if not path.resolve().is_relative_to(folder.resolve()):
                raise ValueError('Unsafe manifest path')
            if path.stat().st_size != pin['bytes'] or file_hash(path) != pin['sha256']:
                raise ValueError('Package file drift')
        yield package, folder


def license_evidence(output, api):
    from huggingface_hub import hf_hub_download
    target = output/'source-license-evidence.json'
    if target.exists():
        evidence = load(target)
        for record in evidence['sources']:
            if file_hash(output/record['card_file']) != record['card_sha256']:
                raise ValueError('License evidence drift')
        return evidence
    sources = []
    for root, names in [
        (Path('data/dfm12'), ['dynaword-'+l for l in ('no','nl','sv','pl','fo','is')]),
        (Path('data/dfm12/european-expansion-20260926'), ['text-ca','text-pt_pt'])]:
        for name in names:
            source = selected_source(root, name)
            sources.append(dict(repo=source['repo'], revision=source['revision'],
                approval=source.get('review_receipt'), catalog_sha256=file_hash(root/'sources.lock.json')))
    for language in ('en','da'):
        repo = 'schneiderkamplab/dfm8-openhermes-'+language
        sources.append(dict(repo=repo, revision=api.dataset_info(repo).sha,
                            note='Repaired OpenHermes source; no declared umbrella license inferred.'))
    for index, record in enumerate(sources):
        info = api.dataset_info(record['repo'], revision=record['revision'])
        path = Path(hf_hub_download(record['repo'], 'README.md', repo_type='dataset', revision=info.sha))
        relative = f'source-cards/{index:02d}.md'
        (output/relative).parent.mkdir(parents=True, exist_ok=True)
        (output/relative).write_bytes(path.read_bytes())
        record.update(revision=info.sha, license=(info.card_data or {}).get('license'),
                      card_file=relative, card_sha256=file_hash(path),
                      url=f"https://huggingface.co/datasets/{record['repo']}/blob/{info.sha}/README.md")
    evidence = dict(inspected_at=time.time(), sources=sources,
        policy='Source-dependent upstream terms; no blanket relicensing. Per-row provenance is retained.',
        warnings=['DynaWord collection CC0 does not remove upstream attribution/share-alike terms.',
                  'CorEGe-PT source card declares CC-BY-NC-SA-4.0; retained document rights also apply.',
                  'Repaired OpenHermes cards do not declare a license; do not infer a new one.'])
    write_json(target, evidence)
    return evidence


def publication_files(folder, output, evidence):
    package = folder.name
    overlay = output/'overlays'/package
    overlay.mkdir(parents=True, exist_ok=True)
    original = (folder/'README.md').read_text()
    card = original.replace('Local-only export; no upload authorized.',
        'Published under explicit user authorization dated 2026-09-29.')
    if package.endswith('-pt_pt'):
        import yaml
        marker, frontmatter, body = card.split('---', 2)
        if marker.strip():raise ValueError('Unexpected card frontmatter')
        metadata = yaml.safe_load(frontmatter)
        if metadata.get('language') != ['pt_pt']:raise ValueError('Unexpected Portuguese card language')
        metadata.update(language=['pt'], language_bcp47=['pt-PT'])
        card = '---\n' + yaml.safe_dump(metadata, sort_keys=False) + '---' + body
    card += ('\n## Source Licenses And Attribution\n\n'
        'This mixed-source synthetic release does not assert a blanket license. '
        'Applicable upstream attribution, share-alike and noncommercial restrictions remain; '
        'see [source terms](LICENSES.md), pinned source cards, and per-row provenance in metadata/. '
        'Historical local-only fields in the original package manifest describe export-time authorization; '
        'metadata/publication-authorization.json records the later upload authorization.\n')
    (overlay/'README.md').write_text(card)
    text = '# Source Terms\n\n' + evidence['policy'] + '\n\n'
    for record in evidence['sources']:
        text += f"- [{record['repo']}]({record['url']}): card license {json.dumps(record.get('license'))}.\n"
    text += '\n' + '\n'.join('- '+warning for warning in evidence['warnings']) + '\n'
    (overlay/'LICENSES.md').write_text(text)
    write_json(overlay/'authorization.json', dict(authorization=AUTHORIZATION,
        source_export=str(folder.resolve()), manifest_sha256=file_hash(folder/'metadata/manifest.json'),
        license_evidence_sha256=file_hash(output/'source-license-evidence.json')))
    files = {str(p.relative_to(folder)):p for p in folder.rglob('*') if p.is_file()}
    files.update({'README.md':overlay/'README.md', 'LICENSES.md':overlay/'LICENSES.md',
        'metadata/publication-authorization.json':overlay/'authorization.json',
        'metadata/source-license-evidence.json':output/'source-license-evidence.json'})
    files.update({'metadata/'+p['card_file']:output/p['card_file'] for p in evidence['sources']})
    return files


def verify_remote(api, repo, revision, files, rows):
    from huggingface_hub import hf_hub_download
    inventory = set(api.list_repo_files(repo, repo_type='dataset', revision=revision)) - {'.gitattributes'}
    if inventory != set(files):raise ValueError('Remote inventory mismatch: '+repo)
    count = 0
    for relative, path in files.items():
        remote = hf_hub_download(repo, relative, repo_type='dataset', revision=revision)
        if file_hash(remote) != file_hash(path):raise ValueError('Remote hash mismatch: '+relative)
        if relative.startswith('data/train-'):
            with gzip.open(remote, 'rt') as stream:
                count += sum(1 for _ in stream)
    if count != rows:raise ValueError('Remote row count mismatch')
    return count


def publish(roots, output):
    from huggingface_hub import HfApi, CommitOperationAdd
    from huggingface_hub.errors import RepositoryNotFoundError
    output = Path(output);output.mkdir(parents=True, exist_ok=True)
    api = HfApi();api.whoami()
    with lock(output/'upload.lock'):
        evidence = license_evidence(output, api)
        receipt_path = output/'upload-receipts.json'
        receipts = load(receipt_path) if receipt_path.exists() else {}
        for root in map(Path, roots):
            mirror = root/'metadata/upload-receipts.json'
            local = load(mirror) if mirror.exists() else {}
            for package, folder in validated_packages(root):
                repo = NAMESPACE+'/'+package['name']
                sha = file_hash(folder/'metadata/manifest.json')
                files = publication_files(folder, output, evidence)
                pins = {name:file_hash(path) for name,path in files.items()}
                old = receipts.get(repo)
                if old and (old['manifest_sha256'] != sha or old['file_pins'] != pins):
                    raise ValueError('Publication inputs drifted: '+repo)
                if old and old['status'] == 'verified':
                    verify_remote(api,repo,old['revision'],files,package['rows'])
                    local[repo]=old;write_json(mirror,local)
                    continue
                try:previous = api.repo_info(repo, repo_type='dataset')
                except RepositoryNotFoundError:previous = None
                if previous and not old:
                    raise ValueError('Unowned existing repository; refusing overwrite: '+repo)
                if previous and old:
                    remote_files=set(api.list_repo_files(repo,repo_type='dataset',revision=previous.sha))-{'.gitattributes'}
                    if remote_files:
                        count=verify_remote(api,repo,previous.sha,files,package['rows'])
                        old.update(status='verified',revision=previous.sha,remote_rows=count,completed=time.time())
                        write_json(receipt_path,receipts);local[repo]=old;write_json(mirror,local)
                        continue
                receipts[repo]=dict(status='publishing',manifest_sha256=sha,file_pins=pins,
                    rows=package['rows'],source_root=str(root.resolve()),authorization=AUTHORIZATION,started=time.time())
                write_json(receipt_path,receipts)
                api.create_repo(repo,repo_type='dataset',private=False,exist_ok=True)
                parent=api.repo_info(repo,repo_type='dataset').sha
                if set(api.list_repo_files(repo,repo_type='dataset',revision=parent))-{'.gitattributes'}:
                    raise ValueError('Repository concurrently populated: '+repo)
                commit=api.create_commit(repo,repo_type='dataset',parent_commit=parent,
                    operations=[CommitOperationAdd(path_in_repo=name,path_or_fileobj=str(path)) for name,path in sorted(files.items())],
                    commit_message='Publish completed audited multilingual synthetic conversations with source provenance')
                count=verify_remote(api,repo,commit.oid,files,package['rows'])
                receipts[repo].update(status='verified',revision=commit.oid,remote_rows=count,completed=time.time())
                write_json(receipt_path,receipts);local[repo]=receipts[repo];write_json(mirror,local)
                print('VERIFIED',repo,count,commit.oid,flush=True)
        verified={repo:receipt for repo,receipt in receipts.items() if receipt['status']=='verified'}
        write_json(output/'upload-completion.json',dict(repositories=len(verified),
            rows=sum(p['remote_rows'] for p in verified.values()),completed=time.time(),
            all_19_complete=len(verified)==len(ALL_LANGUAGES)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--root',action='append',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();publish(args.root,args.output)
