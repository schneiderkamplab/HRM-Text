"""Package the twelve unpublished inherited DaLA repositories, without retokenizing."""
from collections import defaultdict
import os
from pathlib import Path
from dfm12.io import atomic, file_hash, load, lock, write_json


def main():
    handoff = load('data/dfm13/dfm12-full-inheritance-20261004-v2/handoff.json')
    if file_hash(handoff['full_reference']) != handoff['full_reference_sha256']:
        raise ValueError('Inheritance seal drift')
    manifest = load(handoff['full_reference']); groups = defaultdict(list)
    for entry in manifest['sources']:
        if entry['publication']['status'] != 'verified_published':
            groups[entry['hf_repo_id']].append(entry)
    if len(groups) != 12:
        raise ValueError('Unexpected inherited unpublished repository count')
    output = Path('exports_dfm13_inherited_dala'); results = []
    with lock(output/'.lock'):
        for repo, entries in sorted(groups.items()):
            folder = output/repo.split('/')[-1]; configs = {}; files = {}
            for entry in entries:
                task = entry['name'].rsplit('-', 1)[-1]
                if task not in ('acceptability', 'correction') or task in configs:
                    raise ValueError('Unexpected task mapping')
                proof = entry['publication']
                if file_hash(proof['integration']) != proof['integration_sha256']:
                    raise ValueError('Inherited audit integration drift')
                configs[task] = []
                for part in entry['parts']:
                    source = Path(part['source'])
                    if file_hash(source) != part['source_sha256_from_verified_publication']:
                        raise ValueError('Inherited accepted payload drift')
                    target = folder/'data'/task/source.name; target.parent.mkdir(parents=True, exist_ok=True)
                    if not target.exists(): os.link(source, target)
                    if file_hash(target) != part['source_sha256_from_verified_publication']:
                        raise ValueError('Package payload drift')
                    relative = str(target.relative_to(folder)); files[relative] = file_hash(target)
                    configs[task].append(relative)
            with atomic(folder/'README.md') as out:
                out.write('---\ntask_categories: [text-generation]\nconfigs:\n')
                for task in configs:
                    out.write('- config_name: '+task+'\n  data_files:\n  - split: train\n    path: data/'+task+'/*.jsonl.gz\n')
                out.write('---\n\n# '+repo.split('/')[-1]+'\n\nAuthorized accepted-only inherited DaLA training subset. '
                    'Contains the existing native messages and target policy without rewriting or resampling. '
                    'Source attribution and source-specific license terms remain in row provenance; no uniform '
                    'license is asserted. Automated audit decisions are not native-speaker certification. '
                    'This package contains training rows only; no heldout data is added.\n')
            result = dict(hf_repo_id=repo, uploaded=False, local_package_ready=True, files=files,
                          rows=sum(e['rows'] for e in entries), tokens=sum(e['tokens'] for e in entries),
                          inherited_handoff_sha256=file_hash('data/dfm13/dfm12-full-inheritance-20261004-v2/handoff.json'),
                          components=[e['name'] for e in entries])
            write_json(folder/'manifest.json', result); results.append(result)
            write_json(output/'inventory.json', dict(packages=results, complete=len(results)==12, uploaded=False))
            print('PACKAGED', repo, result['rows'], flush=True)


if __name__ == '__main__': main()
