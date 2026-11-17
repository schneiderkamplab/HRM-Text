"""Recover and execute DFM7's historical HF-only jinja chat union rebuild.

Production token arrays are comparison references only. Inputs are pinned HF
acquisitions plus the verified DFM6 reconstruction (lexdk/DBC allowed).
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
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.rebuild_dfm5 import allowed, link
from scripts.rebuild_dfm5_acquire import digest, load
from scripts.replay_dfm_serial import equal_arrays, write_json

# The DFM7 tokenization (2026-07-01) ran with the then-uncommitted adapter that
# cd88c93 later recorded: the DFM6-era 038e9a5 adapter lacks the generic
# instruction/target parquet fallback the kaenguruen/oliverkinch sources need.
REVISION = 'cd88c93'
CONVERTER_REVISION = 'cd88c93'
DATA_IO_REVISION = '0483afe'
CONFIG = ROOT / 'config/data/dfm7_hf_rebuild.json'
QUEUE = ROOT / 'data/rebuild_hf_dfm/serial-queue'
BASE = QUEUE / 'dfm6/tokenized'
REFERENCE = ROOT / 'data/tokenized_dfm7'
ADDITION_REFERENCE = ROOT / 'data/tokenized_dfm7_jinja'
SPECIAL_REFERENCE = ROOT / 'data/dfm7_special_sources'
SPECIAL_WRAPPER = 'dfm7_special_sources__'
SHARDS_NAME = 'dfm_dyna_instruct_apertus_sft_mixture_shards'
SHARD_PREFIX = 'dfm_dyna_instruct__data__apertus-sft-mixture-shards__part-'
MONOLITH_TASK = 'dfm_dyna_instruct__data__apertus-sft-mixture__apertus-sft-mixture.parquet'
EXCLUDED_PREFIXES = ('danish_wildchat4_8m__', 'nemotron_swe__')
FIELDS = ('tokens', 'inst_start', 'inst_len', 'resp_start', 'resp_len')
# Python-literal tool-call arguments (e.g. conditions=[{'valid_to': {'<=', '2023-07-15'}}])
# parse into sets whose json_safe() iteration order depends on PYTHONHASHSEED.
# The historical special-source conversion ran with hash seed 2; without it the
# dolci output cannot be reproduced byte-for-byte.
CONVERSION_HASH_SEED = '2'


def converter_env():
    return dict(os.environ, PYTHONHASHSEED=CONVERSION_HASH_SEED)

# Friendly download directory -> acquisition repository, mirroring the
# historical data/downloads/datasets layout the frozen converters expect.
FRIENDLY_TO_REPO = {
    'ai_arena_udtraek': 'danish-foundation-models/ai_arena_udtraek',
    'allenai_rlvr_gsm': 'allenai/RLVR-GSM',
    'allenai_rlvr_math': 'allenai/RLVR-MATH',
    'dolci_instruct_sft_tool_use': 'allenai/Dolci-Instruct-SFT-Tool-Use',
    'dolci_instruct_sft_tool_use_sa': 'allenai/Dolci-Instruct-SFT-Tool-Use-SA',
    'glaive_function_calling_v2': 'glaiveai/glaive-function-calling-v2',
    'toolace': 'Team-ACE/ToolACE',
    'xlam_function_calling_60k': 'Salesforce/xlam-function-calling-60k',
    'kaenguruen': 'danish-foundation-models/kaenguruen',
    'dfm_dyna_instruct': 'danish-foundation-models/dfm-dyna-instruct',
    'oliverkinch_autodata_da_sft': 'oliverkinch/autodata-da-sft',
    'oliverkinch_da_instruct_dynaword': 'oliverkinch/da-instruct-dynaword',
    'oliverkinch_da_instruct_dynaword_hq': 'oliverkinch/da-instruct-dynaword-hq',
    'oliverkinch_da_instruct_dynaword_contemporary': 'oliverkinch/da-instruct-dynaword-contemporary',
    'oliverkinch_da_instruct_dynaword_contemporary_hq': 'oliverkinch/da-instruct-dynaword-contemporary-hq',
    'oliverkinch_danish_qa': 'oliverkinch/danish-qa',
    'oliverkinch_danish_summarization': 'oliverkinch/danish-summarization',
}


def roots(work):
    return [work.parent, ROOT / 'data/rebuild_hf_dfm/later-acquisition/downloads']


def semantic_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def stripped_name(raw_name):
    return raw_name.removeprefix(SPECIAL_WRAPPER) if raw_name.startswith(SPECIAL_WRAPPER) else raw_name


def expected_union_names(cfg):
    return set(cfg['base']['tasks']) | {stripped_name(x['task']) for x in cfg['tasks']}


def input_key(friendly, rel):
    return f'{friendly}__{rel.replace("/", "__")}'


def staged_download(work, cfg, key):
    item = cfg['inputs'][key]
    return work / 'downloads/datasets' / item['friendly'] / item['rel']


def consumed_inputs(acq_by_repo):
    """Pin the historically consumed download snapshot to its acquisitions.

    The preserved data/downloads/datasets snapshot is what the frozen converters
    actually saw (e.g. RLVR-GSM only had the train split), so it defines the
    inventory; each file must exist sha256-equal in the pinned acquisition.
    """
    inputs = {}
    for friendly, repo in FRIENDLY_TO_REPO.items():
        entry = acq_by_repo[repo]
        acq_root = Path(entry['download_path'])
        local_root = ROOT / 'data/downloads/datasets' / friendly
        if not local_root.is_dir():
            raise ValueError(f'Preserved download snapshot missing: {local_root}')
        for path in sorted(local_root.rglob('*')):
            if not path.is_file() or path.suffix not in ('.parquet', '.json'):
                continue
            rel = path.relative_to(local_root).as_posix()
            key = input_key(friendly, rel)
            if key in inputs:
                raise ValueError(f'Duplicate input identity: {key}')
            acq_path = acq_root / rel
            if not acq_path.is_file():
                raise ValueError(f'Acquisition lacks historically consumed file: {repo}/{rel}')
            local_sha = digest(path)
            acq_sha = digest(acq_path)
            if local_sha != acq_sha:
                raise ValueError(f'Local snapshot diverges from acquisition: {key}')
            inputs[key] = dict(friendly=friendly, repo_id=repo, revision=entry['resolved_revision'],
                rel=rel, path=str(acq_path), sha256=acq_sha)
    return inputs


def sapient_inventory():
    """Relative symlink paths under the sapient filter the union builder maps."""
    sap_root = ROOT / 'data/filtered_sources/sapient_cleaned'
    links = []
    for path in sap_root.rglob('*'):
        if not path.is_symlink():
            continue
        rel = path.relative_to(sap_root)
        if rel.name == 'README.md' or not rel.parts or rel.parts[0] not in ('data', 'data_clustered'):
            continue
        links.append(rel.as_posix())
    return sorted(links)


def historical_special_manifest():
    manifest = load(SPECIAL_REFERENCE / 'manifest.json')
    rows = {}
    for group, entry in manifest['sources'].items():
        if group == 'dolci_native_tool_use':
            rows[group] = {
                'rows': entry['rows'],
                'files': {path.removeprefix('data/dfm7_special_sources/'): item['rows']
                          for path, item in entry['files'].items()},
            }
        else:
            rows[group] = {'rows': entry['rows']}
    return rows


def recover_lock(work):
    if load(QUEUE / 'dfm6/verified.json')['status'] != 'matched':
        raise ValueError('DFM6 must be verified')
    later = load(ROOT / 'data/rebuild_hf_dfm/later-acquisition/manifest.json')['entries']
    acq_by_repo = {e['repo_id']: e for e in later if e['status'] == 'downloaded'}
    missing_repos = [r for r in FRIENDLY_TO_REPO.values() if r not in acq_by_repo]
    if missing_repos:
        raise ValueError(f'Unacquired DFM7 repositories: {missing_repos}')
    inputs = consumed_inputs(acq_by_repo)
    if len(inputs) != 33:
        raise ValueError(f'DFM7 consumes {len(inputs)} files, expected 33')
    if MONOLITH_TASK not in inputs:
        raise ValueError('Apertus monolith missing from acquisitions')
    base_tasks = sorted(p.name for p in BASE.iterdir()
                        if p.is_dir() and not p.name.startswith(EXCLUDED_PREFIXES))
    if len(base_tasks) != 10521:
        raise ValueError(f'DFM6 verified base has {len(base_tasks)} tasks, expected 10521')
    raw_names = sorted(p.name for p in ADDITION_REFERENCE.iterdir() if p.is_dir())
    if len(raw_names) != 130:
        raise ValueError(f'DFM7 additions tree has {len(raw_names)} tasks, expected 130')
    union_names = sorted(p.name for p in REFERENCE.iterdir() if p.is_dir())
    if sorted(set(base_tasks) | {stripped_name(n) for n in raw_names}) != union_names:
        raise ValueError('DFM7 union composition differs from the historical reference')
    direct = [n for n in raw_names if n in inputs]
    if len(direct) != 18:
        raise ValueError(f'{len(direct)} additions map directly to acquisitions, expected 18')
    groups = historical_special_manifest()
    shard_manifest = load(SPECIAL_REFERENCE / SHARDS_NAME / 'manifest.json')
    if shard_manifest['num_source_row_groups'] != 98 or shard_manifest['num_source_rows'] != 3942208:
        raise ValueError('Historical Apertus sharding changed shape')
    shard_rows = [item['rows'] for item in shard_manifest['shards']]
    tasks = []
    conversions = {}
    for name in raw_names:
        if name in inputs:
            tasks.append(dict(task=name, mode='hf', input=name))
        elif name.startswith(SPECIAL_WRAPPER):
            # Task names use '__' separators; on-disk converter outputs use '/'.
            output = name.removeprefix(SPECIAL_WRAPPER).replace('__', '/')
            group = output.split('/')[0]
            if group not in groups:
                raise ValueError(f'Unclassified special source: {name}')
            conversions[group] = conversions.get(group, 0) + 1
            tasks.append(dict(task=name, mode='converted', output=output, group=group))
        elif name.startswith(SHARD_PREFIX) and name.endswith('.parquet'):
            tasks.append(dict(task=name, mode='shard', shard=name.rpartition('__')[2]))
        else:
            raise ValueError(f'Unclassified DFM7 addition: {name}')
    if set(conversions) != set(groups):
        raise ValueError(f'Special-source groups do not cover the historical manifest: '
                         f'{sorted(set(groups) - set(conversions))}')
    for group, count in conversions.items():
        if group == 'dolci_native_tool_use':
            if count != len(groups[group]['files']):
                raise ValueError(f'{group} file inventory differs')
        elif count != 1:
            raise ValueError(f'{group} produced {count} tasks')
    shard_tasks = [x for x in tasks if x['mode'] == 'shard']
    if len(shard_tasks) != 98:
        raise ValueError(f'{len(shard_tasks)} shard tasks, expected 98')
    sap_links = sapient_inventory()
    if len(sap_links) != 4891:
        raise ValueError(f'Sapient filter inventory has {len(sap_links)} links, expected 4891')
    revision = subprocess.check_output(['git', 'rev-parse', REVISION], cwd=ROOT, text=True).strip()
    converter = subprocess.check_output(['git', 'rev-parse', CONVERTER_REVISION], cwd=ROOT, text=True).strip()
    template_revision = subprocess.check_output(['git', '-C', str(ROOT / 'data_io'),
        'rev-parse', DATA_IO_REVISION], text=True).strip()
    tokenizer_path = Path(load(REFERENCE / 'tokenizer_info.json')['tokenizer_path'])
    config = dict(
        version=7, epochs=6, canonical_epochs=5, seed=0,
        adapter_revision=revision, template_revision=template_revision,
        converter_revision=converter,
        input_policy='HF-only plus lexdk/DBC; production arrays comparison-only',
        tokenizer_repo='google/gemma-4-31B-it',
        tokenizer_revision='3548789868c5356dbf307c98e6f609007b82b3eb',
        tokenizer_sha256=digest(tokenizer_path),
        tokenizer_semantic_sha256=semantic_digest(load(tokenizer_path)),
        tokenizer_post_processor=load(tokenizer_path)['post_processor'],
        tokenizer_info=load(REFERENCE / 'tokenizer_info.json'),
        prefix_config_sha256=digest(ROOT / 'data_io/prefix_config_dfm7.yaml'),
        inputs=inputs,
        conversion_groups=groups,
        sharding=dict(input=MONOLITH_TASK, columns=['messages'], shards=98,
                      source_rows=shard_manifest['num_source_rows'], rows=shard_rows),
        base=dict(from_version=6, path=str(BASE), excluded_prefixes=list(EXCLUDED_PREFIXES),
                  tasks=base_tasks),
        sapient_filtered_inventory=dict(root='data/filtered_sources/sapient_cleaned', links=sap_links),
        tasks=tasks)
    write_json(work / 'recovery-inventory.json', dict(tasks=[x['task'] for x in tasks],
        base=len(base_tasks), inputs=len(inputs), sapient_links=len(sap_links)))
    if CONFIG.exists() and load(CONFIG) != config:
        raise ValueError('Refusing to overwrite a different frozen DFM7 lock')
    write_json(CONFIG, config)
    print(f'Recovered {len(tasks)} additions on a {len(base_tasks)}-task DFM6 base', flush=True)


def prepare(work):
    from huggingface_hub import hf_hub_download
    cfg = load(CONFIG)
    if load(QUEUE / 'dfm6/verified.json')['status'] != 'matched':
        raise ValueError('DFM6 verification required')
    if digest(ROOT / 'data_io/prefix_config_dfm7.yaml') != cfg['prefix_config_sha256']:
        raise ValueError('Sampling policy changed')
    shutil.copyfile(ROOT / 'data_io/prefix_config_dfm7.yaml', work / 'prefix_config.yaml')
    for repo, revision, rel, target in [
            (ROOT, cfg['adapter_revision'], 'scripts/tokenize_chat_template.py', 'historical_adapter.py'),
            (ROOT / 'data_io', cfg['template_revision'], 'chat_templates/gemma4_native_chat.jinja',
             'chat_template.jinja'),
            (ROOT, cfg['converter_revision'], 'scripts/prepare_dfm7_special_sources.py',
             'prepare_special_sources.py'),
            (ROOT, cfg['converter_revision'], 'scripts/shard_dfm7_large_parquets.py',
             'shard_large_parquets.py'),
            (ROOT, cfg['converter_revision'], 'scripts/build_tokenized_dfm7_tree.py',
             'build_union_tree.py')]:
        data = subprocess.check_output(['git', 'show', revision + ':' + rel], cwd=repo)
        (work / target).write_bytes(data)
    tokenizer = Path(hf_hub_download(cfg['tokenizer_repo'], 'tokenizer.json',
        revision=cfg['tokenizer_revision'], local_dir=work / 'tokenizer_hf'))
    definition = load(tokenizer)
    # The preserved local Gemma copy adds BOS postprocessing. The historical
    # encoder disables add_special_tokens, but reproduce the definition anyway.
    definition['post_processor'] = cfg['tokenizer_post_processor']
    if semantic_digest(definition) != cfg['tokenizer_semantic_sha256']:
        raise ValueError('HF tokenizer vocabulary/normalization differs from historical DFM7')
    (work / 'tokenizer').mkdir(exist_ok=True)
    write_json(work / 'tokenizer/tokenizer.json', definition)
    (work / 'downloads/datasets').mkdir(parents=True, exist_ok=True)
    (work / 'sources').mkdir(exist_ok=True)
    checked = []
    for i, (key, item) in enumerate(sorted(cfg['inputs'].items()), 1):
        path = allowed(Path(item['path']), roots(work))
        sha = digest(path)
        if sha != item['sha256']:
            raise ValueError(f'HF payload changed: {path}')
        link(path, staged_download(work, cfg, key), roots(work))
        checked.append(dict(key=key, sha256=sha))
        if i % 10 == 0:
            print(f'Validated inputs {i}/{len(cfg["inputs"])}', flush=True)
    for item in cfg['tasks']:
        if item['mode'] == 'hf':
            link(Path(cfg['inputs'][item['input']]['path']),
                 work / 'sources' / item['task'], roots(work))
    write_json(work / 'inputs-verified.json', dict(inputs=checked, config_sha256=digest(CONFIG)))
    write_json(work / 'recipe.json', cfg)


def kaenguruen_rows(module, parquet_path):
    rows = []
    parquet_file = pq.ParquetFile(parquet_path)
    for batch in parquet_file.iter_batches():
        for row in batch.to_pylist():
            rows.append(module.kaenguruen_training_row(dict(row)))
    return rows


def convert(work):
    import importlib.util
    cfg = load(CONFIG)
    if digest(CONFIG) != load(work / 'inputs-verified.json')['config_sha256']:
        raise ValueError('DFM7 input lock changed')
    special = work / 'special_sources'
    if special.exists():
        shutil.rmtree(special)
    subprocess.run([sys.executable, str(work / 'prepare_special_sources.py'),
                    '--download-root', str(work / 'downloads/datasets'),
                    '--output-root', str(special), '--skip-kaenguruen'],
                   check=True, env=converter_env())
    spec = importlib.util.spec_from_file_location('frozen_dfm7_converter',
                                                  work / 'prepare_special_sources.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['frozen_dfm7_converter'] = module
    spec.loader.exec_module(module)
    out = special / 'kaenguruen' / 'train.jsonl'
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = kaenguruen_rows(module, staged_download(work, cfg, 'kaenguruen__data__test-00000-of-00001.parquet'))
    with out.open('w', encoding='utf-8') as handle:
        for record in rows:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
    manifest = load(special / 'manifest.json')
    manifest['sources']['kaenguruen'] = {'path': str(out), 'rows': len(rows)}
    (special / 'manifest.json').write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding='utf-8')
    subprocess.run([sys.executable, str(work / 'shard_large_parquets.py'),
                    '--input', str(staged_download(work, cfg, cfg['sharding']['input'])),
                    '--output', str(special / SHARDS_NAME), '--force'],
                   check=True, env=converter_env())
    expected_outputs = set()
    for item in cfg['tasks']:
        if item['mode'] == 'converted':
            expected_outputs.add(item['output'])
            link(special / item['output'], work / 'sources' / item['task'], roots(work))
        elif item['mode'] == 'shard':
            expected_outputs.add(f'{SHARDS_NAME}/{item["shard"]}')
            link(special / SHARDS_NAME / item['shard'],
                 work / 'sources' / item['task'], roots(work))
    produced = {str(p.relative_to(special)) for p in special.rglob('*')
                if p.is_file() and p.name != 'manifest.json'}
    if produced != expected_outputs:
        raise ValueError(f'Converted inventory differs: '
                         f'missing={sorted(expected_outputs - produced)[:5]} '
                         f'extra={sorted(produced - expected_outputs)[:5]}')
    write_json(work / 'convert-receipt.json', dict(
        status='converted', files=len(expected_outputs), kaenguruen_rows=len(rows)))


def compare_jsonl(generated, historical):
    if generated.read_bytes() == historical.read_bytes():
        return
    # Split on newlines only: raw U+2028/U+2029 occur inside JSON strings.
    gen = generated.read_text(encoding='utf-8').split('\n')
    hist = historical.read_text(encoding='utf-8').split('\n')
    if gen and gen[-1] == '':
        gen.pop()
    if hist and hist[-1] == '':
        hist.pop()
    if len(gen) != len(hist):
        raise ValueError(f'{generated.name}: {len(gen)} rows vs historical {len(hist)}')
    for i, (a, b) in enumerate(zip(gen, hist)):
        if json.loads(a) != json.loads(b):
            raise ValueError(f'{generated.name}: row {i} differs from historical output')
    raise ValueError(f'{generated.name}: identical rows but different bytes')


def verify_rows(work):
    cfg = load(CONFIG)
    for item in cfg['tasks']:
        if item['mode'] != 'converted':
            continue
        generated = work / 'special_sources' / item['output']
        compare_jsonl(generated, SPECIAL_REFERENCE / item['output'])
        group = cfg['conversion_groups'][item['group']]
        expected = group.get('files', {}).get(item['output'], group['rows'])
        count = sum(1 for _ in generated.open(encoding='utf-8'))
        if count != expected:
            raise ValueError(f'{item["output"]}: {count} rows, expected {expected}')
        print(f'Rows matched {item["output"]}', flush=True)
    rows = cfg['sharding']['rows']
    shards = sorted(x['shard'] for x in cfg['tasks'] if x['mode'] == 'shard')
    for i, shard in enumerate(shards):
        generated = work / 'special_sources' / SHARDS_NAME / shard
        historical = SPECIAL_REFERENCE / SHARDS_NAME / shard
        table = pq.read_table(generated)
        if table.num_rows != rows[i]:
            raise ValueError(f'{shard}: {table.num_rows} rows, expected {rows[i]}')
        if generated.read_bytes() != historical.read_bytes():
            if not pq.read_table(historical).equals(table):
                raise ValueError(f'{shard}: shard content differs from historical')
        if (i + 1) % 20 == 0:
            print(f'Shards matched {i + 1}/{len(rows)}', flush=True)
    write_json(work / 'converted-comparison.json', dict(
        status='matched', converted_files=sum(1 for x in cfg['tasks'] if x['mode'] == 'converted'),
        shards=len(rows), method='byte-equality with row-content fallback'))


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
    for name in sorted(chosen.values()):
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
        raise ValueError('DFM7 input lock changed')
    expected = {x['task'] for x in cfg['tasks']}
    if {x.name for x in (work / 'sources').iterdir()} != expected:
        raise ValueError('Unexpected DFM7 source inventory')
    subprocess.run(tokenizer_command(work, work / 'sources', work / 'tokenized',
                                     safe_tokenizer_workers()), check=True)
    tokenized = {x.name for x in (work / 'tokenized').iterdir() if x.is_dir()}
    if tokenized != expected:
        raise ValueError('Tokenized DFM7 additions differ from the locked inventory')
    write_json(work / 'tokenized/tokenizer_info.json', cfg['tokenizer_info'])


def assemble(work):
    cfg = load(CONFIG)
    if digest(CONFIG) != load(work / 'inputs-verified.json')['config_sha256']:
        raise ValueError('DFM7 input lock changed')
    inventory = work / 'sapient_inventory'
    inventory.mkdir(exist_ok=True)
    placeholder = inventory / '.placeholder'
    placeholder.write_text('inventory replica of the historical sapient filter\n')
    for rel in cfg['sapient_filtered_inventory']['links']:
        target = inventory / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_symlink():
            target.symlink_to(placeholder)
    subprocess.run([sys.executable, str(work / 'build_union_tree.py'),
                    '--raw-tokenized', str(work / 'tokenized'),
                    '--base-tokenized', str(BASE),
                    '--sapient-filtered', str(inventory),
                    '--output', str(work / 'union'), '--force'], check=True)
    manifest = load(work / 'union/union_manifest.json')
    if (manifest['base_selected_tasks'], manifest['selected_tasks'], manifest['skipped_tasks']) != (
            10521, 130, 0):
        raise ValueError(f'DFM7 union layout differs from historical: {manifest}')
    if manifest['sapient_allowed_tasks'] != len(cfg['sapient_filtered_inventory']['links']):
        raise ValueError('Staged sapient inventory did not reproduce the historical set')
    produced = {p.name for p in (work / 'union').iterdir() if p.is_dir()}
    if produced != expected_union_names(cfg):
        raise ValueError('Union task inventory differs from the locked composition')
    write_json(work / 'assemble-receipt.json', dict(
        status='assembled', base=manifest['base_selected_tasks'],
        additions=manifest['selected_tasks'], sapient_allowed=manifest['sapient_allowed_tasks']))


def verify(work):
    cfg = load(CONFIG)
    if digest(CONFIG) != load(work / 'inputs-verified.json')['config_sha256']:
        raise ValueError('DFM7 input lock changed')
    tree = work / 'union'
    wanted = expected_union_names(cfg)
    if {x.name for x in tree.iterdir() if x.is_dir()} != wanted:
        raise ValueError('Union task inventory differs')
    for i, name in enumerate(sorted(wanted), 1):
        for field in FIELDS:
            equal_arrays(np.load(tree / name / f'{field}.npy', mmap_mode='r'),
                np.load(REFERENCE / name / f'{field}.npy', mmap_mode='r'), name + '/' + field)
        if i % 100 == 0:
            print(f'Compared {i}/{len(wanted)} tasks', flush=True)
    write_json(work / 'all-token-comparison.json', dict(status='matched', tasks=len(wanted)))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('recover-lock', 'prepare', 'convert', 'verify-rows',
                                     'smoke', 'tokenize', 'assemble', 'verify'))
    p.add_argument('--work', type=Path, required=True)
    args = p.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    with (args.work / 'stage.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        {'recover-lock': recover_lock, 'prepare': prepare, 'convert': convert,
         'verify-rows': verify_rows, 'smoke': smoke, 'tokenize': tokenize,
         'assemble': assemble, 'verify': verify}[args.stage](args.work)


if __name__ == '__main__':
    main()
