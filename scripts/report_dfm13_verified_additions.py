"""Report a frozen assembly's exact row-language token totals and HF pins."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path

import numpy as np

from dfm12.io import file_hash, load, write_json
from scripts.assemble_dfm13_additions import signature, unready_reason


def lengths(source):
    for part in source['parts']:
        root = Path(part['path'])
        prompt = np.load(root/'inst_len.npy', mmap_mode='r', allow_pickle=False)
        response = np.load(root/'resp_len.npy', mmap_mode='r', allow_pickle=False)
        for a, b in zip(prompt, response, strict=True):
            yield int(a) + int(b)


def language(row):
    value = row.get('language')
    return value if isinstance(value, str) and value.strip() else 'unknown'


def remote(entry):
    from huggingface_hub import HfApi
    api = HfApi()
    repo, revision = entry['hf_repo_id'], entry['hf_revision']
    info = api.repo_info(repo, repo_type='dataset', revision=revision, files_metadata=True)
    if info.sha != revision or api.repo_info(repo, repo_type='dataset').sha != revision:
        raise ValueError('Remote revision/head mismatch: '+repo)
    folder = Path(entry['output']).parent.parent
    expected = dict(entry.get('files', {}))
    expected['data/train.jsonl'] = entry['output_sha256']
    expected.update({name: sha for sha, name in entry.get('attribution_files', {}).items()})
    for name in ('README.md', 'manifest.json'):
        expected.setdefault(name, file_hash(folder/name))
    siblings = {s.rfilename: s for s in info.siblings}
    checked = {}
    for name, sha in expected.items():
        item = siblings[name]
        path = folder/name
        if item.lfs:
            if item.lfs.sha256 != sha:
                raise ValueError('Remote LFS hash mismatch: '+repo+'/'+name)
            checked[name] = dict(sha256=sha, method='revision_bound_HF_LFS_SHA256')
        else:
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != sha:
                raise ValueError('Local attachment mismatch: '+str(path))
            blob = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            if item.blob_id != blob:
                raise ValueError('Remote git blob mismatch: '+repo+'/'+name)
            checked[name] = dict(sha256=sha, git_blob_sha1=blob, method='revision_bound_git_blob')
    return entry['name'], dict(repo=repo, revision=revision, head_matches=True, files=checked)


def report(assembly, output, check_remote=False):
    assembly = Path(assembly)
    manifest = load(assembly/'assembly.json')
    registry = load(assembly/'registry.snapshot.json')['additions']
    by_name = {e['name']: e for e in registry}
    eligible = {e['name'] for e in registry if not unready_reason(e)}
    ready = {s['name'] for s in manifest['ready_additions']}
    missing = sorted(eligible-ready)
    if missing:
        raise ValueError('Eligible additions missing from assembly: '+str(missing))
    # Reuse full assembly hashes only while exact file signatures remain unchanged.
    for path, pin in manifest['files'].items():
        if list(signature(Path(path))) != pin['signature']:
            raise ValueError('Assembly input changed: '+path)
    wave_totals = defaultdict(lambda: dict(sources=0, rows=0, tokens=0))
    language_totals = defaultdict(lambda: dict(rows=0, tokens=0))
    wave_language = defaultdict(lambda: defaultdict(lambda: dict(rows=0, tokens=0)))
    sources = []
    for source in manifest['ready_additions']:
        name = source['name']
        wave = 'wave3' if name.startswith('dfm13_wave3_') else (
            'wave4' if name.startswith('dfm13_wave4_') else 'other')
        counts = defaultdict(lambda: dict(rows=0, tokens=0))
        tokens = iter(lengths(source))
        with Path(source['source']).open() as handle:
            for line in handle:
                size = next(tokens)
                code = language(json.loads(line))
                counts[code]['rows'] += 1
                counts[code]['tokens'] += size
        if next(tokens, None) is not None:
            raise ValueError('Unmatched token rows: '+name)
        if (sum(c['rows'] for c in counts.values()) != source['rows'] or
                sum(c['tokens'] for c in counts.values()) != source['tokens']):
            raise ValueError('Language accounting mismatch: '+name)
        wave_totals[wave]['sources'] += 1
        for field in ('rows', 'tokens'):
            wave_totals[wave][field] += source[field]
            for code, value in counts.items():
                language_totals[code][field] += value[field]
                wave_language[wave][code][field] += value[field]
        entry = by_name[name]
        sources.append(dict(name=name, wave=wave, rows=source['rows'], tokens=source['tokens'],
            repeat=source['repeat'], by_language=dict(counts), subset_policy=entry.get('subset_policy'),
            subset_receipt=entry.get('subset_receipt'), subset_receipt_sha256=entry.get('subset_receipt_sha256'),
            parent_hf_revision=entry.get('parent_hf_revision')))
        print('COUNTED', name, source['rows'], source['tokens'], flush=True)
    remote_checks = {}
    if check_remote:
        entries = [by_name[s['name']] for s in manifest['ready_additions']
                   if s['name'].startswith(('dfm13_wave3_', 'dfm13_wave4_'))]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for name, result in pool.map(remote, entries):
                remote_checks[name] = result
                print('REMOTE', name, flush=True)
    for path, pin in manifest['files'].items():
        if list(signature(Path(path))) != pin['signature']:
            raise ValueError('Input mutated during report: '+path)
    result = dict(assembly=str(assembly.resolve()), assembly_sha256=file_hash(assembly/'assembly.json'),
        totals=manifest['totals'], totals_basis='One stored copy; additions only; repeats not materialized',
        by_wave=dict(wave_totals), by_language=dict(language_totals),
        by_wave_language={w: dict(v) for w, v in wave_language.items()}, sources=sources,
        unknown_language_policy='Missing explicit row.language is unknown; never inferred from filename',
        unready=manifest['unready_additions'], missing_eligible=[], remote=remote_checks,
        local_verification='Full assembler hashes/array checks plus unchanged signatures before and after report',
        sampling_performed=False)
    write_json(Path(output), result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--assembly', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--remote', action='store_true')
    a = p.parse_args()
    result = report(a.assembly, a.output, a.remote)
    print(json.dumps(dict(totals=result['totals'], by_wave=result['by_wave'],
                          remote_sources=len(result['remote']))))


if __name__ == '__main__':
    main()
