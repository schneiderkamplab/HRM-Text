#!/usr/bin/env python3
"""Rebuild DFM8 pretrain data in the guarded HF-only serial rebuild queue.

The DFM8 union is the verified DFM7 union plus 69 chat additions: seven
locally converted special sources (giannor TV2R instruction, kobprof
SkoleGPT-Instruct) and 62 published HF files (repaired OpenHermes EN/DA and
six targeted synthetic families). The synthetic/repair generations were
sampling-temperature model runs and are not bit-reproducible; the published
Hub commits pinned below are their frozen provenance.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
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

# The DFM8 tokenization (2026-07-14) ran with the then-uncommitted adapter that
# cd88c93 later recorded (same adapter state family as the DFM7 re-pin).
ADAPTER_REVISION = 'cd88c93'
CONVERTER_REVISION = 'cd88c93'
DATA_IO_REVISION = '0483afe'
CONFIG = ROOT / 'config/data/dfm8_hf_rebuild.json'
QUEUE = ROOT / 'data/rebuild_hf_dfm/serial-queue'
BASE = QUEUE / 'dfm7/union'
REFERENCE = ROOT / 'data/tokenized_dfm8'
ADDITION_REFERENCE = ROOT / 'data/tokenized_dfm8_jinja'
SPECIAL_REFERENCE = ROOT / 'data/dfm8_special_sources'
LATER = ROOT / 'data/rebuild_hf_dfm/later-acquisition'
DFM7_CONFIG = ROOT / 'config/data/dfm7_hf_rebuild.json'
FIELDS = ('tokens', 'inst_start', 'inst_len', 'resp_start', 'resp_len')
# Python-literal tool-call arguments can parse into sets whose json_safe()
# iteration order depends on PYTHONHASHSEED; pin the historical seed for every
# frozen converter invocation.
CONVERSION_HASH_SEED = '2'

# Historical upload commits (wiki/pages/dfm8-plan/dfm8-synthetic-openhermes-pipeline-status.md
# and wiki/pages/dfm8-plan/hugging-face-availability.md).
HF_ADDITIONS = {
    'schneiderkamplab/dfm8-openhermes-en': '157a1488d453aef9e827bddabc77d78c0bfd57ef',
    'schneiderkamplab/dfm8-openhermes-da': 'a9458057e49c84561b5c75495a3d0400614df1ba',
    'schneiderkamplab/dfm8-synthetic-code-debugging': '87e99f9815c1c4b484fecb4485a24e5c18277b1b',
    'schneiderkamplab/dfm8-synthetic-constrained-format-following': '61850112550ef6631d04f89eb575b7bddc80cbd2',
    'schneiderkamplab/dfm8-synthetic-danish-summarization-rewrite-controls': '3b528aa7510d3a7a5fea22a2b33e89b1a1a0d09c',
    'schneiderkamplab/dfm8-synthetic-multiturn-danish-english-chat': 'e345d051a5d8714975de3bb19b137e357d76d92c',
    'schneiderkamplab/dfm8-synthetic-native-tool-calling': '3c2d177835beb79749a45143fd250fcedad5a6c9',
    'schneiderkamplab/dfm8-synthetic-strict-math-answer-contract': '14ff86ffae606f6dee4e959d0a4fe2c5a3b5c1bd',
}
SPECIAL_ACQUISITIONS = {
    'giannor/dala_tv2r_it': '9976093cd4a6d6ee126d6389a267019e361a841c',
    'giannor/gec_dala_tv2r_it': '308570cc643b1d4d2ab9ba2771a0093764838003',
    'kobprof/skolegpt-instruct': 'c6152f131033494a9e6ef044ff5626900296ab4c',
}
FRIENDLY_TO_REPO = {
    'giannor_dala_tv2r_it': 'giannor/dala_tv2r_it',
    'giannor_gec_dala_tv2r_it': 'giannor/gec_dala_tv2r_it',
    'kobprof_skolegpt_instruct': 'kobprof/skolegpt-instruct',
}
CONVERSION_GROUPS = {
    'giannor_tv2r_instruction': {'files': {
        'giannor_tv2r_instruction/giannor_dala_tv2r_it/test.jsonl': 147618,
        'giannor_tv2r_instruction/giannor_dala_tv2r_it/train.jsonl': 787300,
        'giannor_tv2r_instruction/giannor_dala_tv2r_it/validation.jsonl': 49208,
        'giannor_tv2r_instruction/giannor_gec_dala_tv2r_it/test.jsonl': 139585,
        'giannor_tv2r_instruction/giannor_gec_dala_tv2r_it/train.jsonl': 744475,
        'giannor_tv2r_instruction/giannor_gec_dala_tv2r_it/validation.jsonl': 46505}},
    'kobprof_skolegpt_instruct': {'files': {
        'kobprof_skolegpt_instruct/train-00000.jsonl': 21580}},
}
# Raw wrapper prefix -> local reference root for hashing the historical copies.
WRAPPER_ROOTS = {
    'export-upload-dfm8-openhermes-repaired__': ROOT / 'export-upload-dfm8-openhermes-repaired',
    'export-upload-dfm8-synthetic__': ROOT / 'export-upload-dfm8-synthetic',
}
# Mirrors selected_name() in build_tokenized_dfm8_tree.py (cd88c93).
SPECIAL_WRAPPER = 'dfm8_special_sources__'
EXPORT_UPLOAD_STRIP_PREFIXES = ('common-pile-', 'danish-dynaword-', 'transformations-')
EXPECTED_COMPOSITION = {'base_selected_tasks': 10651, 'dfm8_selected_tasks': 69,
                        'duplicate_skipped_tasks': 1357, 'skipped_tasks': 2600}


def converter_env():
    return dict(os.environ, PYTHONHASHSEED=CONVERSION_HASH_SEED)


def roots(work):
    return [work.parent, LATER / 'downloads']


def stripped_name(raw_name):
    if raw_name.startswith(SPECIAL_WRAPPER):
        return raw_name.removeprefix(SPECIAL_WRAPPER)
    for wrapper in WRAPPER_ROOTS:
        if raw_name.startswith(wrapper):
            name = raw_name.removeprefix(wrapper)
            if name.startswith(('dfm8-synthetic-', 'dfm8-openhermes-en__', 'dfm8-openhermes-da__')):
                return name
    return None


def dfm7_union_name(raw_name):
    return (raw_name.removeprefix('dfm7_special_sources__')
            if raw_name.startswith('dfm7_special_sources__') else raw_name)


def task_repo_rel(raw_name):
    name = stripped_name(raw_name)
    repo, _, rest = name.partition('__')
    return repo, rest.replace('__', '/')


def acquisition_dir(repo, revision):
    return LATER / 'downloads' / (repo.replace('/', '--') + '--' + revision[:12])


def frozen_selected_name():
    data = subprocess.check_output(
        ['git', 'show', ADAPTER_REVISION + ':scripts/build_tokenized_dfm8_tree.py'], cwd=ROOT)
    namespace: dict = {}
    exec(compile(data, 'build_tokenized_dfm8_tree.py', 'exec'), namespace)
    return namespace['selected_name']


def special_reference_files(friendly):
    base = ROOT / 'data/downloads/datasets' / friendly
    return sorted(p for p in base.rglob('*') if p.is_file()
                  and not any(part.startswith('.') for part in p.relative_to(base).parts))


def recover_lock(work):
    if CONFIG.exists():
        raise ValueError(f'{CONFIG} already exists; delete it to regenerate deliberately')
    builder = frozen_selected_name()
    manifest = load(ROOT / 'data/tokenized_dfm8/union_manifest.json')
    if {k: manifest[k] for k in EXPECTED_COMPOSITION} != EXPECTED_COMPOSITION:
        raise ValueError(f'Historical DFM8 union manifest differs: {manifest}')
    dfm7 = load(DFM7_CONFIG)
    base_names = sorted(set(dfm7['base']['tasks']) |
                        {dfm7_union_name(t['task']) for t in dfm7['tasks']})
    if len(base_names) != 10651:
        raise ValueError(f'DFM7 union inventory has {len(base_names)} tasks')
    raw_names = sorted(p.name for p in ADDITION_REFERENCE.iterdir() if p.is_dir())
    selected = [n for n in raw_names if builder(n) is not None]
    stripped = {builder(n): n for n in selected}
    duplicates = [n for n in selected if builder(n) in set(base_names)]
    skipped = [n for n in raw_names if builder(n) is None]
    if (len(selected), len(duplicates), len(skipped)) != (1426, 1357, 2600):
        raise ValueError(f'Frozen builder census differs: selected={len(selected)} '
                         f'duplicates={len(duplicates)} skipped={len(skipped)}')
    additions = sorted(name for name in stripped if name not in set(base_names))
    if len(additions) != 69:
        raise ValueError(f'Expected 69 DFM8 additions, census produced {len(additions)}')
    if sorted(stripped[name] for name in additions) != sorted(
            n for n in raw_names if n.startswith((SPECIAL_WRAPPER, 'export-upload-dfm8-synthetic__',
                                                  'export-upload-dfm8-openhermes-repaired__'))):
        raise ValueError('Census additions differ from the preserved wrapper directories')
    info_8 = (REFERENCE / 'tokenizer_info.json').read_bytes()
    info_7 = (ROOT / 'data/tokenized_dfm7/tokenizer_info.json').read_bytes()
    if info_8 != info_7:
        raise ValueError('DFM8 tokenizer info differs from DFM7')
    for group, spec in CONVERSION_GROUPS.items():
        for output, rows in spec['files'].items():
            historical = SPECIAL_REFERENCE / output
            if not historical.exists():
                raise ValueError(f'Missing historical conversion: {output}')
            count = sum(1 for _ in historical.open(encoding='utf-8'))
            if count != rows:
                raise ValueError(f'{output}: {count} historical rows, expected {rows}')
    prefix_sha = hashlib.sha256(subprocess.check_output(
        ['git', 'show', DATA_IO_REVISION + ':prefix_config_dfm8.yaml'],
        cwd=ROOT / 'data_io')).hexdigest()
    inputs = {}
    tasks = []
    for name in additions:
        raw = stripped[name]
        if raw.startswith(SPECIAL_WRAPPER):
            output = raw.removeprefix(SPECIAL_WRAPPER).replace('__', '/')
            group = output.split('/')[0]
            tasks.append(dict(task=raw, mode='converted', output=output, group=group))
            continue
        repo, rel = task_repo_rel(raw)
        full = 'schneiderkamplab/' + repo
        row = inputs.setdefault(full, {'repo_id': full, 'revision': HF_ADDITIONS[full], 'files': {}})
        reference = WRAPPER_ROOTS[next(w for w in WRAPPER_ROOTS if raw.startswith(w))] / repo / rel
        row['files'][rel] = digest(reference)
        tasks.append(dict(task=raw, mode='hf', input=full))
    for friendly, repo in FRIENDLY_TO_REPO.items():
        files = {}
        for path in special_reference_files(friendly):
            rel = str(path.relative_to(ROOT / 'data/downloads/datasets' / friendly))
            sha = digest(path)
            if sha != digest(acquisition_dir(repo, SPECIAL_ACQUISITIONS[repo]) / rel):
                raise ValueError(f'Acquisition copy differs: {repo}/{rel}')
            files[rel] = sha
        inputs[repo] = {'repo_id': repo, 'revision': SPECIAL_ACQUISITIONS[repo], 'files': files}
    cfg = {
        'version': 8, 'recipe': 'dfm8-hf-v1', 'epochs': 7,
        'generated_from': 'preserved DFM8 chat-source and union inventories',
        'adapter_revision': subprocess.check_output(
            ['git', 'rev-parse', ADAPTER_REVISION], cwd=ROOT, text=True).strip(),
        'template_revision': dfm7['template_revision'],
        'converter_revision': subprocess.check_output(
            ['git', 'rev-parse', CONVERTER_REVISION], cwd=ROOT, text=True).strip(),
        'data_io_revision': subprocess.check_output(
            ['git', 'rev-parse', DATA_IO_REVISION], cwd=ROOT / 'data_io', text=True).strip(),
        'prefix_config_sha256': prefix_sha,
        'tokenizer_repo': dfm7['tokenizer_repo'],
        'tokenizer_revision': dfm7['tokenizer_revision'],
        'tokenizer_sha256': dfm7['tokenizer_sha256'],
        'tokenizer_semantic_sha256': dfm7['tokenizer_semantic_sha256'],
        'tokenizer_post_processor': dfm7['tokenizer_post_processor'],
        'tokenizer_info': json.loads(info_8),
        'base': {'version': 7, 'tasks': base_names, 'tokenized_path': str(BASE)},
        'composition': dict(EXPECTED_COMPOSITION, raw_tasks=len(raw_names)),
        'inputs': inputs,
        'tasks': tasks,
        'conversion_groups': CONVERSION_GROUPS,
        'sampled': {'epochs': 7, 'seed': 0, 'concat_workers': 4,
                    'reference_metadata': load(ROOT / 'data/sampled_dfm8/metadata.json')},
    }
    write_json(CONFIG, cfg)
    print(f'Wrote {CONFIG}: {len(tasks)} tasks, {len(inputs)} inputs, '
          f'{sum(len(v["files"]) for v in inputs.values())} pinned files', flush=True)


def acquire(work):
    from huggingface_hub import HfApi, snapshot_download
    cfg = load(CONFIG)
    api = HfApi()
    with (LATER / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = load(LATER / 'manifest.json')
        for repo, revision in sorted(HF_ADDITIONS.items()):
            info = api.dataset_info(repo, revision=revision)
            if info.sha != revision:
                raise ValueError(f'{repo}: pinned commit no longer resolves')
            destination = acquisition_dir(repo, revision)
            if not destination.exists():
                snapshot_download(repo_id=repo, repo_type='dataset', revision=revision,
                                  local_dir=destination, cache_dir=LATER / 'hf-cache')
            for rel, sha in cfg['inputs'][repo]['files'].items():
                if digest(destination / rel) != sha:
                    raise ValueError(f'{repo}/{rel}: downloaded payload differs from '
                                     f'the historical upload receipt')
            row = next((e for e in manifest['entries'] if e['repo_id'] == repo), None)
            if row is None:
                raise ValueError(f'{repo}: absent from the later-acquisition manifest')
            row.update(status='downloaded', resolved_revision=revision,
                       revision_basis='registry_pin', download_path=str(destination))
            write_json(LATER / 'manifest.json', manifest)
            print(f'Acquired {repo} at {revision[:12]}', flush=True)
    write_json(work / 'acquire-receipt.json', dict(
        status='downloaded', repos=len(HF_ADDITIONS), basis='wiki-recorded upload commits'))


def prepare(work):
    from huggingface_hub import hf_hub_download
    cfg = load(CONFIG)
    if load(QUEUE / 'dfm7/verified.json')['status'] != 'matched':
        raise ValueError('DFM7 verification required')
    staged_prefix = work / 'prefix_config.yaml'
    staged_prefix.write_bytes(subprocess.check_output(
        ['git', 'show', DATA_IO_REVISION + ':prefix_config_dfm8.yaml'], cwd=ROOT / 'data_io'))
    if digest(staged_prefix) != cfg['prefix_config_sha256']:
        raise ValueError('Sampling policy changed')
    for repo, revision, rel, target in [
            (ROOT, cfg['adapter_revision'], 'scripts/tokenize_chat_template.py', 'historical_adapter.py'),
            (ROOT / 'data_io', cfg['data_io_revision'], 'chat_templates/gemma4_native_chat.jinja',
             'chat_template.jinja'),
            (ROOT, cfg['converter_revision'], 'scripts/convert_dfm8_giannor_tv2r.py',
             'convert_giannor_tv2r.py'),
            (ROOT, cfg['converter_revision'], 'scripts/convert_dfm8_skolegpt.py',
             'convert_skolegpt.py'),
            (ROOT, cfg['converter_revision'], 'scripts/build_tokenized_dfm8_tree.py',
             'build_union_tree.py')]:
        data = subprocess.check_output(['git', 'show', revision + ':' + rel], cwd=repo)
        (work / target).write_bytes(data)
    tokenizer = Path(hf_hub_download(cfg['tokenizer_repo'], 'tokenizer.json',
        revision=cfg['tokenizer_revision'], local_dir=work / 'tokenizer_hf'))
    definition = load(tokenizer)
    definition['post_processor'] = cfg['tokenizer_post_processor']
    if semantic_digest(definition) != cfg['tokenizer_semantic_sha256']:
        raise ValueError('HF tokenizer vocabulary/normalization differs from historical DFM8')
    (work / 'tokenizer').mkdir(exist_ok=True)
    write_json(work / 'tokenizer/tokenizer.json', definition)
    (work / 'downloads/datasets').mkdir(parents=True, exist_ok=True)
    (work / 'sources').mkdir(exist_ok=True)
    checked = []
    for i, (repo, item) in enumerate(sorted(cfg['inputs'].items()), 1):
        destination = acquisition_dir(repo, item['revision'])
        for rel, sha in sorted(item['files'].items()):
            path = allowed(destination / rel, roots(work))
            if not path.exists() or digest(path) != sha:
                raise ValueError(f'Acquisition payload missing or changed: {repo}/{rel}')
        checked.append(dict(repo=repo, revision=item['revision'],
                            files=len(item['files'])))
        if i % 4 == 0:
            print(f'Validated inputs {i}/{len(cfg["inputs"])}', flush=True)
    for friendly, repo in FRIENDLY_TO_REPO.items():
        for rel in sorted(cfg['inputs'][repo]['files']):
            link(acquisition_dir(repo, cfg['inputs'][repo]['revision']) / rel,
                 work / 'downloads/datasets' / friendly / rel, roots(work))
    for item in cfg['tasks']:
        if item['mode'] != 'hf':
            continue
        repo, rel = task_repo_rel(item['task'])
        full = 'schneiderkamplab/' + repo
        link(acquisition_dir(full, cfg['inputs'][full]['revision']) / rel,
             work / 'sources' / item['task'], roots(work))
    write_json(work / 'inputs-verified.json', dict(inputs=checked, config_sha256=digest(CONFIG)))
    write_json(work / 'recipe.json', cfg)


def convert(work):
    cfg = load(CONFIG)
    if digest(CONFIG) != load(work / 'inputs-verified.json')['config_sha256']:
        raise ValueError('DFM8 input lock changed')
    special = work / 'special_sources'
    if special.exists():
        shutil.rmtree(special)
    subprocess.run([sys.executable, str(work / 'convert_giannor_tv2r.py'),
                    '--download-root', str(work / 'downloads/datasets'),
                    '--output-root', str(special / 'giannor_tv2r_instruction'), '--force'],
                   check=True, env=converter_env())
    subprocess.run([sys.executable, str(work / 'convert_skolegpt.py'),
                    '--download-root', str(work / 'downloads/datasets'),
                    '--output-root', str(special / 'kobprof_skolegpt_instruct'), '--force'],
                   check=True, env=converter_env())
    for item in cfg['tasks']:
        if item['mode'] == 'converted':
            link(special / item['output'], work / 'sources' / item['task'], roots(work))
    write_json(work / 'convert-receipt.json', dict(status='converted', files=sum(
        1 for x in cfg['tasks'] if x['mode'] == 'converted')))


def verify_rows(work):
    cfg = load(CONFIG)
    for item in cfg['tasks']:
        if item['mode'] != 'converted':
            continue
        generated = work / 'special_sources' / item['output']
        compare_jsonl(generated, SPECIAL_REFERENCE / item['output'])
        expected = cfg['conversion_groups'][item['group']]['files'][item['output']]
        count = sum(1 for _ in generated.open(encoding='utf-8'))
        if count != expected:
            raise ValueError(f'{item["output"]}: {count} rows, expected {expected}')
        print(f'Rows matched {item["output"]}', flush=True)
    write_json(work / 'converted-comparison.json', dict(
        status='matched', converted_files=sum(1 for x in cfg['tasks'] if x['mode'] == 'converted'),
        method='byte-equality with row-content fallback'))


def smoke(work):
    from scripts.tokenize_historical_chat import adapter, examples
    import jinja2
    from tokenizers import Tokenizer
    module = adapter(work / 'historical_adapter.py')
    tok = Tokenizer.from_file(str(work / 'tokenizer/tokenizer.json'))
    template = jinja2.Environment().from_string((work / 'chat_template.jinja').read_text())
    # Check one file per source family before committing to full retokenization.
    chosen = {}
    for item in load(CONFIG)['tasks']:
        if item['mode'] == 'converted':
            family = item['output'].split('/')[0]
        else:
            family = item['task'].split('__', 1)[1].split('__', 1)[0]
        chosen.setdefault(family, item['task'])
    passed = []
    for family in sorted(chosen):
        name = chosen[family]
        expected = ADDITION_REFERENCE / name
        starts = np.load(expected / 'inst_start.npy', mmap_mode='r')
        if not len(starts):
            continue
        n = min(3, len(starts))
        tokens = np.load(expected / 'tokens.npy', mmap_mode='r')
        response_starts = np.load(expected / 'resp_start.npy', mmap_mode='r')
        response_lengths = np.load(expected / 'resp_len.npy', mmap_mode='r')
        count = 0
        for example in examples(module, work / 'sources' / name):
            pair = module.tokenize_example(tok, template, example, False)
            if pair is None:
                continue
            end = int(response_starts[count]) + int(response_lengths[count])
            equal_arrays(np.asarray(pair[0] + pair[1], dtype=np.uint32),
                         tokens[int(starts[count]):end], f'{name}/row{count}')
            count += 1
            if count == n:
                break
        if count != n:
            raise ValueError(f'Insufficient smoke rows: {name}')
        passed.append(name)
        print(f'Smoke matched {name}', flush=True)
    write_json(work / 'smoke.json', dict(status='matched', tasks=passed))


def tokenizer_command(work, source, output, workers):
    return [sys.executable, str(ROOT / 'scripts/tokenize_historical_chat.py'),
            '--input', str(source), '--output', str(output),
            '--adapter', str(work / 'historical_adapter.py'),
            '--tokenizer', str(work / 'tokenizer/tokenizer.json'),
            '--template', str(work / 'chat_template.jinja'), '--workers', str(workers)]


def tokenize(work):
    from scripts.queue_dfm_hf_rebuild import safe_tokenizer_workers
    cfg = load(CONFIG)
    if digest(CONFIG) != load(work / 'inputs-verified.json')['config_sha256']:
        raise ValueError('DFM8 input lock changed')
    expected = {x['task'] for x in cfg['tasks']}
    if {x.name for x in (work / 'sources').iterdir()} != expected:
        raise ValueError('Unexpected DFM8 source inventory')
    subprocess.run(tokenizer_command(work, work / 'sources', work / 'tokenized',
                                     safe_tokenizer_workers()), check=True)
    tokenized = {x.name for x in (work / 'tokenized').iterdir() if x.is_dir()}
    if tokenized != expected:
        raise ValueError('Tokenized DFM8 additions differ from the locked inventory')
    write_json(work / 'tokenized/tokenizer_info.json', cfg['tokenizer_info'])


def assemble(work):
    cfg = load(CONFIG)
    if digest(CONFIG) != load(work / 'inputs-verified.json')['config_sha256']:
        raise ValueError('DFM8 input lock changed')
    union = work / 'union'
    if union.exists():
        shutil.rmtree(union)
    union.mkdir(parents=True)
    info = work / 'tokenized/tokenizer_info.json'
    if info.read_bytes() != (BASE / 'tokenizer_info.json').read_bytes():
        raise ValueError('Base tokenized tree and DFM8 additions use different tokenizer info')
    (union / 'tokenizer_info.json').symlink_to(info.resolve())
    base_names = set(cfg['base']['tasks'])
    for name in sorted(base_names):
        target = union / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to((BASE / name).resolve())
    addition_names = set()
    for item in cfg['tasks']:
        name = stripped_name(item['task'])
        target = union / name
        if target.exists() or target.is_symlink():
            raise ValueError(f'Union collision: {name}')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to((work / 'tokenized' / item['task']).resolve())
        addition_names.add(name)
    # The historical union builder saw 4,026 raw tasks; the 1,357 export-upload
    # duplicates and 2,600 non-matching transform-expansion tasks were skipped.
    # Those receipts are reproduced here instead of re-tokenizing discarded data.
    manifest = {'raw_tokenized': str(work / 'tokenized'), 'base_tokenized': str(BASE),
                'output': str(union),
                'base_selected_tasks': len(base_names),
                'dfm8_selected_tasks': len(addition_names),
                'duplicate_skipped_tasks': cfg['composition']['duplicate_skipped_tasks'],
                'skipped_tasks': cfg['composition']['skipped_tasks']}
    (union / 'union_manifest.json').write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding='utf-8')
    if (manifest['base_selected_tasks'], manifest['dfm8_selected_tasks'],
            manifest['duplicate_skipped_tasks'], manifest['skipped_tasks']) != (
            10651, 69, 1357, 2600):
        raise ValueError('DFM8 union layout differs from historical')
    produced = {p.name for p in union.iterdir() if p.is_dir()}
    if produced != base_names | addition_names:
        raise ValueError('Union task inventory differs from the locked composition')
    write_json(work / 'assemble-receipt.json', dict(
        status='assembled', base=manifest['base_selected_tasks'],
        additions=manifest['dfm8_selected_tasks'],
        duplicate_skipped=manifest['duplicate_skipped_tasks'],
        skipped=manifest['skipped_tasks']))


def verify(work):
    cfg = load(CONFIG)
    if digest(CONFIG) != load(work / 'inputs-verified.json')['config_sha256']:
        raise ValueError('DFM8 input lock changed')
    tree = work / 'union'
    wanted = {p.name for p in (REFERENCE).iterdir() if p.is_dir()}
    if {x.name for x in tree.iterdir() if x.is_dir()} != wanted:
        raise ValueError('Union task inventory differs from historical DFM8')
    for i, name in enumerate(sorted(wanted), 1):
        for field in FIELDS:
            equal_arrays(np.load(tree / name / f'{field}.npy', mmap_mode='r'),
                np.load(REFERENCE / name / f'{field}.npy', mmap_mode='r'), name + '/' + field)
        if i % 250 == 0:
            print(f'Compared {i}/{len(wanted)} tasks', flush=True)
    write_json(work / 'all-token-comparison.json', dict(status='matched', tasks=len(wanted)))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('recover-lock', 'acquire', 'prepare', 'convert',
                                     'verify-rows', 'smoke', 'tokenize', 'assemble', 'verify'))
    p.add_argument('--work', type=Path, required=True)
    args = p.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    with (args.work / 'stage.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        {'recover-lock': recover_lock, 'acquire': acquire, 'prepare': prepare,
         'convert': convert, 'verify-rows': verify_rows, 'smoke': smoke,
         'tokenize': tokenize, 'assemble': assemble, 'verify': verify}[args.stage](args.work)


if __name__ == '__main__':
    main()
