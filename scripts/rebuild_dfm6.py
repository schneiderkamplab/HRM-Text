"""Recover and execute DFM6's historical HF-only Gemma-tokenizer migration.

Production token arrays are comparison references only. Inputs are pinned HF
acquisitions and verified earlier reconstructions (including lexdk/DBC).
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_dfm6_chat_source_tree import DIRECT_FILTERED_PREFIXES
from scripts.rebuild_dfm5 import allowed, link
from scripts.rebuild_dfm5_acquire import digest, load
from scripts.replay_dfm_serial import equal_arrays, write_json

REVISION = '038e9a5'
CONFIG = ROOT / 'config/data/dfm6_hf_rebuild.json'
REFERENCE = ROOT / 'data/tokenized_dfm6'
SWE_TASK = 'nemotron_swe__data__swe.jsonl'


def converted_inventory(root):
    result = {}
    for directory, _, filenames in os.walk(root, followlinks=True):
        for name in filenames:
            path = Path(directory) / name
            if path.suffix in ('.parquet', '.jsonl') or name.endswith('.jsonl.gz'):
                key = '__'.join(path.relative_to(root).parts)
                if key in result:
                    raise ValueError(f'Duplicate input identity: {key}')
                result[key] = path
    return result


def recover_lock(work):
    queue = work.parent
    if load(queue / 'dfm5/verified.json')['status'] != 'matched':
        raise ValueError('DFM5 must be verified')
    provenance = load(queue / 'dfm1/input-provenance.json')
    sources = {s['name']: s for s in provenance['acquisition_manifest']['hf_sources']}
    later = load(ROOT / 'data/rebuild_hf_dfm/later-acquisition/manifest.json')['entries']
    for name, repo in [('allenai_rlvr_gsm', 'allenai/RLVR-GSM'),
                       ('allenai_rlvr_math', 'allenai/RLVR-MATH')]:
        sources[name] = next(s for s in later if s['repo_id'] == repo and s['status'] == 'downloaded')
    exports = load(ROOT / 'data/rebuild_hf_dfm/dfm5-acquisition/manifest.json')['entries']
    inputs = {}
    for entry in exports:
        family = entry['repo_id'].split('/')[-1]
        for item in entry['files']:
            key = family + '__' + item['path'].replace('/', '__')
            inputs[key] = dict(mode='hf', source=entry['repo_id'], revision=entry['revision'],
                path=str(Path(entry['download_path']) / item['path']), sha256=item['verified_sha256'])
    recipe5 = load(queue / 'dfm5/recipe.json')
    for item in recipe5['selection']:
        inputs[item['task']] = dict(mode='hf', source=recipe5['source']['repo_id'],
            revision=recipe5['source']['resolved_revision'],
            path=str(Path(recipe5['source']['download_path']) / item['path']))
    converted = converted_inventory(queue / 'dfm1/converted')
    converted.update(converted_inventory(queue / 'dfm4/summary'))
    reference_names = sorted(p.name for p in REFERENCE.iterdir() if p.is_dir())
    missing = []
    tasks = []
    for name in reference_names:
        item = inputs.get(name)
        if item is None:
            family, _, relative = name.partition('__')
            if family in DIRECT_FILTERED_PREFIXES:
                entry = sources.get(family)
                if entry and entry['status'] == 'downloaded':
                    path = Path(entry['download_path']) / relative.replace('__', '/')
                    if path.is_file():
                        item = dict(mode='hf', source=entry['repo_id'],
                            revision=entry['resolved_revision'], path=str(path))
            elif name in converted:
                item = dict(mode='verified-rebuild-source', path=str(converted[name]))
        if item is None:
            missing.append(name)
        else:
            tasks.append(dict(task=name, **item))
    write_json(work / 'recovery-inventory.json', dict(tasks=tasks, missing=missing))
    if missing:
        raise ValueError(f'{len(missing)} unresolved tasks: {missing[:30]}')
    revision = subprocess.check_output(['git', 'rev-parse', REVISION], cwd=ROOT, text=True).strip()
    template_revision = subprocess.check_output(['git', '-C', str(ROOT / 'data_io'),
        'rev-parse', '0483afe'], text=True).strip()
    config = dict(version=6, epochs=5, seed=0, adapter_revision=revision,
        template_revision=template_revision,
        input_policy='HF-only plus lexdk/DBC; production arrays comparison-only',
        tokenizer_repo='google/gemma-4-31B-it',
        tokenizer_revision='3548789868c5356dbf307c98e6f609007b82b3eb',
        tokenizer_sha256=digest(Path(load(REFERENCE / 'tokenizer_info.json')['tokenizer_path'])),
        tokenizer_semantic_sha256=semantic_digest(load(Path(load(REFERENCE / 'tokenizer_info.json')['tokenizer_path']))),
        tokenizer_post_processor=load(Path(load(REFERENCE / 'tokenizer_info.json')['tokenizer_path']))['post_processor'],
        tokenizer_info=load(REFERENCE / 'tokenizer_info.json'),
        prefix_config_sha256=digest(ROOT / 'data_io/prefix_config_dfm6.yaml'), tasks=tasks)
    if CONFIG.exists() and load(CONFIG) != config:
        raise ValueError('Refusing to overwrite a different frozen DFM6 lock')
    write_json(CONFIG, config)
    print(f'Recovered {len(tasks)} task identities', flush=True)


def roots(work):
    return [work.parent, ROOT / 'data/rebuild_hf_dfm/dfm1-acquisition/downloads',
            ROOT / 'data/rebuild_hf_dfm/dfm5-acquisition/downloads',
            ROOT / 'data/rebuild_hf_dfm/later-acquisition/downloads']


def semantic_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def clean_tool_calling(source, target):
    if target.exists():
        return
    stage = target.with_suffix('.partial')
    kept = dropped = 0
    with source.open('rb') as inp, stage.open('wb') as out:
        for line in inp:
            if b'\x00' in line:
                dropped += 1
            else:
                out.write(line)
                kept += int(bool(line.strip()))
    if (kept, dropped) != (8443, 1):
        stage.unlink()
        raise ValueError(f'Upstream tool-call corruption changed: {kept=}, {dropped=}')
    stage.rename(target)


def prepare(work):
    from huggingface_hub import hf_hub_download
    cfg = load(CONFIG)
    if load(work.parent / 'dfm5/verified.json')['status'] != 'matched':
        raise ValueError('DFM5 verification required')
    if digest(ROOT / 'data_io/prefix_config_dfm6.yaml') != cfg['prefix_config_sha256']:
        raise ValueError('Sampling policy changed')
    shutil.copyfile(ROOT / 'data_io/prefix_config_dfm6.yaml', work / 'prefix_config.yaml')
    for repo, revision, rel, target in [
            (ROOT, cfg['adapter_revision'], 'scripts/tokenize_chat_template.py', 'historical_adapter.py'),
            (ROOT / 'data_io', cfg['template_revision'], 'chat_templates/gemma4_native_chat.jinja', 'chat_template.jinja')]:
        data = subprocess.check_output(['git', 'show', revision + ':' + rel], cwd=repo)
        (work / target).write_bytes(data)
    tokenizer = Path(hf_hub_download(cfg['tokenizer_repo'], 'tokenizer.json',
        revision=cfg['tokenizer_revision'], local_dir=work / 'tokenizer_hf'))
    definition = load(tokenizer)
    # The preserved local Gemma copy adds BOS postprocessing. The historical
    # encoder disables add_special_tokens, but reproduce the definition anyway.
    definition['post_processor'] = cfg['tokenizer_post_processor']
    if semantic_digest(definition) != cfg['tokenizer_semantic_sha256']:
        raise ValueError('HF tokenizer vocabulary/normalization differs from historical DFM6')
    (work / 'tokenizer').mkdir(exist_ok=True)
    write_json(work / 'tokenizer/tokenizer.json', definition)
    (work / 'sources').mkdir(exist_ok=True)
    checked = []
    for i, item in enumerate(cfg['tasks'], 1):
        path = allowed(Path(item['path']), roots(work))
        sha = digest(path)
        if item.get('sha256') and item['sha256'] != sha:
            raise ValueError(f'HF payload changed: {path}')
        checked.append(dict(task=item['task'], sha256=sha))
        if item['task'] == 'nemotron_agentic__data__tool_calling.jsonl':
            cleaned = work / 'cleaned_tool_calling.jsonl'
            clean_tool_calling(path, cleaned)
            path = cleaned
        link(path, work / 'sources' / item['task'], roots(work))
        if i % 100 == 0:
            print(f'Validated sources {i}/{len(cfg["tasks"])}', flush=True)
    write_json(work / 'inputs-verified.json', dict(tasks=checked, config_sha256=digest(CONFIG)))
    write_json(work / 'recipe.json', cfg)


def verify(work):
    cfg = load(CONFIG)
    if digest(CONFIG) != load(work / 'inputs-verified.json')['config_sha256']:
        raise ValueError('DFM6 input lock changed')
    tree = work / 'tokenized'
    wanted = {x['task'] for x in cfg['tasks']}
    if {x.name for x in tree.iterdir() if x.is_dir()} != wanted:
        raise ValueError('Tokenized task inventory differs')
    for i, name in enumerate(sorted(wanted), 1):
        for field in ('tokens', 'inst_start', 'inst_len', 'resp_start', 'resp_len'):
            equal_arrays(np.load(tree / name / f'{field}.npy', mmap_mode='r'),
                np.load(REFERENCE / name / f'{field}.npy', mmap_mode='r'), name + '/' + field)
        if i % 50 == 0:
            print(f'Compared {i}/{len(wanted)} tasks', flush=True)
    # Preserve historical descriptive paths; payload provenance is recorded separately.
    write_json(tree / 'tokenizer_info.json', cfg['tokenizer_info'])
    write_json(work / 'all-token-comparison.json', dict(status='matched', tasks=len(wanted)))


def tokenizer_command(work, source, output, workers):
    return [sys.executable, str(ROOT / 'scripts/tokenize_historical_chat.py'),
            '--input', str(source), '--output', str(output),
            '--adapter', str(work / 'historical_adapter.py'),
            '--tokenizer', str(work / 'tokenizer/tokenizer.json'),
            '--template', str(work / 'chat_template.jinja'), '--workers', str(workers)]


def tokenize(work):
    from scripts.queue_dfm_hf_rebuild import safe_tokenizer_workers
    source = work / 'sources' / SWE_TASK
    other = work / 'sources_non_swe'
    other.mkdir(exist_ok=True)
    expected = {x['task'] for x in load(CONFIG)['tasks']} - {SWE_TASK}
    for name in sorted(expected):
        link(work / 'sources' / name, other / name, roots(work))
    if {x.name for x in other.iterdir()} != expected:
        raise ValueError('Unexpected non-SWE input inventory')
    # Same driver, source stats and output paths: finished receipts are reused.
    subprocess.run(tokenizer_command(work, other, work / 'tokenized',
                                    safe_tokenizer_workers()), check=True)
    split = work / 'swe_split'
    manifest = split / 'split_manifest.json'
    if not manifest.exists():
        stage = work / 'swe_split.partial'
        subprocess.run([sys.executable, str(ROOT / 'scripts/split_jsonl_objects.py'),
            str(source), '--output-dir', str(stage), '--shards', '32', '--prefix', 'swe',
            '--force'], check=True)
        summary = load(stage / 'split_manifest.json')
        if summary['rows'] != 46278 or summary['actual_shards'] != 32:
            raise ValueError('SWE split differs from historical 46,278 objects / 32 shards')
        for item in summary['shards']:
            item['sha256'] = digest(stage / item['path'])
        summary['source_sha256'] = digest(source)
        write_json(stage / 'split_manifest.json', summary)
        stage.rename(split)
    summary = load(manifest)
    expected_source_sha = next(x['sha256'] for x in load(work / 'inputs-verified.json')['tasks']
                               if x['task'] == SWE_TASK)
    if summary['source_sha256'] != expected_source_sha:
        raise ValueError('SWE split does not match verified HF input')
    shard_inputs = work / 'swe_sources'
    shard_inputs.mkdir(exist_ok=True)
    for item in summary['shards']:
        path = split / item['path']
        if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            raise ValueError(f'SWE shard changed: {path}')
        link(path, shard_inputs / path.name, roots(work))
    if {x.name for x in shard_inputs.iterdir()} != {x['path'] for x in summary['shards']}:
        raise ValueError('Unexpected SWE shard inputs')
    tokens = work / 'swe_tokenized'
    subprocess.run(tokenizer_command(work, shard_inputs, tokens,
                                    min(32, safe_tokenizer_workers())), check=True)
    if {x.name for x in tokens.iterdir() if x.is_dir() and x.name.startswith('swe-')} != {
            x['path'] for x in summary['shards']}:
        raise ValueError('Incomplete or unexpected SWE tokenized shards')
    joined = tokens / SWE_TASK
    if not (joined / 'joined_shards.json').exists():
        subprocess.run([sys.executable, str(ROOT / 'scripts/join_tokenized_shards.py'),
            '--tokenized-root', str(tokens), '--shard-prefix', 'swe-',
            '--output-name', SWE_TASK, '--source-file', str(source)], check=True)
    for field in ('tokens', 'inst_start', 'inst_len', 'resp_start', 'resp_len'):
        print(f'Checking joined SWE {field}', flush=True)
        equal_arrays(np.load(joined / f'{field}.npy', mmap_mode='r'),
                     np.load(REFERENCE / SWE_TASK / f'{field}.npy', mmap_mode='r'), SWE_TASK + '/' + field)
    write_json(work / 'swe-comparison.json', dict(status='matched', shards=32,
        source_objects=46278, source_sha256=expected_source_sha))
    link(joined, work / 'tokenized' / SWE_TASK, roots(work))


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
        chosen.setdefault(item['task'].split('__')[0], item['task'])
    passed = []
    for name in chosen.values():
        expected = REFERENCE / name
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('recover-lock', 'prepare', 'smoke', 'tokenize', 'verify'))
    p.add_argument('--work', type=Path, required=True)
    args = p.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    with (args.work / 'stage.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        {'recover-lock': recover_lock, 'prepare': prepare, 'smoke': smoke,
         'tokenize': tokenize, 'verify': verify}[args.stage](args.work)


if __name__ == '__main__':
    main()
