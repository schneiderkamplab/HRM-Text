"""Prepare HF-layout packages for completed approved DaLA compact subsets."""
import argparse
import os
from pathlib import Path
import time
from dfm12.io import atomic, file_hash, load, lock, write_json

ROOTS = [Path('data/dfm13')/name for name in (
    'dala-v2-compact-finalized-20261004-v1',
    'dala-remaining21-finalized-20261004-v1',
    'dala-baseline-delta-finalized-20261004-v1')]


def package(group, output):
    integration = load(group/'integration.json')
    if integration['status'] != 'complete_train_only':
        raise ValueError('Incomplete group')
    proof = integration['export']
    if file_hash(proof['path']) != proof['sha256']:
        raise ValueError('Export changed')
    export = load(proof['path']); language = export['language']
    name = 'dfm13-dala-v2-'+group.name+'-compact'
    # Preserve the nine already proposed canonical repository names.
    pool = group.name.rsplit('-', 1)[1]
    name = 'dfm13-dala-v2-'+language+'-compact-'+pool
    root = output/name
    with lock(output/(name+'.lock')):
        if (root/'ready.json').exists():
            result = load(root/'ready.json')
            if result['export_sha256'] != proof['sha256']:
                raise ValueError('Existing package binding differs')
            return result
        root.mkdir(parents=True, exist_ok=True)
        files = {}; configs = {task: {} for task in ('acceptability', 'correction')}
        for item in export['files']:
            parts = Path(item['relative']).parts
            if len(parts) != 3 or parts[0] != 'exports' or parts[1] not in configs:
                continue
            source = Path(item['path'])
            if file_hash(source) != item['sha256']:
                raise ValueError('Export shard changed')
            target = root/'data'/parts[1]/parts[2]; target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                os.link(source, target)
            if file_hash(target) != item['sha256']:
                raise ValueError('Package shard differs')
            relative = str(target.relative_to(root)); files[relative] = item['sha256']
            split = parts[2].removesuffix('.jsonl.gz')
            configs[parts[1]][split] = relative
        if any('train_representative' not in splits for splits in configs.values()):
            raise ValueError('Missing train data')
        language_tag = 'pt' if language == 'pt-PT' else language
        with atomic(root/'README.md') as stream:
            stream.write('---\nlanguage: ['+language_tag+']\ntask_categories: [text-generation]\nconfigs:\n')
            for task, splits in configs.items():
                stream.write('- config_name: '+task+'\n  data_files:\n')
                for split, path in sorted(splits.items()):
                    stream.write('  - split: '+('train' if split=='train_representative' else split)+'\n    path: '+path+'\n')
            stream.write('---\n\n# '+name+'\n\nAccepted compact whole-pair/control audit subset. '
                'Model judgments are not human or native-speaker certification and are not producer per-edit certification. '
                'Only the train split is tokenized for training; validation/test views remain separate. '
                'Native full messages and explicit target indices are preserved.\n\n'
                'Source-specific terms and attribution remain in each row provenance, including upstream dataset, '
                'revision, URL and license evidence where supplied. This derived package does not relicense '
                'those sources or assert a uniform license. See the pinned export receipt for screening and '
                'heldout exclusions. No rejected record text is included.\n')
        write_json(root/'export-receipt.json', export)
        files['README.md'] = file_hash(root/'README.md')
        files['export-receipt.json'] = file_hash(root/'export-receipt.json')
        result = dict(name=name, hf_repo_id='schneiderkamplab/'+name, uploaded=False,
            local_package_ready=True, export_sha256=proof['sha256'], files=files,
            train_task_rows=sum(e['rows'] for e in integration['components']),
            tokens=sum(e['tokens'] for e in integration['components']), language=language,
            source_terms='mixed_per_row_preserved_not_relicensed')
        write_json(root/'ready.json', result)
        return result


if __name__ == '__main__':
    raise SystemExit('Superseded: use scripts.package_dala_languages; one dataset per language required')
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,default=Path('exports_dfm13_dala_compact'))
    p.add_argument('--watch',action='store_true'); a=p.parse_args()
    while True:
        completed=[]; errors=[]
        for root in ROOTS:
            for integration in sorted((root/'groups').glob('*/integration.json')):
                try:
                    completed.append(package(integration.parent,a.output))
                except Exception as exc:
                    errors.append(dict(group=str(integration.parent),error=repr(exc)))
        write_json(a.output/'inventory.json',dict(packages=completed,errors=errors,expected_packages=36,
                   complete=len(completed)==36 and not errors,uploaded=False))
        print('PACKAGES',len(completed),'ERRORS',errors,flush=True)
        if not a.watch or len(completed)==36 and not errors:break
        time.sleep(60)
