#!/usr/bin/env python3
"""Rebuild DFM9 pretrain data in the guarded HF-only serial rebuild queue.

The DFM9 union is a link farm over the verified DFM6 direct-jinja, DFM7 and
DFM8 tokenized trees plus 693 freshly converted and tokenized tasks: six new
HF post-training sources (Natural Instructions, Code Meta Reasoning,
Nemotron Terminal Corpus, NuminaMath 1.5, CoEdIT, ASSET), the windowed
Nemotron SWE shards, and the Danish croco-munin/gsm-symbolic extension. The
base links are recorded verbatim from the historical union tree, so the
rebuild reproduces the union without re-tokenizing the 10,720 inherited tasks.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.rebuild_dfm5 import allowed, link
from scripts.rebuild_dfm5_acquire import digest, load
from scripts.rebuild_dfm7 import compare_jsonl, semantic_digest
from scripts.replay_dfm_serial import equal_arrays, write_json

QUEUE = ROOT / 'data/rebuild_hf_dfm/serial-queue'
CONFIG = ROOT / 'config/data/dfm9_hf_rebuild.json'
ADAPTER_REVISION = 'cd88c93'   # last tokenize_chat_template.py state before 2026-08-07
TEMPLATE_REVISION = '0483afe'  # DFM8-pinned chat template, asserted unchanged in fe79a2d
DATA_IO_REVISION = 'fe79a2d'   # prefix_config_dfm9.yaml plus chat template state
CONVERTER_REVISION = '69fd85c4f9da91dac1b883f89cada6c88ac3117c'
REFERENCE = ROOT / 'data/tokenized_dfm9'
NEW_REFERENCE = ROOT / 'data/tokenized_dfm9_new'
SWE_REFERENCE = ROOT / 'data/tokenized_dfm9_swe_windowed'
CONVERTED_SOURCES = ROOT / 'data/converted_sources'
SWE_GROUP_SIZE = 8
EXT_REFERENCE = ROOT / 'data/tokenized_dfm9_ext'
LINK_TABLE = ROOT / 'logs/analysis/dfm9-prep/link_table.json'
FIELDS = ('tokens', 'inst_start', 'inst_len', 'resp_start', 'resp_len')
CONVERSION_HASH_SEED = '2'
FILTERED_ROOT = ROOT / 'data/filtered_sources'
DOWNLOADS = ROOT / 'data/downloads/datasets'
BASE_TREES = {'dfm6': QUEUE / 'dfm6/tokenized', 'dfm7': QUEUE / 'dfm7/union',
              'dfm8': QUEUE / 'dfm8/union'}
# Repos whose historical filtered_sources tree is the conversion input, mapped
# to the download directory backing it. The two extension sources are staged
# whole because convert_dfm9_extension.py reads its snapshot directory itself.
FILTERED_KIND = {
    'posttrain_natural_instructions': 'Muennighoff/natural-instructions',
    'allenai_code_meta_reasoning': 'allenai/code-meta-reasoning-cleaned-final-string-id',
    'nemotron_terminal_corpus': 'nvidia/Nemotron-Terminal-Corpus',
    'numinamath_1_5': 'AI-MO/NuminaMath-1.5',
    'posttrain_coedit': 'grammarly/coedit',
    'posttrain_asset': 'facebook/asset',
    'nemotron_swe': 'nvidia/Nemotron-SFT-SWE-v2',
}
# Local byte-faithful copies used when a filtered link dangles because the
# live download directory was later re-downloaded against a restructured
# upstream (the code-meta reasoning raw dir now holds thirty-six shards).
RECOVERY_SOURCE = {
    'allenai_code_meta_reasoning': 'allenai_code_meta_reasoning_flattened_legacy',
}
DOWNLOAD_KIND = {
    'croco_munin_da_50k': 'danish-foundation-models/croco-munin-apertus-8b-da-simpo-full-50k',
    'multilingual_gsm_symbolic': 'danish-foundation-models/multilingual-gsm-symbolic',
}
FRIENDLY_TO_REPO = {**{name: repo for name, repo in FILTERED_KIND.items()},
                    **DOWNLOAD_KIND}


def converter_env():
    return dict(os.environ, PYTHONHASHSEED=CONVERSION_HASH_SEED)


def roots(work):
    return [work.parent, work / 'acquisitions']


def acquisition_dir(work, repo, revision):
    return work / 'acquisitions' / (repo.replace('/', '--') + '--' + revision[:12])


def swe_task(sub):
    name = sub.rsplit('/', 1)[-1]
    if name.startswith('merged_') and name.endswith('.jsonl'):
        return name
    if name == 'agentless.parquet':
        return name
    raise ValueError(f'Unexpected DFM9 SWE union entry: {sub}')


def frozen_tree_files(directory):
    files = {}
    for path in sorted(directory.rglob('*')):
        rel = path.relative_to(directory)
        if path.is_dir() or any(part.startswith('.') for part in rel.parts):
            continue
        if path.suffix == '.md':
            continue
        files[rel.as_posix()] = path
    return files


def frozen_download_files(directory):
    files = {}
    for path in sorted(directory.rglob('*')):
        rel = path.relative_to(directory)
        if path.is_dir() or any(part.startswith('.') for part in rel.parts):
            continue
        files[rel.as_posix()] = path
    return files


def frozen_payload(work, friendly, rel, path, task_meta):
    source = path.resolve()
    if source.is_file():
        return dict(bytes=source.stat().st_size, sha256=digest(source))
    # Some historical raw payloads were replaced upstream and deleted locally
    # (the code-meta reasoning source went from ten to thirty-six shards). The
    # tokenized receipts still record the exact input size; content equivalence
    # is then proven by verify-rows byte-comparing the conversions.
    task = task_meta.get(f'{friendly}__' + rel.replace('/', '__'))
    if task is None:
        raise ValueError(f'DFM9 source payload missing without a receipt: {path}')
    receipt = load(ROOT / 'data' / task['reference'] / 'metadata.json')
    return dict(bytes=int(receipt['source_size']), sha256=None,
                recovered='tokenized source receipt')


def resolve_revision(api, repo, digests):
    """Pin the newest revision whose locked files still match the historical sizes.

    Upstreams occasionally restructure their repositories (the code-meta
    reasoning source went from ten to thirty-six train shards); the DFM9
    conversion inputs are the historical payloads, so the pin must reproduce
    them rather than track main.
    """
    info = api.dataset_info(repo, files_metadata=True)
    revision = info.sha
    sizes = {s.rfilename: s.size for s in info.siblings if s.size is not None}
    if all(sizes.get(rel) == meta['bytes'] for rel, meta in digests.items()):
        return revision
    for commit in api.list_repo_commits(repo, repo_type='dataset'):
        info = api.dataset_info(repo, revision=commit.commit_id, files_metadata=True)
        sizes = {s.rfilename: s.size for s in info.siblings if s.size is not None}
        if all(sizes.get(rel) == meta['bytes'] for rel, meta in digests.items()):
            return commit.commit_id
    raise ValueError(f'{repo}: no Hub revision reproduces the historical DFM9 payloads')


def recover_lock(work):
    from huggingface_hub import HfApi
    dfm6 = load(QUEUE / 'dfm6/all-token-comparison.json')
    dfm7 = load(QUEUE / 'dfm7/verified.json')
    dfm8 = load(QUEUE / 'dfm8/verified.json')
    if (dfm6.get('status'), dfm7.get('status'), dfm8.get('status')) != ('matched',) * 3:
        raise ValueError('DFM9 requires verified DFM6/DFM7/DFM8 rebuild unions')
    table = load(LINK_TABLE)
    if len(table) != len({row['name'] for row in table}):
        raise ValueError('DFM9 link table has duplicate union names')
    live = {entry.name for entry in REFERENCE.iterdir()}
    if live != {row['name'] for row in table}:
        raise ValueError('DFM9 link table drifted from the historical union tree')
    base, tasks = [], []
    counts = {'dfm6': 0, 'dfm7': 0, 'dfm8': 0, 'new': 0, 'swe': 0, 'ext': 0}
    for row in table:
        name, root, rebuild = row['name'], row['root'], row['rebuild']
        text = os.readlink(REFERENCE / name)
        resolved = Path(text) if text.startswith('/') else (REFERENCE / text)
        resolved = resolved.resolve()
        tree = resolved.relative_to(ROOT / 'data').parts[0]
        expected_root = 'tokenized_dfm9_swe_windowed' if root == '..' else root
        if tree != expected_root:
            raise ValueError(f'{name}: link resolves under {tree}, table says {expected_root}')
        if rebuild in ('dfm6', 'dfm7', 'dfm8'):
            expected = row['expected']
            if not (BASE_TREES[rebuild] / expected).exists():
                raise ValueError(f'Rebuild tree lacks {rebuild}/{expected}')
            base.append([name, rebuild, expected])
            counts[rebuild] += 1
        elif rebuild == 'fresh_new':
            if row['target'] != name or not (NEW_REFERENCE / name / 'tokens.npy').exists():
                raise ValueError(f'Historical DFM9 addition missing: {name}')
            tasks.append(dict(task=name, mode='converted',
                              output=name.replace('__', '/', 2),
                              reference=f'tokenized_dfm9_new/{name}'))
            counts['new'] += 1
        elif rebuild == 'fresh_swe':
            marker = '/tokenized_dfm9_swe_windowed/'
            sub = text.split(marker, 1)[1]
            leaf = swe_task(sub)
            if not (SWE_REFERENCE / sub / 'tokens.npy').exists():
                raise ValueError(f'Historical DFM9 SWE addition missing: {sub}')
            if leaf == 'agentless.parquet':
                tasks.append(dict(task=f'nemotron_swe_windowed__{leaf}', mode='converted',
                                  output='nemotron_swe_windowed/data/agentless.parquet',
                                  reference=f'tokenized_dfm9_swe_windowed/{sub}'))
            else:
                group = int(leaf[len('merged_'):-len('.jsonl')])
                members = [f'nemotron_swe_windowed/data/shards/shard_{i:02d}.jsonl'
                           for i in range(SWE_GROUP_SIZE * group,
                                          SWE_GROUP_SIZE * (group + 1))]
                for rel in members:
                    if not (CONVERTED_SOURCES / rel).is_file():
                        raise ValueError(f'Historical SWE shard missing: {rel}')
                receipt = load(SWE_REFERENCE / sub / 'metadata.json')
                tasks.append(dict(task=f'nemotron_swe_windowed__{leaf}', mode='swe_merge',
                                  members=members, group=group,
                                  source_mtime=int(receipt['source_mtime']),
                                  source_size=int(receipt['source_size']),
                                  reference=f'tokenized_dfm9_swe_windowed/{sub}'))
            counts['swe'] += 1
        elif rebuild == 'fresh_ext':
            sub = row['target']
            if not (EXT_REFERENCE / sub / 'tokens.npy').exists():
                raise ValueError(f'Historical DFM9 extension missing: {sub}')
            tasks.append(dict(task=name, mode='converted',
                              output=name.replace('__', '/', 2),
                              reference=f'tokenized_dfm9_ext/{sub}'))
            counts['ext'] += 1
        else:
            raise ValueError(f'Unknown DFM9 link table rebuild kind: {rebuild}')
    if len(base) != len({x[0] for x in base}) or len(tasks) != len({x['task'] for x in tasks}):
        raise ValueError('DFM9 union link names are not unique')
    if {x['task'] for x in tasks} & {x[0] for x in base}:
        raise ValueError('DFM9 fresh tasks collide with the base inventory')
    if 'tokenizer_info.json' not in {x[0] for x in base} \
            or 'union_manifest.json' not in {x[0] for x in base}:
        raise ValueError('DFM9 union specials are not part of the base links')
    api = HfApi()
    acquisitions = {}
    task_meta = {x['task']: x for x in tasks}
    for friendly, repo in sorted(FRIENDLY_TO_REPO.items()):
        directory = FILTERED_ROOT / friendly if friendly in FILTERED_KIND \
            else DOWNLOADS / friendly
        if not directory.exists():
            raise ValueError(f'Historical DFM9 source directory missing: {directory}')
        files = frozen_tree_files(directory) if friendly in FILTERED_KIND \
            else frozen_download_files(directory)
        digests = {}
        recovery = RECOVERY_SOURCE.get(friendly)
        for rel, path in files.items():
            source = path.resolve()
            if not source.is_file() and recovery:
                fallback = DOWNLOADS / recovery / rel
                if fallback.is_file():
                    path = fallback
            digests[rel] = frozen_payload(work, friendly, rel, path, task_meta)
        revision = resolve_revision(api, repo, digests)
        if not revision:
            raise ValueError(f'{repo}: Hub did not resolve a main revision')
        main_sha = api.dataset_info(repo).sha
        note = '' if revision == main_sha else ' (historical revision; main moved)'
        acquisitions[repo] = dict(revision=revision, friendly=friendly,
                                  kind='filtered' if friendly in FILTERED_KIND else 'download',
                                  files=digests)
        print(f'Froze {repo} at {revision[:12]}{note} ({len(digests)} files)', flush=True)
    prefix = subprocess.check_output(
        ['git', 'show', DATA_IO_REVISION + ':prefix_config_dfm9.yaml'], cwd=ROOT / 'data_io')
    dfm8_cfg = load(ROOT / 'config/data/dfm8_hf_rebuild.json')
    composition = {'base_links': len(base), 'fresh_new': counts['new'],
                   'fresh_swe': counts['swe'], 'fresh_ext': counts['ext'],
                   'total_tasks': len(base) + len(tasks)}
    config = dict(version=9, recipe='dfm9-hf-v1', epochs=10, seed=0, concat_workers=4,
                  adapter_revision=ADAPTER_REVISION, template_revision=TEMPLATE_REVISION,
                  data_io_revision=DATA_IO_REVISION, converter_revision=CONVERTER_REVISION,
                  tokenizer_repo=dfm8_cfg['tokenizer_repo'],
                  tokenizer_revision=dfm8_cfg['tokenizer_revision'],
                  tokenizer_post_processor=dfm8_cfg['tokenizer_post_processor'],
                  tokenizer_semantic_sha256=dfm8_cfg['tokenizer_semantic_sha256'],
                  tokenizer_info=dfm8_cfg['tokenizer_info'],
                  prefix_config_sha256=hashlib.sha256(prefix).hexdigest(),
                  base=base, tasks=tasks, acquisitions=acquisitions,
                  composition=composition)
    write_json(CONFIG, config)
    print(f'Wrote {CONFIG}: {composition}', flush=True)


def acquire(work):
    from huggingface_hub import HfApi, snapshot_download
    cfg = load(CONFIG)
    api = HfApi()
    for repo, item in sorted(cfg['acquisitions'].items()):
        info = api.dataset_info(repo, revision=item['revision'])
        if info.sha != item['revision']:
            raise ValueError(f'{repo}: pinned commit no longer resolves')
        destination = acquisition_dir(work, repo, item['revision'])
        if not destination.exists():
            snapshot_download(repo_id=repo, repo_type='dataset', revision=item['revision'],
                              allow_patterns=sorted(item['files']),
                              local_dir=destination, cache_dir=work / 'hf-cache')
        for rel, meta in sorted(item['files'].items()):
            path = allowed(destination / rel, roots(work))
            if not path.is_file() or path.stat().st_size != meta['bytes'] \
                    or meta['sha256'] is not None and digest(path) != meta['sha256']:
                raise ValueError(f'{repo}/{rel}: payload differs from the historical copy')
        print(f'Acquired {repo} at {item["revision"][:12]}', flush=True)
    write_json(work / 'acquire-receipt.json', dict(
        status='downloaded', repos=len(cfg['acquisitions']),
        files=sum(len(x['files']) for x in cfg['acquisitions'].values()),
        basis='digest-verified historical local copies'))


def prepare(work):
    from huggingface_hub import hf_hub_download
    cfg = load(CONFIG)
    for name, receipt in (('dfm6', QUEUE / 'dfm6/all-token-comparison.json'),
                          ('dfm7', QUEUE / 'dfm7/verified.json'),
                          ('dfm8', QUEUE / 'dfm8/verified.json')):
        if load(receipt).get('status') != 'matched':
            raise ValueError(f'DFM{name} verification required')
    staged_prefix = work / 'prefix_config.yaml'
    staged_prefix.write_bytes(subprocess.check_output(
        ['git', 'show', DATA_IO_REVISION + ':prefix_config_dfm9.yaml'], cwd=ROOT / 'data_io'))
    if digest(staged_prefix) != cfg['prefix_config_sha256']:
        raise ValueError('Sampling policy changed')
    template = work / 'chat_template.jinja'
    template.write_bytes(subprocess.check_output(
        ['git', 'show', DATA_IO_REVISION + ':chat_templates/gemma4_native_chat.jinja'],
        cwd=ROOT / 'data_io'))
    if template.read_bytes() != subprocess.check_output(
            ['git', 'show', TEMPLATE_REVISION + ':chat_templates/gemma4_native_chat.jinja'],
            cwd=ROOT / 'data_io'):
        raise ValueError('Chat template changed between the pinned revisions')
    for repo, revision, rel, target in [
            (ROOT, cfg['adapter_revision'], 'scripts/tokenize_chat_template.py',
             'historical_adapter.py'),
            (ROOT, cfg['converter_revision'], 'scripts/convert_dfm9_new_sources.py',
             'scripts/convert_dfm9_new_sources.py'),
            (ROOT, cfg['converter_revision'], 'scripts/convert_nemotron_swe_windowed.py',
             'scripts/convert_nemotron_swe_windowed.py'),
            (ROOT, cfg['converter_revision'], 'scripts/convert_dfm9_extension.py',
             'scripts/convert_dfm9_extension.py')]:
        data = subprocess.check_output(['git', 'show', revision + ':' + rel], cwd=repo)
        path = work / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    tokenizer = Path(hf_hub_download(cfg['tokenizer_repo'], 'tokenizer.json',
                                     revision=cfg['tokenizer_revision'],
                                     local_dir=work / 'tokenizer_hf'))
    definition = load(tokenizer)
    definition['post_processor'] = cfg['tokenizer_post_processor']
    if semantic_digest(definition) != cfg['tokenizer_semantic_sha256']:
        raise ValueError('HF tokenizer vocabulary/normalization differs from historical DFM9')
    (work / 'tokenizer').mkdir(exist_ok=True)
    write_json(work / 'tokenizer/tokenizer.json', definition)
    (work / 'sources').mkdir(exist_ok=True)
    # The staged converters resolve REPO_ROOT from their own location and then
    # read REPO_ROOT/data/...; mirror the historical layout exactly and clear
    # any staging left by an earlier attempt.
    for stale in ('filtered_sources', 'downloads', 'data'):
        if (work / stale).exists():
            shutil.rmtree(work / stale)
    (work / 'data/filtered_sources').mkdir(parents=True, exist_ok=True)
    (work / 'data/downloads/datasets').mkdir(parents=True, exist_ok=True)
    checked = []
    for i, (repo, item) in enumerate(sorted(cfg['acquisitions'].items()), 1):
        destination = acquisition_dir(work, repo, item['revision'])
        for rel, meta in sorted(item['files'].items()):
            path = allowed(destination / rel, roots(work))
            if not path.is_file() or path.stat().st_size != meta['bytes'] \
                    or meta['sha256'] is not None and digest(path) != meta['sha256']:
                raise ValueError(f'Acquisition payload missing or changed: {repo}/{rel}')
        checked.append(dict(repo=repo, revision=item['revision'], files=len(item['files'])))
        if i % 3 == 0:
            print(f'Validated inputs {i}/{len(cfg["acquisitions"])}', flush=True)
    for repo, item in sorted(cfg['acquisitions'].items()):
        friendly = item['friendly']
        for rel in sorted(item['files']):
            link(acquisition_dir(work, repo, item['revision']) / rel,
                 work / ('data/filtered_sources' if item['kind'] == 'filtered'
                         else 'data/downloads/datasets') / friendly / rel, roots(work))
        if item['kind'] == 'download':
            (work / 'data/downloads/datasets' / friendly / '.complete').touch()
    write_json(work / 'inputs-verified.json', dict(inputs=checked, config_sha256=digest(CONFIG)))
    write_json(work / 'recipe.json', cfg)


SWE_SHARD_OFFSETS = (
    509214941, 1018417652, 1527631431, 2036835859, 2546036605, 3055254515,
    3564445832, 4073650955, 4582875088, 5092063235, 5601278244, 6110497029,
    6619695429, 7128903026, 7638094180, 8147310135, 8656512433, 9165720612,
    9674933192, 10184132626, 10693339413, 11202545132, 11711742817, 12220966660,
    12730172953, 13239390626, 13748590576, 14257777669, 14766987036, 15276190974,
    15785398598, 16294607916, 16803804730, 17313023290, 17822228884, 18331426540,
    18840629857, 19349849169, 19859044379, 20368262646, 20877455897, 21386691013,
    21895871993, 22405077185, 22914288930, 23423505397, 23932701412, 24441901281,
    24951103620, 25460340414, 25969526936, 26478737443, 26987930113, 27497135323,
    28006363757, 28515562245, 29024777226, 29533968075, 30043169215, 30552388078,
    31061581802, 31570794082, 32080002282,
)


def split_swe(work, offsets=SWE_SHARD_OFFSETS):
    source = work / 'data/converted_sources/nemotron_swe_windowed/data/swe.jsonl'
    out_dir = source.parent / 'shards'
    out_dir.mkdir(parents=True, exist_ok=True)
    bounds = (0,) + tuple(offsets) + (source.stat().st_size,)
    if len(bounds) < 2:
        raise ValueError('At least one shard boundary is required')
    with source.open('rb') as stream:
        for index, (start, end) in enumerate(zip(bounds, bounds[1:])):
            if end < start:
                raise ValueError(f'Shard {index} boundaries are not monotone')
            stream.seek(start)
            remaining = end - start
            with (out_dir / f'shard_{index:02d}.jsonl').open('wb') as out:
                while remaining:
                    chunk = stream.read(min(1 << 24, remaining))
                    if not chunk:
                        raise ValueError(f'Unexpected EOF in shard {index}')
                    out.write(chunk)
                    remaining -= len(chunk)
    write_json(work / 'split-swe-receipt.json',
               dict(status='split', shards=len(bounds) - 1))


def convert(work):
    cfg = load(CONFIG)
    if digest(CONFIG) != load(work / 'inputs-verified.json')['config_sha256']:
        raise ValueError('DFM9 input lock changed')
    converted = work / 'data' / 'converted_sources'
    if converted.exists():
        shutil.rmtree(converted)
    for item in cfg['acquisitions'].values():
        if item['kind'] != 'filtered':
            continue
        staged = work / 'data/filtered_sources' / item['friendly']
        if not any(staged.iterdir()):
            raise ValueError(f'Staged filtered tree is empty: {staged}')
    for script in ('convert_dfm9_new_sources.py', 'convert_nemotron_swe_windowed.py',
                   'convert_dfm9_extension.py'):
        subprocess.run([sys.executable, str(work / 'scripts' / script)],
                       check=True, env=converter_env(), cwd=work)
        print(f'Ran {script}', flush=True)
    split_swe(work)
    sources = work / 'sources'
    if sources.exists():
        shutil.rmtree(sources)
    sources.mkdir()
    for item in cfg['tasks']:
        outputs = item['members'] if item['mode'] == 'swe_merge' else [item['output']]
        for rel in outputs:
            path = allowed(converted / rel, roots(work))
            if not path.is_file():
                raise ValueError(f'Missing conversion output: {rel}')
            name = swe_shard_internal(rel) if item['mode'] == 'swe_merge' else item['task']
            link(path, work / 'sources' / name, roots(work))
    write_json(work / 'convert-receipt.json', dict(
        status='converted',
        files=sum(len(x['members']) if x['mode'] == 'swe_merge' else 1
                  for x in cfg['tasks'])))


def compare_parquet(generated, historical, rel):
    import pyarrow.parquet as pq
    if digest(generated) == digest(historical):
        return
    left = pq.read_table(generated)
    right = pq.read_table(historical)
    if not left.equals(right, check_metadata=False):
        raise ValueError(f'{rel}: converted parquet differs from the historical copy')


def verify_rows(work):
    cfg = load(CONFIG)
    total = sum(len(x['members']) if x['mode'] == 'swe_merge' else 1
                for x in cfg['tasks'])
    done = 0
    for item in cfg['tasks']:
        outputs = item['members'] if item['mode'] == 'swe_merge' else [item['output']]
        for rel in outputs:
            generated = allowed(work / 'data' / 'converted_sources' / rel, roots(work))
            historical = allowed(ROOT / 'data/converted_sources' / rel, [ROOT])
            if not historical.is_file():
                raise ValueError(f'Missing historical conversion: {rel}')
            if generated.suffix == '.parquet':
                compare_parquet(generated, historical, rel)
            else:
                compare_jsonl(generated, historical)
            done += 1
            if done % 100 == 0:
                print(f'Rows matched {done}/{total}', flush=True)
    write_json(work / 'converted-comparison.json', dict(
        status='matched', converted_files=total,
        method='byte-equality with content fallback'))


def tokenizer_command(work, source, output, workers):
    return [sys.executable, str(ROOT / 'scripts/tokenize_historical_chat.py'),
            '--input', str(source), '--output', str(output),
            '--adapter', str(work / 'historical_adapter.py'),
            '--tokenizer', str(work / 'tokenizer/tokenizer.json'),
            '--template', str(work / 'chat_template.jinja'), '--workers', str(workers)]


def swe_shard_internal(rel):
    return 'swe_shard_' + rel.rsplit('/', 1)[-1].removeprefix('shard_')


def merge_swe_group(work, item):
    member_dirs = [work / 'tokenized' / swe_shard_internal(m) for m in item['members']]
    out = work / 'tokenized' / item['task']
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    tokens_len = 0
    rows = 0
    for d in member_dirs:
        tokens_len += len(np.load(d / 'tokens.npy', mmap_mode='r'))
        rows += len(np.load(d / 'inst_start.npy', mmap_mode='r'))
    tokens = np.lib.format.open_memmap(out / 'tokens.npy', mode='w+',
                                       dtype=np.uint32, shape=(tokens_len,))
    starts = {f: np.lib.format.open_memmap(out / f'{f}.npy', mode='w+', dtype=np.uint64,
                                           shape=(rows,))
              for f in ('inst_start', 'resp_start')}
    lens = {f: np.lib.format.open_memmap(out / f'{f}.npy', mode='w+', dtype=np.uint64,
                                         shape=(rows,))
            for f in ('inst_len', 'resp_len')}
    tok_off = 0
    row_off = 0
    for d in member_dirs:
        t = np.load(d / 'tokens.npy', mmap_mode='r')
        base = tok_off
        tokens[base:base + len(t)] = t[:]
        tok_off += len(t)
        for f in ('inst_start', 'resp_start'):
            s = np.load(d / f'{f}.npy', mmap_mode='r')
            starts[f][row_off:row_off + len(s)] = s[:] + base
        for f in ('inst_len', 'resp_len'):
            v = np.load(d / f'{f}.npy', mmap_mode='r')
            lens[f][row_off:row_off + len(v)] = v[:]
        row_off += len(s)
    for array in (tokens, *starts.values(), *lens.values()):
        array.flush()
    write_json(out / 'metadata.json', dict(source_mtime=item['source_mtime'],
                                           source_size=item['source_size']))
    for d in member_dirs:
        shutil.rmtree(d)


def tokenize(work):
    from scripts.queue_dfm_hf_rebuild import safe_tokenizer_workers
    cfg = load(CONFIG)
    if digest(CONFIG) != load(work / 'inputs-verified.json')['config_sha256']:
        raise ValueError('DFM9 input lock changed')
    expected_sources = set()
    for item in cfg['tasks']:
        if item['mode'] == 'swe_merge':
            expected_sources.update(swe_shard_internal(m) for m in item['members'])
        else:
            expected_sources.add(item['task'])
    if {x.name for x in (work / 'sources').iterdir()} != expected_sources:
        raise ValueError('Unexpected DFM9 source inventory')
    subprocess.run(tokenizer_command(work, work / 'sources', work / 'tokenized',
                                     safe_tokenizer_workers()), check=True)
    for item in cfg['tasks']:
        if item['mode'] == 'swe_merge' \
                and not (work / 'tokenized' / item['task']).exists():
            merge_swe_group(work, item)
    tokenized = {x.name for x in (work / 'tokenized').iterdir() if x.is_dir()}
    if tokenized != {x['task'] for x in cfg['tasks']}:
        raise ValueError('Tokenized DFM9 additions differ from the locked inventory')
    write_json(work / 'tokenized/tokenizer_info.json', cfg['tokenizer_info'])


def assemble(work):
    cfg = load(CONFIG)
    if digest(CONFIG) != load(work / 'inputs-verified.json')['config_sha256']:
        raise ValueError('DFM9 input lock changed')
    if (work / 'tokenized/tokenizer_info.json').read_bytes().rstrip(b'\n') != \
            (REFERENCE / 'tokenizer_info.json').read_bytes().rstrip(b'\n'):
        raise ValueError('Fresh tokenizer info differs from the historical DFM9 union')
    union = work / 'union'
    if union.exists():
        shutil.rmtree(union)
    union.mkdir(parents=True)
    for name, tree, expected in cfg['base']:
        target = union / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to((BASE_TREES[tree] / expected).resolve())
    for item in cfg['tasks']:
        target = union / item['task']
        if target.exists() or target.is_symlink():
            raise ValueError(f'Union collision: {item["task"]}')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to((work / 'tokenized' / item['task']).resolve())
    produced = {p.name for p in union.iterdir() if p.is_dir()}
    wanted = {p.name for p in REFERENCE.iterdir() if p.is_dir()}
    if produced != wanted:
        raise ValueError('Union task inventory differs from historical DFM9')
    write_json(work / 'assemble-receipt.json', dict(
        status='assembled', base=cfg['composition']['base_links'],
        additions=len(cfg['tasks']), total_tasks=len(wanted)))


def verify(work):
    cfg = load(CONFIG)
    if digest(CONFIG) != load(work / 'inputs-verified.json')['config_sha256']:
        raise ValueError('DFM9 input lock changed')
    union = work / 'union'
    for item in cfg['tasks']:
        reference = allowed(ROOT / 'data' / item['reference'], [ROOT])
        for field in FIELDS:
            equal_arrays(np.load(union / item['task'] / f'{field}.npy', mmap_mode='r'),
                         np.load(reference / f'{field}.npy', mmap_mode='r'),
                         item['task'] + '/' + field)
    print(f'Compared {len(cfg["tasks"])} fresh tasks against the historical arrays',
          flush=True)
    write_json(work / 'all-token-comparison.json', dict(
        status='matched', tasks=len(cfg['tasks']),
        inventory=cfg['composition']['total_tasks'],
        scope='fresh additions plus base links verified in DFM6/DFM7/DFM8 receipts'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('recover-lock', 'acquire', 'prepare', 'convert',
                                     'split-swe', 'verify-rows', 'tokenize', 'assemble',
                                     'verify'))
    p.add_argument('--work', type=Path, required=True)
    args = p.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    with (args.work / 'stage.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        {'recover-lock': recover_lock, 'acquire': acquire, 'prepare': prepare,
         'convert': convert, 'split-swe': split_swe, 'verify-rows': verify_rows,
         'tokenize': tokenize, 'assemble': assemble, 'verify': verify}[args.stage](args.work)


if __name__ == '__main__':
    main()
