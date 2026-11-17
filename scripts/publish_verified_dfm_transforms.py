"""Publish exact DFM2/3 derivatives only after both serial comparisons pass."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

from huggingface_hub import HfApi, snapshot_download

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.replay_dfm_serial import write_json
from scripts.download_training_datasets import HF_DATASETS


def register_publication(version, saved):
    path = ROOT / 'config/data/historical_rebuild_packages.json'
    registry = json.loads(path.read_text())
    registry[str(version)] = {k: saved[k] for k in ('repo_id', 'revision')}
    write_json(path, registry)


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def require_verified(queue):
    for version in (2, 3):
        path = queue / f'dfm{version}/verified.json'
        if not path.exists() or json.loads(path.read_text()).get('status') != 'matched':
            raise ValueError(f'DFM{version} is not verified')


def publish(queue, version, api):
    work = queue / f'dfm{version}'
    receipt = work / 'hf-publication.json'
    if receipt.exists():
        saved = json.loads(receipt.read_text())
        api.update_repo_settings(repo_id=saved['repo_id'], repo_type='dataset', private=False)
        saved['private'] = False
        write_json(receipt, saved)
        api.dataset_info(saved['repo_id'], revision=saved['revision'])
        register_publication(version, saved)
        return
    name = {2: 'dfm2-dynaword-historical', 3: 'dfm3-common-pile-historical'}[version]
    repo = 'schneiderkamplab/' + name
    package = work / 'hf-package'
    package.mkdir(exist_ok=True)
    files = sorted((work / 'converted').rglob('*.parquet'))
    expected = 450 if version == 2 else 2862
    if len(files) != expected:
        raise ValueError(f'Expected {expected} files, got {len(files)}')
    manifest = []
    for i, src in enumerate(files):
        rel = Path('data') / src.relative_to(work / 'converted')
        dst = package / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            os.link(src, dst)
        sha = digest(dst)
        if not os.path.samefile(src, dst) and sha != digest(src):
            raise ValueError(f'Stale package payload: {dst}')
        manifest.append(dict(path=str(rel), size=dst.stat().st_size, sha256=sha))
        print(f'DFM{version}: package {i+1}/{len(files)}', flush=True)
    provenance = package / 'provenance'
    provenance.mkdir(exist_ok=True)
    for name in ('verified.json', 'generated-row-comparison.json', 'input-provenance.json',
                 'hf-input-lock.json', 'prefix_config.yaml'):
        if (work / name).exists():
            shutil.copyfile(work / name, provenance / name)
    generator = f'generate_dfm{version}_' + (
        'dynaword_tasks.py' if version == 2 else 'common_pile_tasks.py')
    shutil.copyfile(ROOT / 'scripts' / generator, provenance / generator)
    write_json(package / 'manifest.json', dict(
        version=version, files=manifest, max_chars=3000,
        seed=20260530 if version == 2 else 20260531,
        historical_full_reconstruction=True,
        format='condition/instruction/response; original file names and row order'))
    (package / 'README.md').write_text(
        '---\nlanguage:\n- ' + ('da' if version == 2 else 'en') +
        '\ntask_categories:\n- text-generation\n---\n'
        f'# Historical DFM{version} deterministic transformations\n\n'
        'Exact historical reconstruction, not a newer filtered/expanded release. '
        'All generated rows and sampled token/index arrays were compared to the preserved corpus.\n\n'
        'Original task-relative paths and row order are preserved under `data/`. '
        'The manifest contains SHA-256 checksums; provenance includes source locks, '
        'the generator and sampling recipe. Regeneration uses `--max-chars 3000 '
        '--historical-full-reconstruction` and the seed in the manifest. '
        'No model generation or new audit is required.\n\n'
        'Upstream source licenses and attribution requirements continue to apply; '
        'this package does not grant a blanket replacement license. '
        'See source repository identifiers/revisions in provenance.\n')
    api.create_repo(repo_id=repo, repo_type='dataset', private=False, exist_ok=True)
    api.update_repo_settings(repo_id=repo, repo_type='dataset', private=False)
    result = api.upload_folder(repo_id=repo, repo_type='dataset', folder_path=package,
                               commit_message=f'Verified historical DFM{version} transformations')
    revision = result.oid
    remote = {x.rfilename: x for x in api.dataset_info(
        repo, revision=revision, files_metadata=True).siblings}
    for item in manifest:
        entry = remote[item['path']]
        sha = getattr(entry.lfs, 'sha256', None) if entry.lfs else None
        if entry.size != item['size'] or sha != item['sha256']:
            raise ValueError(f'Remote payload verification failed: {item["path"]}')
    saved = dict(repo_id=repo, revision=revision, private=False,
                 files=len(files), status='uploaded_sha256_verified')
    write_json(receipt, saved)
    register_publication(version, saved)
    print(f'Published and verified {repo}@{revision}', flush=True)


def prepare_dfm4(queue, api):
    """Acquire additions now; preserve the historical paragraph-source split."""
    work = queue / 'dfm4'
    work.mkdir(exist_ok=True)
    lock = work / 'hf-input-lock.json'
    if lock.exists():
        sources = json.loads(lock.read_text())
    else:
        sources = []
        for source in HF_DATASETS:
            if source.name not in ('govreport_summarization', 'wiki_cat_sum',
                                   'laion_scientific_summaries'):
                continue
            sources.append(dict(name=source.name, repo_id=source.repo_id,
                                revision=api.dataset_info(source.repo_id).sha,
                                patterns=list(source.allow_patterns)))
        if len(sources) != 3:
            raise ValueError('DFM4 source registration incomplete')
        write_json(lock, sources)
    for source in sources:
        print(f'DFM4 acquiring {source["repo_id"]}', flush=True)
        snapshot_download(source['repo_id'], repo_type='dataset',
                          revision=source['revision'], allow_patterns=source['patterns'],
                          local_dir=work / 'downloads' / source['name'], max_workers=8)
    shutil.copyfile(ROOT / 'data_io/prefix_config_dfm4.yaml', work / 'prefix_config.yaml')
    write_json(work / 'preparation.json', dict(
        status='hf_additions_acquired', tokenizer_workers=32, epochs=5,
        predecessor='dfm3 verified and DFM2/3 published',
        remaining='Recover original Common Pile single-window paragraph algorithm; '
                  'retain later DynaWord multi-window algorithm; verify summarization lengths '
                  'before tokenization. Do not substitute current generator defaults.'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue', type=Path, required=True)
    parser.add_argument('--wait', action='store_true')
    args = parser.parse_args()
    queue = args.queue.resolve()
    with (queue / 'publication.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            try:
                require_verified(queue)
                break
            except ValueError:
                if not args.wait:
                    raise
                time.sleep(120)
        api = HfApi()
        for version in (2, 3):
            publish(queue, version, api)
        prepare_dfm4(queue, api)


if __name__ == '__main__':
    main()
