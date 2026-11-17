#!/usr/bin/env python3
"""Rebuild DFM11 pretrain data in the guarded HF-only serial rebuild queue.

The DFM11 union is the verified DFM10 union minus thirteen replaced
native-tool-use/folketing tasks plus 290 isolated replacement tasks tokenized
from eleven pinned public packages. The historical additions pipeline is
committed as ``scripts/tokenize_dfm11_from_hub.py``: it downloads the pinned
revisions, derives the three FineInstructions families deterministically, and
tokenizes the staging tree with the September-5 adapter state. The union is
assembled by the committed DFM11 builder.
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
from scripts.rebuild_dfm9 import FIELDS
from scripts.replay_dfm_serial import equal_arrays, write_json

QUEUE = ROOT / 'data/rebuild_hf_dfm/serial-queue'
CONFIG = ROOT / 'config/data/dfm11_hf_rebuild.json'
ADAPTER_REVISION = 'f9b588f'         # adapter state at the historical DFM11 tokenization
DRIVER_REVISION = '4022697'          # committed additions rebuild driver
BUILDER_REVISION = 'bc1e181'         # committed union builder + FineInstructions helpers
TEMPLATE_REVISION = 'e9584e0'        # chat template with mapping-valued tool responses
DATA_IO_REVISION = 'cfe0d19'         # data_io commit matching prefix_config_dfm11.yaml
REFERENCE = ROOT / 'data/tokenized_dfm11'
ADDITIONS_REFERENCE = ROOT / 'data/tokenized_dfm11_additions'
CONVERTED_REFERENCE = ROOT / 'data/converted_dfm11_hub'
BASE_UNION = QUEUE / 'dfm10-hf-v2/union'
BASE_INVENTORY = ROOT / 'data/tokenized_dfm10'
CONFIG_GROUPS = ('tool_replacements', 'mathagentic', 'koolbardi',
                 'fineinstructions_english', 'fineinstructions_danish')
# The three FineInstructions families are re-derived from the pinned packages
# on every run; the other staging families are byte-deterministic snapshots.
DERIVED_FAMILIES = ('dfm11-fineinstructions-da',
                    'dfm11-fineinstructions-en-controlled',
                    'dfm11-fineinstructions-en-legacy-balanced')
REPLACED_PREFIXES = ('glaive_native_tool_use__', 'dfm10-glaive-native-tool-use__',
                     'toolace_native_tool_use__', 'dfm10-toolace-native-tool-use__',
                     'nemotron_agentic__data__tool_calling',
                     'dfm8-synthetic-native-tool-calling__',
                     'dfm8_synthetic_native_tool_calling__',
                     'folketingets-dokumenter-error-correction__')


def roots(work):
    return [work.parent, work]


def digest_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 24), b''):
            h.update(chunk)
    return h.hexdigest()


def family_of(task):
    family, sep, rel = task.partition('__data__')
    if not sep:
        raise ValueError(f'Unexpected DFM11 addition task name: {task}')
    return family, 'data/' + rel


def source_packages():
    import yaml
    packages = {}
    for group in CONFIG_GROUPS:
        path = ROOT / f'config/data/dfm11_{group}.yaml'
        config = yaml.safe_load(path.read_text())
        sources = config.get('sources') or {'source': config['source']}
        for name, source in sources.items():
            repo = source['repo_id']
            if repo in packages:
                raise ValueError(f'DFM11 package listed twice: {repo}')
            packages[repo] = dict(group=group, name=repo.split('/')[-1],
                                  revision=source['revision'])
    return packages


def recover_lock(work, planning=False):
    if not planning:
        from scripts.dfm_hf_gate import require_dfm10
        require_dfm10(QUEUE)
    for version in (9,):
        state = load(QUEUE / f'dfm{version}/verified.json')
        if state.get('status') != 'matched':
            raise ValueError(f'DFM11 requires a verified DFM{version} rebuild union')
    packages = source_packages()
    from huggingface_hub import HfApi, hf_hub_download
    api = HfApi()
    acquisitions = {}
    for repo, item in sorted(packages.items()):
        info = api.dataset_info(repo, revision=item['revision'], files_metadata=True)
        if info.sha != item['revision']:
            raise ValueError(f'Unresolved pinned revision: {repo}')
        files = {}
        for blob in info.siblings:
            rel = blob.rfilename
            if Path(rel).is_absolute() or '..' in Path(rel).parts:
                raise ValueError(f'Unsafe HF package path: {rel}')
            if blob.lfs is not None:
                sha = blob.lfs.sha256
            else:
                path = Path(hf_hub_download(repo, rel, repo_type='dataset',
                    revision=item['revision'], local_dir=work / 'lock-metadata' / item['name']))
                sha = digest_file(path)
            files[rel] = dict(bytes=blob.size, sha256=sha)
        if not files:
            raise ValueError(f'Empty pinned HF package: {repo}')
        acquisitions[repo] = dict(revision=item['revision'], files=files)
        print(f'Pinned {repo} at {item["revision"][:12]} ({len(files)} files)', flush=True)
    tasks = []
    for task_dir in sorted(ADDITIONS_REFERENCE.iterdir()):
        if not (task_dir / 'metadata.json').is_file():
            continue
        family, rel = family_of(task_dir.name)
        if family in DERIVED_FAMILIES:
            package = None
        else:
            matches = [repo for repo in acquisitions
                       if repo.split('/')[-1] == family]
            if len(matches) != 1:
                raise ValueError(f'{task_dir.name}: no unique DFM11 source package')
            package = matches[0]
        tasks.append(dict(task=task_dir.name, family=family, rel=rel,
                          source_package=package,
                          reference='data/tokenized_dfm11_additions/' + task_dir.name))
    if len(tasks) != 290 or len({x['task'] for x in tasks}) != len(tasks):
        raise ValueError(f'DFM11 additions inventory mismatch: {len(tasks)} tasks')
    replaced = sum(1 for entry in BASE_INVENTORY.iterdir()
                   if entry.is_dir() and entry.name.startswith(REPLACED_PREFIXES))
    base_tasks = sum(1 for entry in BASE_INVENTORY.iterdir()
                     if entry.is_dir() and (entry / 'metadata.json').is_file())
    composition = {'base_entries': base_tasks + 2, 'replaced_base': replaced,
                   'base_tasks': base_tasks - replaced, 'addition_tasks': len(tasks),
                   'total_tasks': base_tasks - replaced + len(tasks) + 2}
    if composition['total_tasks'] != len([x for x in REFERENCE.iterdir()]):
        raise ValueError('DFM11 composition differs from the historical union size')
    config_group_sha256 = {group: digest(ROOT / f'config/data/dfm11_{group}.yaml')
                           for group in CONFIG_GROUPS}
    dfm9_cfg = load(ROOT / 'config/data/dfm9_hf_rebuild.json')
    prefix = subprocess.check_output(
        ['git', 'show', DATA_IO_REVISION + ':prefix_config_dfm11.yaml'],
        cwd=ROOT / 'data_io')
    config = dict(version=11, recipe='dfm11-hf-v1', epochs=10, seed=0, concat_workers=4,
                  adapter_revision=ADAPTER_REVISION, driver_revision=DRIVER_REVISION,
                  builder_revision=BUILDER_REVISION, template_revision=TEMPLATE_REVISION,
                  data_io_revision=DATA_IO_REVISION,
                  tokenizer_repo=dfm9_cfg['tokenizer_repo'],
                  tokenizer_revision=dfm9_cfg['tokenizer_revision'],
                  tokenizer_post_processor=dfm9_cfg['tokenizer_post_processor'],
                  tokenizer_semantic_sha256=dfm9_cfg['tokenizer_semantic_sha256'],
                  tokenizer_info=dfm9_cfg['tokenizer_info'],
                  prefix_config_sha256=hashlib.sha256(prefix).hexdigest(),
                  config_group_sha256=config_group_sha256,
                  base_union='data/rebuild_hf_dfm/serial-queue/dfm10-hf-v2/union',
                  tasks=tasks, acquisitions=acquisitions, composition=composition)
    write_json(CONFIG, config)
    print(f'Wrote {CONFIG}: {composition}', flush=True)


def check_config(work):
    cfg = load(CONFIG)
    if digest(CONFIG) != load(work / 'inputs-verified.json')['config_sha256']:
        raise ValueError('DFM11 input lock changed')
    return cfg


def git_show(repo, revision, rel):
    return subprocess.check_output(['git', 'show', revision + ':' + rel], cwd=repo)


def stage_tokenizer(work, cfg):
    from huggingface_hub import hf_hub_download
    tokenizer = Path(hf_hub_download(cfg['tokenizer_repo'], 'tokenizer.json',
                                     revision=cfg['tokenizer_revision'],
                                     local_dir=work / 'tokenizer_hf'))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'rebuild_dfm7_semantic', ROOT / 'scripts/rebuild_dfm7.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    definition = load(tokenizer)
    definition['post_processor'] = cfg['tokenizer_post_processor']
    if module.semantic_digest(definition) != cfg['tokenizer_semantic_sha256']:
        raise ValueError('HF tokenizer vocabulary/normalization differs from historical DFM11')
    (work / 'tokenizer').mkdir(exist_ok=True)
    write_json(work / 'tokenizer/tokenizer.json', definition)


def prepare(work):
    cfg = check_config(work) if (work / 'inputs-verified.json').exists() else load(CONFIG)
    from scripts.dfm_hf_gate import require_dfm10
    predecessor = require_dfm10(QUEUE)
    if load(work / 'acquire-receipt.json')['status'] != 'downloaded':
        raise ValueError('DFM11 HF acquisition is incomplete')
    for version in (9,):
        if load(QUEUE / f'dfm{version}/verified.json').get('status') != 'matched':
            raise ValueError(f'DFM{version} verification required for DFM11')
    if not (BASE_UNION / 'tokenizer_info.json').is_file():
        raise ValueError('The rebuilt DFM10 union is missing')
    data_io = ROOT / 'data_io'
    staged_prefix = work / 'prefix_config.yaml'
    staged_prefix.write_bytes(git_show(data_io, DATA_IO_REVISION,
                                       'prefix_config_dfm11.yaml'))
    if digest(staged_prefix) != cfg['prefix_config_sha256']:
        raise ValueError('Sampling policy changed')
    template = work / 'chat_template.jinja'
    template.write_bytes(git_show(data_io, DATA_IO_REVISION,
                                  'chat_templates/gemma4_native_chat.jinja'))
    if template.read_bytes() != git_show(data_io, TEMPLATE_REVISION,
                                         'chat_templates/gemma4_native_chat.jinja'):
        raise ValueError('Chat template changed between the pinned revisions')
    for group in CONFIG_GROUPS:
        target = work / 'config/data' / f'dfm11_{group}.yaml'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / f'config/data/dfm11_{group}.yaml').read_bytes())
        if digest(target) != cfg['config_group_sha256'][group]:
            raise ValueError(f'DFM11 config changed: dfm11_{group}.yaml')
    scripts_dir = work / 'scripts'
    scripts_dir.mkdir(exist_ok=True)
    for revision, source_rel, target in [
            (cfg['driver_revision'], 'scripts/tokenize_dfm11_from_hub.py',
             'tokenize_dfm11_from_hub.py'),
            (cfg['adapter_revision'], 'scripts/tokenize_chat_template.py',
             'tokenize_chat_template.py'),
            (cfg['builder_revision'], 'scripts/prepare_dfm11_fineinstructions_english.py',
             'prepare_dfm11_fineinstructions_english.py'),
            (cfg['builder_revision'], 'scripts/build_tokenized_dfm11_tree.py',
             'build_tokenized_dfm11_tree.py')]:
        (scripts_dir / target).write_bytes(git_show(ROOT, revision, source_rel))
    stage_tokenizer(work, cfg)
    # The committed driver reads the tokenizer/template locations from this
    # file; it is a staging pointer, not a verification artifact.
    driver_info = dict(cfg['tokenizer_info'])
    driver_info['tokenizer_path'] = str(work / 'tokenizer/tokenizer.json')
    driver_info['chat_template_path'] = str(work / 'chat_template.jinja')
    (work / 'data/tokenized_dfm10').mkdir(parents=True, exist_ok=True)
    write_json(work / 'data/tokenized_dfm10/tokenizer_info.json', driver_info)
    for stale in ('exports_dfm11', 'data/converted_dfm11_hub',
                  'data/tokenized_dfm11_additions', 'union'):
        if (work / stale).exists():
            shutil.rmtree(work / stale)
    (work / 'exports_dfm11').mkdir()
    for repo, item in sorted(cfg['acquisitions'].items()):
        name = repo.split('/')[-1]
        destination = work / 'exports_dfm11' / name
        destination.mkdir()
        source = work / 'acquisitions' / (repo.replace('/', '--') + '--'
                                          + item['revision'][:12])
        for rel in item['files']:
            target = destination / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(allowed(source / rel, roots(work)), target)
    (work / 'data/converted_dfm11_hub').mkdir(parents=True, exist_ok=True)
    write_json(work / 'inputs-verified.json', dict(
        inputs=len(cfg['acquisitions']), config_sha256=digest(CONFIG),
        predecessor=predecessor))
    write_json(work / 'recipe.json', cfg)


def acquire(work):
    from huggingface_hub import HfApi, snapshot_download
    cfg = load(CONFIG)
    api = HfApi()
    for repo, item in sorted(cfg['acquisitions'].items()):
        info = api.dataset_info(repo, revision=item['revision'])
        if info.sha != item['revision']:
            raise ValueError(f'{repo}: pinned commit no longer resolves')
        destination = work / 'acquisitions' / (repo.replace('/', '--')
                                               + '--' + item['revision'][:12])
        # Resume partial downloads; a directory is not a completion receipt.
        snapshot_download(repo_id=repo, repo_type='dataset',
                          revision=item['revision'],
                          allow_patterns=sorted(item['files']),
                          local_dir=destination, cache_dir=work / 'hf-cache', max_workers=4)
        for rel, meta in sorted(item['files'].items()):
            path = allowed(destination / rel, roots(work))
            if not path.is_file() or path.stat().st_size != meta['bytes'] \
                    or digest(path) != meta['sha256']:
                raise ValueError(f'{repo}/{rel}: payload differs from the pinned copy')
        print(f'Acquired {repo} at {item["revision"][:12]}', flush=True)
    write_json(work / 'acquire-receipt.json', dict(
        status='downloaded', repos=len(cfg['acquisitions']),
        files=sum(len(x['files']) for x in cfg['acquisitions'].values()),
        basis='digest-verified pinned public packages'))


def convert(work):
    from scripts.queue_dfm_hf_rebuild import safe_tokenizer_workers
    cfg = check_config(work)
    subprocess.run([sys.executable, str(work / 'scripts/tokenize_dfm11_from_hub.py'),
                    '--workers', str(safe_tokenizer_workers())],
                   check=True, cwd=work)
    additions = work / 'data/tokenized_dfm11_additions'
    tokenized = {x.name for x in additions.iterdir() if x.is_dir()}
    if tokenized != {x['task'] for x in cfg['tasks']}:
        raise ValueError('Tokenized DFM11 additions differ from the locked inventory')
    write_json(additions / 'tokenizer_info.json', cfg['tokenizer_info'])
    write_json(work / 'convert-receipt.json', dict(
        status='converted', tasks=len(cfg['tasks']),
        families=len({x['family'] for x in cfg['tasks']}),
        derived_families=len(DERIVED_FAMILIES)))


def compare_shard_content(generated, historical, label):
    import gzip
    generated_sha = hashlib.sha256()
    with gzip.open(generated, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 24), b''):
            generated_sha.update(chunk)
    historical_sha = hashlib.sha256()
    with gzip.open(historical, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 24), b''):
            historical_sha.update(chunk)
    if generated_sha.hexdigest() != historical_sha.hexdigest():
        raise ValueError(f'DFM11 derived shard differs: {label}')


def verify_rows(work):
    cfg = load(CONFIG)
    families = sorted({x['family'] for x in cfg['tasks']})
    if len(families) != 12:
        raise ValueError('Unexpected DFM11 family inventory')
    staged = work / 'data/converted_dfm11_hub'
    checked = 0
    for family in families:
        generated = staged / family
        historical = (CONVERTED_REFERENCE / family).resolve(strict=True)
        if not historical.is_dir():
            raise ValueError(f'Missing historical DFM11 conversion: {family}')
        generated_files = sorted(p.relative_to(generated).as_posix()
                                 for p in generated.rglob('*') if p.is_file() and not any(part.startswith('.') for part in p.relative_to(generated).parts))
        historical_files = sorted(p.relative_to(historical).as_posix()
                                  for p in historical.rglob('*') if p.is_file() and not any(part.startswith('.') for part in p.relative_to(historical).parts))
        if generated_files != historical_files:
            raise ValueError(f'DFM11 shard inventory differs: {family}')
        for rel in generated_files:
            if family in DERIVED_FAMILIES:
                compare_shard_content(generated / rel, historical / rel,
                                      f'{family}/{rel}')
            elif digest_file(generated / rel) != digest_file(historical / rel):
                raise ValueError(f'DFM11 converted shard differs: {family}/{rel}')
            checked += 1
    write_json(work / 'converted-comparison.json', dict(
        status='matched', families=len(families), files=checked,
        method='byte-equality for snapshots, decompressed-content equality '
               'for derived FineInstructions shards'))


def assemble(work):
    cfg = check_config(work)
    union = work / 'union'
    subprocess.run([sys.executable, str(work / 'scripts/build_tokenized_dfm11_tree.py'),
                    '--base', str(BASE_UNION),
                    '--additions', str(work / 'data/tokenized_dfm11_additions'),
                    '--output', str(union)], check=True, cwd=work)
    produced = {x.name for x in union.iterdir() if x.is_dir()}
    wanted = {x.name for x in REFERENCE.iterdir() if x.is_dir()}
    if produced != wanted:
        raise ValueError('Union task inventory differs from historical DFM11')
    manifest = load(union / 'union_manifest.json')
    if manifest['counts'] != {'base_kept': cfg['composition']['base_tasks'],
                              'base_replaced': cfg['composition']['replaced_base'],
                              'additions': cfg['composition']['addition_tasks']}:
        raise ValueError('DFM11 union manifest counts differ from the lock')
    write_json(work / 'assemble-receipt.json', dict(
        status='assembled', base_tasks=cfg['composition']['base_tasks'],
        additions=cfg['composition']['addition_tasks'],
        total_tasks=cfg['composition']['total_tasks']))


def verify(work):
    cfg = check_config(work)
    union = work / 'union'
    for i, item in enumerate(cfg['tasks'], 1):
        reference = (ROOT / item['reference']).resolve(strict=True)
        allowed(union / item['task'], roots(work))
        for field in FIELDS:
            equal_arrays(np.load(union / item['task'] / f'{field}.npy', mmap_mode='r'),
                         np.load(reference / f'{field}.npy', mmap_mode='r'),
                         item['task'] + '/' + field)
        if i % 100 == 0:
            print(f'Compared DFM11 additions {i}/{len(cfg["tasks"])}', flush=True)
    write_json(work / 'all-token-comparison.json', dict(
        status='matched', tasks=len(cfg['tasks']),
        inventory=cfg['composition']['total_tasks'],
        scope='fresh additions plus the DFM10 base verified in the DFM10 receipt'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('plan-lock', 'recover-lock', 'acquire', 'prepare', 'convert',
                                     'verify-rows', 'assemble', 'verify'))
    p.add_argument('--work', type=Path, required=True)
    args = p.parse_args()
    if args.stage != 'plan-lock':
        from scripts.dfm_hf_gate import require_dfm10
        require_dfm10(QUEUE)
    args.work.mkdir(parents=True, exist_ok=True)
    with (args.work / 'stage.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        {'plan-lock': lambda work: recover_lock(work, planning=True), 'recover-lock': recover_lock, 'acquire': acquire, 'prepare': prepare,
         'convert': convert, 'verify-rows': verify_rows, 'assemble': assemble,
         'verify': verify}[args.stage](args.work)


if __name__ == '__main__':
    main()
