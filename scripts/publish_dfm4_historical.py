"""Publish only verified historical DFM4 additions, then pin their Hub commit."""
import argparse
from collections import Counter
import fcntl
import json
import os
from pathlib import Path
import shutil
import sys

from huggingface_hub import HfApi, hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.publish_verified_dfm_transforms import digest
from scripts.replay_dfm_serial import write_json

REPO = 'schneiderkamplab/dfm4-historical-additions'
FAMILIES = {
    'paragraph': {'dfm4_common_pile_paragraph_reorder', 'dfm4_dynaword_paragraph_reorder'},
    'summary': {'dfm4_arxiv_paper_summarization', 'dfm4_govreport_summarization',
                'dfm4_wiki_cat_sum_summarization', 'dfm4_laion_scientific_summaries'},
}
COUNTS = {'paragraph': 450, 'summary': 4019}


def require_verified(work):
    for name in ('verified.json', 'generated-row-comparison.json', 'addition-token-comparison.json'):
        receipt = json.loads((work / name).read_text())
        if receipt.get('status') != 'matched':
            raise ValueError(f'Unverified evidence: {name}')
        if name == 'verified.json' and (receipt.get('version') != 4 or receipt.get('verified_files') != 21):
            raise ValueError('Full DFM4 comparison required')


def inventory(work):
    files = []
    for kind, families in FAMILIES.items():
        paths = sorted((work / kind).rglob('*.parquet'))
        found = {p.relative_to(work / kind).parts[0] for p in paths}
        if found != families or len(paths) != COUNTS[kind]:
            raise ValueError(f'Unexpected {kind} inventory: {len(paths)} files, {sorted(found)}')
        for path in paths:
            if path.is_symlink() or not path.resolve().is_relative_to((work / kind).resolve()):
                raise ValueError('Payload must be a reconstructed local file')
        files.extend(paths)
    return files


def build(work):
    require_verified(work)
    files = inventory(work)
    package = work / 'hf-additions-package'
    package.mkdir(exist_ok=True)
    manifest = []
    for i, src in enumerate(files, 1):
        rel = Path('data') / src.relative_to(work)
        dst = package / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            os.link(src, dst)
        sha = digest(src)
        if dst.stat().st_size != src.stat().st_size or (not os.path.samefile(src, dst) and digest(dst) != sha):
            raise ValueError(f'Stale payload: {rel}')
        manifest.append(dict(path=rel.as_posix(), size=src.stat().st_size, sha256=sha))
        if i % 100 == 0 or i == len(files):
            print(f'Packaged {i}/{len(files)}', flush=True)
    provenance = package / 'provenance'
    provenance.mkdir(exist_ok=True)
    for version, names in {
        1: ('input-provenance.json', 'verified.json'),
        3: ('hf-input-lock.json', 'hf-publication.json', 'verified.json'),
        4: ('hf-input-lock.json', 'verified.json', 'generated-row-comparison.json',
            'addition-token-comparison.json', 'prefix_config.yaml'),
    }.items():
        for name in names:
            dst = provenance / f'dfm{version}' / name
            dst.parent.mkdir(exist_ok=True)
            shutil.copyfile(work.parent / f'dfm{version}' / name, dst)
    for name in ('rebuild_dfm4_additions.py', 'generate_dfm4_tasks.py', 'publish_dfm4_historical.py',
                 'tokenize_hrm_hf.py', 'build_tokenized_dfm4_tree.py'):
        shutil.copyfile(ROOT / 'scripts' / name, provenance / name)
    shutil.copytree(work / 'paragraph_receipts', provenance / 'paragraph_receipts', dirs_exist_ok=True)
    write_json(provenance / 'recipe.json', dict(seed=20260601, epochs=5, sampling_seed=0,
        concat_workers=1, common_pile_variant='single-window 1370 chars, max 8 paragraphs, cap 6000',
        dynaword_variant='four-window, cap 200000', max_rows_scanned_per_file=250000,
        inherited_payloads_included=False, tokenizer='Sapient BPE; HRM template',
        supersedes='DFM4 preparation.json preliminary recipe-recovery hold'))
    proof = [dict(path=p.relative_to(package).as_posix(), size=p.stat().st_size, sha256=digest(p))
             for p in sorted(provenance.rglob('*')) if p.is_file()]
    write_json(package / 'manifest.json', dict(version=4, files=manifest, provenance=proof,
        families=dict(Counter(Path(x['path']).parts[2] for x in manifest)),
        historical_full_reconstruction=True, inherited_payloads_included=False))
    (package / 'README.md').write_text(
        '---\nlanguage:\n- da\n- en\ntask_categories:\n- text-generation\n---\n'
        '# Historical DFM4 additions\n\n'
        'Six verified paragraph-reordering and summarization families only. No inherited '
        'DFM1-3 payloads or preliminary smoke outputs. Original task names, filenames, '
        'variants and Parquet row order are preserved under data/paragraph and data/summary.\n\n'
        'Full token values, five epoch index sets (21 arrays) and metadata matched the '
        'historical corpus. Manifest SHA-256 covers payloads and provenance. Source revision '
        'locks, reconstruction scripts, paragraph receipts and sampling settings are included. '
        'Predecessor provenance is lineage, not additional packaged training data.\n\n'
        'Upstream licenses and attribution continue to apply; no blanket replacement '
        'license is granted. See provenance/dfm1/input-provenance.json and the DFM3/DFM4 '
        'HF input locks for source repositories and revisions.\n')
    expected = {x['path'] for x in manifest + proof} | {'manifest.json', 'README.md'}
    actual = {p.relative_to(package).as_posix() for p in package.rglob('*') if p.is_file()}
    if actual != expected:
        raise ValueError('Unexpected package files; refusing upload')
    return package, manifest + proof


def pin(saved, registry):
    with registry.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        value = json.loads(registry.read_text())
        value['4'] = {k: saved[k] for k in ('repo_id', 'revision', 'manifest_sha256')}
        write_json(registry, value)


def publish(work, registry):
    with (work / 'dfm4-publication.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        package, entries = build(work)
        api = HfApi()
        api.create_repo(repo_id=REPO, repo_type='dataset', private=False, exist_ok=True)
        api.update_repo_settings(repo_id=REPO, repo_type='dataset', private=False)
        print(f'Uploading PUBLIC {REPO}', flush=True)
        result = api.upload_folder(repo_id=REPO, repo_type='dataset', folder_path=package,
            commit_message='Verified historical DFM4 additions only')
        write_json(work / 'hf-upload-commit.json', dict(repo_id=REPO, revision=result.oid))
        info = api.dataset_info(REPO, revision=result.oid, files_metadata=True)
        if info.private:
            raise ValueError('Repository is not public')
        remote = {p.rfilename: p for p in info.siblings}
        for item in entries + [dict(path='manifest.json', size=(package / 'manifest.json').stat().st_size,
                                   sha256=digest(package / 'manifest.json'))]:
            entry = remote[item['path']]
            sha = getattr(entry.lfs, 'sha256', None) if entry.lfs else None
            if sha is None:
                sha = digest(Path(hf_hub_download(REPO, item['path'], repo_type='dataset', revision=result.oid)))
            if entry.size != item['size'] or sha != item['sha256']:
                raise ValueError(f'Remote checksum mismatch: {item["path"]}')
        saved = dict(repo_id=REPO, revision=result.oid, private=False, files=sum(COUNTS.values()),
                     manifest_sha256=digest(package / 'manifest.json'), status='uploaded_sha256_verified')
        write_json(work / 'hf-publication.json', saved)
        pin(saved, registry)
        print(f'Published, verified and pinned {REPO}@{result.oid}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--registry', type=Path, default=ROOT / 'config/data/historical_rebuild_packages.json')
    args = parser.parse_args()
    publish(args.work.resolve(), args.registry.resolve())
