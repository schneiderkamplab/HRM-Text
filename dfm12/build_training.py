"""Accepted-only DFM12 tokenization and additive sampling over frozen DFM11 epochs."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import yaml

from .io import file_hash, load, lock, write_json

FIELDS = ('inst_start', 'inst_len', 'resp_start', 'resp_len')
CHUNK = 1_000_000


def source_repeat(config, name):
    value = config.get('identity_repeat', 10) if name.startswith('dfm12-identity-') else 1
    if type(value) is not int or value < 0:
        raise ValueError('identity_repeat must be a nonnegative integer')
    return value


def package_data_files(manifest):
    if manifest.get('schema') in (
        'dfm12-multilingual-completed-export-v1', 'dfm12-identity21-accepted-export-v1'
    ):
        entries = [dict(file=name, sha256=value['sha256'] if isinstance(value, dict) else value)
                   for name, value in manifest['files'].items() if name.startswith('data/')]
    else:
        entries = manifest['data_files']
    if not entries:
        raise ValueError('Nonempty package has no training files')
    for entry in entries:
        path = Path(entry['file'])
        if path.is_absolute() or '..' in path.parts or path.parts[0] != 'data':
            raise ValueError('Unsafe training file path')
    return entries


def registered_packages(config):
    """Resolve every published package once, retaining its owning export root."""
    seen = set()
    result = []
    overrides = {name: Path(root).resolve() for name, root in config.get('package_overrides', {}).items()}
    for value in config['export_roots']:
        root = Path(value)
        receipts = root / 'metadata/upload-receipts.json'
        if not receipts.exists():
            receipts = root / 'upload-receipts.json'
        uploads = load(receipts)
        for package in load(root / 'manifest.json')['packages']:
            name = package['name']
            if name in overrides and root.resolve() != overrides[name]:
                continue
            if Path(name).name != name or not name.startswith('dfm12-'):
                raise ValueError('Unsafe package name: ' + name)
            if name in seen:
                raise ValueError('Duplicate exported component: ' + name)
            seen.add(name)
            if not package['rows']:
                if name in overrides:
                    raise ValueError('Empty replacement package: ' + name)
                continue
            directory = root / name
            receipt = uploads.get('schneiderkamplab/' + name, {})
            manifest = load(directory / 'metadata/manifest.json')
            checksum = file_hash(directory / 'metadata/manifest.json')
            valid = package.get('validation', {}).get('valid')
            if manifest.get('schema') == 'dfm12-multilingual-completed-export-v1':
                verification = load(root / 'verification.json')
                valid = (verification.get('all_package_hashes_verified') is True
                         and verification.get('all_training_audit_pairs_verified') is True
                         and verification['manifest_sha256'] == file_hash(root / 'manifest.json')
                         and any(p['manifest_sha256'] == checksum and p['rows'] == package['rows']
                                 for p in verification['packages']))
            elif manifest.get('schema') == 'dfm12-identity21-accepted-export-v1':
                valid = (receipt.get('remote_rows') == package['rows'] == manifest['rows']
                         and bool(receipt.get('revision')))
            if name in config.get('local_only_disabled_packages', []):
                if source_repeat(config, name) != 0:
                    raise ValueError('Unpublished local package must remain disabled: ' + name)
                from .export_validator import validate
                checked = validate(directory)
                if not checked['valid'] or checked['rows'] != package['rows']:
                    raise ValueError('Invalid local disabled package: ' + name)
                result.append((package, directory))
                continue
            if (not valid
                    or receipt.get('status') != 'verified'
                    or receipt.get('manifest_sha256') != checksum):
                raise ValueError('Unverified or changed package: ' + name)
            result.append((package, directory))
    if set(overrides) - seen:
        raise ValueError('Missing replacement packages: ' + ', '.join(sorted(set(overrides) - seen)))
    return result


def merge_epoch(base, additions, output, offset, seed):
    """Uniformly shuffle complete rows; offset only the added token pointers."""
    output.mkdir(parents=True, exist_ok=True)
    n = len(np.load(base / 'inst_len.npy', mmap_mode='r'))
    m = len(np.load(additions / 'inst_len.npy', mmap_mode='r'))
    perm = np.random.default_rng(seed).permutation(n + m)
    totals = {'base': 0, 'additions': 0}
    for field in FIELDS:
        a = np.load(base / (field + '.npy'), mmap_mode='r')
        b = np.load(additions / (field + '.npy'), mmap_mode='r')
        if len(a) != n or len(b) != m:
            raise ValueError('Mismatched index lengths')
        dst = np.lib.format.open_memmap(output / (field + '.npy'), mode='w+', dtype=np.uint64, shape=(n+m,))
        for start in range(0, n+m, CHUNK):
            p = perm[start:start+CHUNK]
            mask = p < n
            values = np.empty(len(p), dtype=np.uint64)
            values[mask] = a[p[mask]]
            values[~mask] = b[p[~mask]-n]
            if field.endswith('_start'):
                values[~mask] += offset
            else:
                totals['base'] += int(values[mask].sum())
                totals['additions'] += int(values[~mask].sum())
            dst[start:start+len(p)] = values
        dst.flush()
        del dst
    return dict(totals, base_rows=n, added_rows=m)


def combine(base, additions, output, epochs):
    metadata = load(base / 'metadata.json')
    extra = load(additions / 'metadata.json')
    for key in ('vocab_size', 'enable_thinking', 'template_mode'):
        if metadata['tokenizer_info'].get(key) != extra['tokenizer_info'].get(key):
            raise ValueError(f'Tokenizer mismatch: {key}')
    for key in ('tokenizer_path', 'chat_template_path'):
        if file_hash(metadata['tokenizer_info'][key]) != file_hash(extra['tokenizer_info'][key]):
            raise ValueError(f'Tokenizer content mismatch: {key}')
    if metadata['max_seq_len'] != extra['max_seq_len']:
        raise ValueError('Context length mismatch')
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'metadata.json').exists():
        raise FileExistsError('Refusing to replace an already published sampled corpus')
    a = np.load(base / 'tokens.npy', mmap_mode='r')
    b = np.load(additions / 'tokens.npy', mmap_mode='r')
    token_receipt = output / 'token-copy.json'
    if not token_receipt.exists():
        dst = np.lib.format.open_memmap(output / 'tokens.npy', mode='w+', dtype=a.dtype, shape=(len(a)+len(b),))
        for src, offset in ((a, 0), (b, len(a))):
            for i in range(0, len(src), 8*CHUNK):
                dst[offset+i:offset+min(i+8*CHUNK,len(src))] = src[i:i+8*CHUNK]
                if i % (1024*CHUNK) == 0:
                    dst.flush()
                    print('token copy', offset+i, '/',len(a)+len(b), flush=True)
        dst.flush()
        del dst
        write_json(token_receipt, {'base_tokens':len(a), 'addition_tokens':len(b)})
    reports = []
    for epoch in range(epochs):
        path = output / f'epoch_{epoch}'
        receipt = path / 'merge.json'
        if receipt.exists():
            report = load(receipt)
        else:
            report = merge_epoch(base / path.name, additions / path.name, path, len(a), epoch)
            write_json(receipt, report)
        reports.append(report)
        print('merged', epoch, report, flush=True)
    metadata['total_length'] = round(sum(r['base']+r['additions'] for r in reports)/epochs)
    for key in ('tokenizer_path','chat_template_path'):
        metadata['tokenizer_info'][key] = os.path.relpath(Path(metadata['tokenizer_info'][key]).resolve())
    metadata['tokenizer_info']['tokenizer_path_base'] = 'repo_root'
    write_json(output / 'build-receipt.json', {'base':str(base),'additions':str(additions),'epochs':reports,
        'additional_tokens_per_epoch':sum(r['additions'] for r in reports)/epochs,
        'base_tokens_per_epoch':sum(r['base'] for r in reports)/epochs})
    # Published last: readers cannot mistake partial index files for a ready corpus.
    write_json(output / 'metadata.json', metadata)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers',type=int,default=16)
    parser.add_argument('--epochs',type=int,default=10)
    parser.add_argument('--local-dala-additions', type=Path,
                        help='Verified local pair-audited DaLA integration.json; no HF upload required')
    parser.add_argument('--suffix', default='', help='Isolated new build/output suffix')
    parser.add_argument('--sources-config', type=Path, default=Path('dfm12/training_sources.json'))
    parser.add_argument('--prepare-only', action='store_true', help='Stage validated inputs and sampling rules without tokenizing or sampling')
    parser.add_argument('--tokenize-only', action='store_true', help='Stage and tokenize without sampling or replacing an existing corpus')
    args = parser.parse_args()
    source_config = load(args.sources_config)
    if not args.local_dala_additions and source_config.get('local_dala_registry'):
        registry = load(source_config['local_dala_registry'])
        args.local_dala_additions = Path(registry['path'])
        if file_hash(args.local_dala_additions) != registry['sha256']:
            raise ValueError('Changed local DaLA integration manifest')
    if not 1 <= args.workers <= 64 or not 1 <= args.epochs <= 10:
        raise ValueError('Use 1-64 workers and 1-10 inherited epochs')
    if args.suffix and any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in args.suffix):
        raise ValueError('Unsafe build suffix')
    if args.local_dala_additions and not args.suffix:
        raise ValueError('Local additions require an isolated --suffix; existing corpus is immutable')
    suffix = '-' + args.suffix if args.suffix else ''
    root = Path('data/dfm12/training-build' + suffix)
    root.mkdir(parents=True,exist_ok=True)
    with lock(root / '.lock'):
        base = Path('data/sampled_dfm11')
        info = load(base / 'metadata.json')['tokenizer_info']
        packages = registered_packages(source_config)
        stage = root / 'accepted_inputs'
        rules = []
        sources = []
        for package, directory in packages:
            name = package['name']
            manifest = load(directory / 'metadata/manifest.json')
            repeat = source_repeat(source_config, name)
            rules.append({'prefix':name+'__', 'repeat':repeat})
            sources.append({'name':name,'repeat':repeat,
                            'hf_repo_id':'schneiderkamplab/'+name,
                            'export_root':str(directory.parent),
                            'manifest_sha256':file_hash(directory/'metadata/manifest.json')})
            for entry in package_data_files(manifest):
                src = directory / entry['file']
                if file_hash(src) != entry['sha256']:
                    raise ValueError(f'Source checksum mismatch: {src}')
                dest = stage / name / Path(entry['file']).name
                dest.parent.mkdir(parents=True,exist_ok=True)
                if dest.exists() or dest.is_symlink():
                    if not dest.is_symlink() or dest.resolve() != src.resolve():
                        raise ValueError('Conflicting input: ' + str(dest))
                else:
                    dest.symlink_to(src.resolve())
        if args.local_dala_additions:
            from .dala_audited_release import validate_additions
            additions = validate_additions(args.local_dala_additions)
            for component in additions['components']:
                name = component['name']
                if name in {s['name'] for s in sources}:
                    raise ValueError('Duplicate local/exported component: ' + name)
                rules.append({'prefix': name + '__', 'repeat': 1})
                sources.append({'name': name, 'repeat': 1,
                                'hf_repo_id': load(Path(component['source_package'])/'metadata/manifest.json')['repo_id'],
                                'integration_sha256': file_hash(args.local_dala_additions)})
                for item in component['data_files']:
                    src = Path(item['path']).resolve()
                    dest = stage / name / src.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if dest.exists() or dest.is_symlink():
                        if not dest.is_symlink() or dest.resolve() != src:
                            raise ValueError('Conflicting local input: ' + str(dest))
                    else:
                        dest.symlink_to(src)
        source_receipt = root / 'sources.json'
        if source_receipt.exists() and load(source_receipt) != sources:
            raise ValueError('Accepted inventory changed; use a new build root')
        write_json(source_receipt,sources)
        policy = root / 'prefix_config.yaml'
        policy.write_text(yaml.safe_dump(rules,sort_keys=False))
        if args.prepare_only:
            print('Prepared', len(sources), 'sources at', stage, flush=True)
            return
        tokenized = Path('data/tokenized_dfm12_additions' + suffix)
        subprocess.run([sys.executable,'scripts/tokenize_chat_template.py',str(stage),
            '--tokenizer-path',info['tokenizer_path'],'--chat-template',info['chat_template_path'],
            '--output-dir',str(tokenized),'--max-seq-len','4096','--workers',str(args.workers)],check=True)
        counts = {}
        for task in tokenized.iterdir():
            if not task.is_dir():
                continue
            name = task.name.split('__')[0]
            if name not in {s['name'] for s in sources}:
                raise ValueError(f'Unexpected tokenized task {task}')
            count = counts.setdefault(name, {'rows':0,'tokens':0})
            lengths = np.load(task/'inst_len.npy',mmap_mode='r')
            count['rows'] += len(lengths)
            count['tokens'] += int(lengths.sum())
            count['tokens'] += int(np.load(task/'resp_len.npy',mmap_mode='r').sum())
        for source in sources:
            if source['name'] not in counts:
                raise ValueError(f'Missing tokenized package {source}')
            counts[source['name']]['repeat'] = source['repeat']
        write_json(root/'token-counts.json',counts)
        if args.tokenize_only:
            print('Tokenization complete; no sampling:', tokenized, flush=True)
            return
        # Translation ceilings are not quotas: do not repeat short supplies.
        for name, count in counts.items():
            if name.startswith('dfm12-opus-'):
                cap = 661329827 if 'en' in name.removeprefix('dfm12-opus-').split('-') else 165332456
                if count['tokens'] > cap:
                    raise ValueError(f'Translation cap requires explicit selection: {name}')
        sampled = Path('data/sampled_dfm12_additions' + suffix)
        if not (sampled/'metadata.json').exists():
            subprocess.run([sys.executable,'data_io/sample_tokenized.py',f'tokenized_path={tokenized}',
                f'output_path={sampled}',f'prefix_config_path={policy}',f'epochs={args.epochs}',
                'concat_workers=1','skip_unmatched=true'],check=True)
        combine(base,sampled,Path('data/sampled_dfm12' + suffix),args.epochs)


if __name__ == '__main__':
    main()
