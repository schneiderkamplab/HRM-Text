"""Package/upload historical DFM1 derivatives only after a complete parity pass."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time

import pyarrow.parquet as pq
from huggingface_hub import HfApi

from scripts.queue_dfm_hf_rebuild import load, write_json


TARGETS = {
    'danish_dynaword': ('dfm1_dynaword_continuation',
                       'Danish DynaWord documents split into 12000-character continuation chunks.'),
    'opus': ('dfm1_opus_da_en',
             'OPUS Danish-English pairs expanded into both translation instruction directions.'),
}


def require_verified(queue):
    receipt = load(queue / 'dfm1/verified.json')
    if (receipt.get('status') != 'matched' or receipt.get('version') != 1
            or receipt.get('verified_files') != 17):
        raise ValueError('Full historical DFM1 token/index/metadata parity is required before publication')
    return receipt


def build(queue, destination, source_name):
    receipt = require_verified(queue)
    work = queue / 'dfm1'
    manifest = load(work / 'input-provenance.json')['acquisition_manifest']
    source = next(s for s in manifest['hf_sources'] if s['name'] == source_name)
    root = work / 'converted' / source_name
    package = destination / TARGETS[source_name][0]
    package.mkdir(parents=True, exist_ok=True)
    files = []
    for path in sorted(root.rglob('*.parquet')):
        rel = path.relative_to(root)
        target = package / 'data' / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        with target.open('rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        files.append(dict(path=target.relative_to(package).as_posix(), sha256=digest,
                          rows=pq.ParquetFile(target).metadata.num_rows,
                          historical_task=source_name + '__' + rel.as_posix().replace('/', '__')))
    if not files:
        raise ValueError(f'No converted files for {source_name}')
    provenance = dict(source=source, conversion=load(work / 'input-provenance.json'),
                      verification=receipt, files=files, rows=sum(f['rows'] for f in files),
                      sampling='Full converted reservoir; DFM1 caps applied separately by prefix_config.yaml')
    # Do not publish local agreement paths or unrelated source inventories.
    provenance['conversion'] = {k: v for k, v in provenance['conversion'].items()
                                if k in ('filter_git_revision', 'converter_sha256')}
    write_json(package / 'provenance.json', provenance)
    shutil.copyfile(work / 'prefix_config.yaml', package / 'prefix_config.yaml')
    (package / 'README.md').write_text(
        '---\nlanguage:\n- da\n' + ('- en\n' if source_name == 'opus' else '') +
        'task_categories:\n- text-generation\n---\n\n# ' + TARGETS[source_name][0] + '\n\n' +
        TARGETS[source_name][1] + '\n\n' +
        f"Upstream: [{source['repo_id']}](https://huggingface.co/datasets/{source['repo_id']}/tree/"
        f"{source['resolved_revision']}).\n\n"
        'Archival reproduction of DFM1, not a modern Gemma chat-format release. '
        'Columns: `condition`, `instruction`, `response`. Rows and file boundaries '
        'are preserved; no new audit, generation, deduplication, or content changes. '
        'DynaWord instructions are empty; OPUS instructions retain the historical source note.\n\n'
        f"Rows: {provenance['rows']:,}; files: {len(files)}. The full reconstructed DFM1 "
        'token bank and all four epoch index sets passed exact comparison against the '
        'preserved dataset before this package was created. Per-file hashes and upstream '
        'revisions are recorded in `provenance.json`.\n\n'
        'Upstream constituent licenses and attribution obligations still apply; '
        'this conversion does not grant additional redistribution or usage rights.\n')
    return package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--upload', action='store_true')
    parser.add_argument('--wait', action='store_true')
    args = parser.parse_args()
    while not (args.queue / 'dfm1/verified.json').exists():
        if not args.wait:
            raise ValueError('DFM1 has not passed comparison')
        state = load(args.queue / 'plan.json')['rows'][0]
        if state['status'] == 'blocked':
            raise ValueError(f"DFM1 blocked: {state.get('error')}")
        print('Waiting for complete DFM1 parity; nothing published.', flush=True)
        time.sleep(300)
    for source, (name, _) in TARGETS.items():
        package = build(args.queue, args.output, source)
        if args.upload:
            api = HfApi()
            repo_id = 'schneiderkamplab/' + name
            api.create_repo(repo_id, repo_type='dataset', exist_ok=True)
            commit = api.upload_folder(repo_id=repo_id, repo_type='dataset', folder_path=package,
                                       commit_message='Publish exact historical DFM1 derivative after parity verification')
            write_json(args.output / (name + '.upload.json'),
                       dict(repo_id=repo_id, commit=str(commit)))
        print(package, flush=True)


if __name__ == '__main__':
    main()
