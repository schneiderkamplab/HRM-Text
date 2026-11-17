#!/usr/bin/env python3
"""Historical DFM10 reconstruction mechanics (legacy local inputs disabled).

Use acquire_dfm10_hf.py for fresh pinned public acquisitions. The legacy input
lock is reference inventory only and cannot authorize an HF-only rebuild.
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
CONFIG = ROOT / 'config/data/dfm10_hf_rebuild.json'
ADAPTER_REVISION = 'cd88c93'        # baseline adapter; capped and designated-target tasks use ccbb215
NATIVE_ADAPTER_REVISION = 'ccbb215'  # commit that recorded the native tool-use mode
BUILDER_REVISION = 'ccbb215'         # committed union builder
TEMPLATE_REVISION = '1f52b10'        # template committed with the DFM10 data_io pin
DATA_IO_REVISION = '1f52b10'         # data_io commit matching prefix_config_dfm10.yaml
REFERENCE = ROOT / 'data/tokenized_dfm10'
BASE_UNION = QUEUE / 'dfm9/union'
BASE_INVENTORY = ROOT / 'data/tokenized_dfm9'
MANIFEST = ROOT / 'data/tokenized_dfm10/union_manifest.json'
REPLACED_BASE_PREFIXES = ('nemotron_terminal_corpus__', 'dolci_instruct_sft_tool_use__',
                          'dolci_instruct_sft_tool_use_sa__', 'dolci_native_tool_use__')
NATIVE_LABEL = 'nemotron_terminal_native'
NATIVE_MAX_SEQ_LEN = 4096
# The historical scibench source was re-saved after tokenization (identical
# size, different mtime); the name/size match plus the verify stage carry it.
FALLBACK_SOURCES = {
    'sapient_scibench_repaired__train.parquet':
        'data/converted_sources/sapient_scibench_repaired/train.parquet',
}
# The historical union manifest predates the committed builder and omits one
# component path; the tree name is deterministic.
FALLBACK_TREES = {
    'dfm10_synthetic_values_model_charter_da':
        'data/tokenized_dfm10_synthetic_values_model_charter_da',
}
LABEL_TO_FLAG = {
    'nemotron_terminal_native': 'nemotron-terminal-native',
    'andersen': 'andersen',
    'bornholmsk_parallel': 'bornholmsk-parallel',
    'diem_modernization': 'diem-modernization',
    'cor_sem': 'cor-sem',
    'danish_book_ads': 'danish-book-ads',
    'sks_tei': 'sks-tei',
    'alexandra': 'alexandra',
    'folketing': 'folketing',
    'deepdive': 'deepdive',
    'dbc_repaired': 'dbc-repaired',
    'openmathinstruct2_repaired': 'openmath-repaired',
    'dolci_tool_use_repaired': 'dolci-tool-use-repaired',
    'govreport_repaired': 'govreport-repaired',
    'wiki_cat_sum_repaired': 'wiki-cat-sum-repaired',
    'danmarks_statistik_bt_repaired': 'danmarks-statistik-bt-repaired',
    'nordjylland_news_repaired': 'nordjylland-news-repaired',
    'dst_table_prompts_repaired': 'dst-table-prompts-repaired',
    'nemotron_swe_repaired': 'nemotron-swe-repaired',
    'dynaword_instruct_repaired': 'dynaword-instruct-repaired',
    'code_meta_reasoning_repaired': 'code-meta-reasoning-repaired',
    'opus_da_en_repaired': 'opus-repaired',
    'danish_university_portals_bt_repaired': 'university-portals-repaired',
    'scientific_summaries_repaired': 'scientific-summaries-repaired',
    'machine_translation_da_uk_repaired': 'machine-translation-da-uk-repaired',
    'sapient_qrecc_ii_repaired': 'qrecc-ii-repaired',
    'sapient_scibench_repaired': 'scibench-repaired',
    'openstax_mimir_sft': 'openstax-sft',
    'mimir_grounded_expanded_sft': 'mimir-grounded-expanded-sft',
    'mimir_answer_contract_calibration': 'mimir-answer-contract-calibration',
    'mimir_benchmark_campaigns': 'mimir-benchmark-campaigns',
    'danish_lexical_sft': 'danish-lexical',
    'tidsskrift_open_sft': 'tidsskrift-open',
    'tidsskrift_open_chats': 'tidsskrift-open-chats',
    'danish_wikipedia_open_chats': 'danish-wikipedia-open-chats',
    'openstax_open_chats': 'openstax-open-chats',
    'dfm10_synthetic_values_model_charter': 'synthetic-values-model-charter',
    'dfm10_synthetic_values_model_charter_da': 'synthetic-values-model-charter-da',
    'danish_persona_chats': 'danish-persona-chats',
    'domsdatabasen_grounded_chats': 'domsdatabasen-grounded-chats',
    'medical': 'medical',
    'medquad': 'medquad',
}


def roots(work):
    # The component sources are frozen local inputs (see the DFM10 rebuild
    # recipe): the same reservoirs source_index() enumerates.
    allowed_roots = [work.parent, work, ROOT / 'data/converted_sources',
                     ROOT / 'data/mimir_benchmark_campaigns',
                     ROOT / 'data/mimir_answer_contract_calibration']
    allowed_roots += sorted((ROOT / 'data').glob('dfm10_*source*'))
    return allowed_roots


def source_path_ok(rel):
    """Containment on the in-repo path; content is digest-pinned.

    Reservoir trees may contain symlinks to files outside the repo, so the
    check must not resolve symlinks — prepare verifies sha256 and size
    against the lock instead.
    """
    path = ROOT / rel
    if path.is_relative_to(QUEUE):
        return True
    prefixes = ['data/converted_sources', 'data/mimir_benchmark_campaigns',
                'data/mimir_answer_contract_calibration']
    prefixes += [p.relative_to(ROOT).as_posix()
                 for p in sorted((ROOT / 'data').glob('dfm10_*source*'))]
    return any(rel == prefix or rel.startswith(prefix + '/')
               for prefix in prefixes)


def source_index():
    index = {}
    roots = [ROOT / 'data/converted_sources',
             ROOT / 'data/mimir_benchmark_campaigns',
             ROOT / 'data/mimir_answer_contract_calibration']
    roots += sorted((ROOT / 'data').glob('dfm10_*source*'))
    seen = set()
    for root in roots:
        if not root.is_dir():
            if root.name.startswith('dfm10_') and root.suffix:
                continue
            raise ValueError(f'DFM10 source root missing: {root}')
        for dirpath, dirs, files in os.walk(root, followlinks=True):
            real = os.path.realpath(dirpath)
            if real in seen:
                dirs[:] = []
                continue
            seen.add(real)
            dirs[:] = [d for d in dirs if not d.startswith(('tokenized_', 'sampled_'))]
            for f in files:
                path = Path(dirpath) / f
                try:
                    st = path.stat()
                except OSError:
                    continue
                index.setdefault((int(st.st_mtime), st.st_size), []).append(
                    path.relative_to(ROOT).as_posix())
    return index


def component_tasks():
    manifest = load(MANIFEST)
    counts = manifest['task_counts']
    labels = [k for k in counts if k not in ('dfm9', 'output')]
    if set(labels) != set(LABEL_TO_FLAG):
        raise ValueError('DFM10 manifest labels differ from the recipe mapping')
    return manifest, labels, counts


def resolve_sources(work):
    manifest, labels, counts = component_tasks()
    index = source_index()
    tasks = []
    for label in labels:
        tree = ROOT / (manifest[label] if label in manifest else FALLBACK_TREES[label])
        resolved = 0
        for task_dir in sorted(tree.iterdir()):
            meta_path = task_dir / 'metadata.json'
            if not meta_path.is_file():
                continue
            meta = load(meta_path)
            key = (int(meta['source_mtime']), int(meta['source_size']))
            hits = index.get(key, [])
            if not hits and task_dir.name in FALLBACK_SOURCES:
                fallback = ROOT / FALLBACK_SOURCES[task_dir.name]
                if fallback.is_file() and fallback.stat().st_size == key[1]:
                    hits = [FALLBACK_SOURCES[task_dir.name]]
            if len(hits) > 1:
                if len({digest_file(ROOT / h) for h in hits}) != 1:
                    raise ValueError(
                        f'{task_dir.name}: ambiguous DFM10 sources with different content')
                hits.sort(key=lambda p: (not p.startswith('data/converted_sources/'), p))
            if not hits:
                raise ValueError(
                    f'{task_dir.name}: no DFM10 source candidate for '
                    f'{key} under the frozen source roots')
            native = label == NATIVE_LABEL
            tasks.append(dict(task=task_dir.name, component=label,
                              source=hits[0], source_mtime=key[0],
                              source_size=key[1], native=native))
            resolved += 1
        if resolved != counts[label]:
            raise ValueError(f'{label}: resolved {resolved} tasks, manifest says {counts[label]}')
    if len(tasks) != len({x['task'] for x in tasks}):
        raise ValueError('DFM10 task names are not unique')
    replaced = 0
    for entry in BASE_INVENTORY.iterdir():
        if entry.is_dir() and entry.name.startswith(REPLACED_BASE_PREFIXES):
            replaced += 1
    base_tasks = sum(1 for x in BASE_INVENTORY.iterdir()
                     if x.is_dir() and (x / 'metadata.json').is_file())
    composition = {'base_entries': base_tasks + 2, 'replaced_base': replaced,
                   'base_tasks': base_tasks - replaced, 'addition_tasks': len(tasks),
                   'total_tasks': base_tasks - replaced + len(tasks) + 2}
    return tasks, composition, counts


def digest_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 24), b''):
            h.update(chunk)
    return h.hexdigest()


def recover_lock(work):
    dfm9 = load(QUEUE / 'dfm9/verified.json')
    if dfm9.get('status') != 'matched':
        raise ValueError('DFM10 requires a verified DFM9 rebuild union')
    tasks, composition, counts = resolve_sources(work)
    if composition['total_tasks'] != len([x for x in REFERENCE.iterdir()]):
        raise ValueError('DFM10 composition differs from the historical union size')
    for i, item in enumerate(tasks, 1):
        item['sha256'] = digest_file(ROOT / item['source'])
        if i % 250 == 0:
            print(f'Digested DFM10 sources {i}/{len(tasks)}', flush=True)
    dfm9_cfg = load(ROOT / 'config/data/dfm9_hf_rebuild.json')
    prefix = subprocess.check_output(
        ['git', 'show', DATA_IO_REVISION + ':prefix_config_dfm10.yaml'],
        cwd=ROOT / 'data_io')
    config = dict(version=10, recipe='dfm10-hf-v1', epochs=10, seed=0, concat_workers=4,
                  adapter_revision=ADAPTER_REVISION,
                  native_adapter_revision=NATIVE_ADAPTER_REVISION,
                  builder_revision=BUILDER_REVISION,
                  template_revision=TEMPLATE_REVISION, data_io_revision=DATA_IO_REVISION,
                  native_max_seq_len=NATIVE_MAX_SEQ_LEN,
                  tokenizer_repo=dfm9_cfg['tokenizer_repo'],
                  tokenizer_revision=dfm9_cfg['tokenizer_revision'],
                  tokenizer_post_processor=dfm9_cfg['tokenizer_post_processor'],
                  tokenizer_semantic_sha256=dfm9_cfg['tokenizer_semantic_sha256'],
                  tokenizer_info=dfm9_cfg['tokenizer_info'],
                  prefix_config_sha256=hashlib.sha256(prefix).hexdigest(),
                  base_union='data/rebuild_hf_dfm/serial-queue/dfm9/union',
                  manifest_labels=sorted(counts), tasks=tasks, acquisitions={},
                  composition=composition)
    write_json(CONFIG, config)
    print(f'Wrote {CONFIG}: {composition}', flush=True)


def check_config(work):
    cfg = load(CONFIG)
    if digest(CONFIG) != load(work / 'inputs-verified.json')['config_sha256']:
        raise ValueError('DFM10 input lock changed')
    return cfg


def git_show(repo, revision, rel):
    return subprocess.check_output(['git', 'show', revision + ':' + rel], cwd=repo)


def prepare(work):
    if (work / 'inputs-verified.json').exists():
        cfg = check_config(work)
    else:
        cfg = load(CONFIG)
    if load(QUEUE / 'dfm9/verified.json').get('status') != 'matched':
        raise ValueError('DFM9 verification required for DFM10')
    if not (BASE_UNION / 'tokenizer_info.json').is_file():
        raise ValueError('The rebuilt DFM9 union is missing')
    work_dir = ROOT / 'data_io'
    staged_prefix = work / 'prefix_config.yaml'
    staged_prefix.write_bytes(git_show(work_dir, DATA_IO_REVISION, 'prefix_config_dfm10.yaml'))
    if digest(staged_prefix) != cfg['prefix_config_sha256']:
        raise ValueError('Sampling policy changed')
    template = work / 'chat_template.jinja'
    # The DFM10-era template is the one committed with the DFM10 data_io pin
    # (1f52b10 added the mapping/sequence tool-body handling the DFM10
    # sources require; 0483afe predates it and cannot tokenize them).
    template.write_bytes(git_show(work_dir, DATA_IO_REVISION,
                                  'chat_templates/gemma4_native_chat.jinja'))
    if template.read_bytes() != git_show(work_dir, TEMPLATE_REVISION,
                                         'chat_templates/gemma4_native_chat.jinja'):
        raise ValueError('Chat template changed between the pinned revisions')
    for revision, rel, target in [
            (cfg['adapter_revision'], 'scripts/tokenize_chat_template.py',
             'historical_adapter.py'),
            (cfg['native_adapter_revision'], 'scripts/tokenize_chat_template.py',
             'native_adapter.py'),
            (cfg['builder_revision'], 'scripts/build_tokenized_dfm10_tree.py',
             'build_dfm10_union.py')]:
        (work / target).write_bytes(git_show(ROOT, revision, rel))
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
        raise ValueError('HF tokenizer vocabulary/normalization differs from historical DFM10')
    (work / 'tokenizer').mkdir(exist_ok=True)
    write_json(work / 'tokenizer/tokenizer.json', definition)
    gate = ROOT / 'data/tokenized_dfm10_dst_table_prompts_repaired/production_gate.json'
    if not gate.is_file():
        raise ValueError('The DST production grounding gate is missing')
    shutil.copyfile(gate, work / 'production_gate.json')
    for stale in ('sources', 'sources_native', 'tokenized', 'tokenized_native',
                  'components', 'union'):
        if (work / stale).exists():
            shutil.rmtree(work / stale)
    (work / 'sources').mkdir()
    (work / 'sources_native').mkdir()
    checked = 0
    for i, item in enumerate(cfg['tasks'], 1):
        rel = item['source']
        if not source_path_ok(rel):
            raise ValueError(f'DFM10 source outside the pinned reservoirs: {rel}')
        source = ROOT / rel
        if not source.is_file() or source.stat().st_size != item['source_size'] \
                or digest_file(source) != item['sha256']:
            raise ValueError(f'DFM10 source missing or changed: {rel}')
        farm = work / ('sources_native' if item['native'] else 'sources') / item['task']
        farm.parent.mkdir(parents=True, exist_ok=True)
        farm.symlink_to(source.resolve())
        checked += 1
        if i % 250 == 0:
            print(f'Staged DFM10 sources {i}/{len(cfg["tasks"])}', flush=True)
    write_json(work / 'inputs-verified.json', dict(
        inputs=checked, config_sha256=digest(CONFIG)))
    write_json(work / 'recipe.json', cfg)


def tokenize(work):
    from scripts.queue_dfm_hf_rebuild import safe_tokenizer_workers
    cfg = check_config(work)
    standard = {x['task'] for x in cfg['tasks'] if not x['native']}
    native = {x['task'] for x in cfg['tasks'] if x['native']}
    if {x.name for x in (work / 'sources').iterdir()} != standard \
            or {x.name for x in (work / 'sources_native').iterdir()} != native:
        raise ValueError('Unexpected DFM10 source inventory')
    from scripts.restore_dfm10_token_limits import COMPONENTS as CAPPED_COMPONENTS
    from scripts.restore_dfm10_swe_targets import COMPONENTS as SWE_COMPONENTS
    COMPONENTS=CAPPED_COMPONENTS | SWE_COMPONENTS
    unlimited=work/'sources_unlimited'
    unlimited.mkdir(exist_ok=True)
    for item in cfg['tasks']:
        stale=unlimited/item['task']
        if item['component'] in COMPONENTS and stale.is_symlink():stale.unlink()
    for item in cfg['tasks']:
        if not item['native'] and item['component'] not in COMPONENTS:
            link(work/'sources'/item['task'],unlimited/item['task'],roots(work))
    subprocess.run([sys.executable, str(ROOT / 'scripts/tokenize_historical_chat.py'),
                    '--input', str(unlimited), '--output', str(work / 'tokenized'),
                    '--adapter', str(work / 'historical_adapter.py'),
                    '--tokenizer', str(work / 'tokenizer/tokenizer.json'),
                    '--template', str(work / 'chat_template.jinja'),
                    '--workers', str(safe_tokenizer_workers())], check=True)
    subprocess.run([sys.executable,str(ROOT/'scripts/restore_dfm10_token_limits.py'),'--work',str(work),'--config',str(CONFIG)],check=True)
    subprocess.run([sys.executable,str(ROOT/'scripts/restore_dfm10_swe_targets.py'),'--work',str(work),'--config',str(CONFIG)],check=True)
    tokenized = {x.name for x in (work / 'tokenized').iterdir() if x.is_dir()}
    if tokenized != standard:
        raise ValueError('Tokenized DFM10 additions differ from the locked inventory')
    subprocess.run([sys.executable, str(ROOT / 'scripts/tokenize_dfm10_native_sharded.py'),
                    '--work', str(work), '--config', str(CONFIG)], check=True)
    native_done = {x.name for x in (work / 'tokenized_native').iterdir() if x.is_dir()}
    if native_done != native:
        raise ValueError('Native tokenized DFM10 tasks differ from the locked inventory')
    write_json(work / 'tokenized/tokenizer_info.json', cfg['tokenizer_info'])
    write_json(work / 'tokenized_native/tokenizer_info.json', cfg['tokenizer_info'])


def component_tree_name(manifest, label):
    path = manifest.get(label, FALLBACK_TREES.get(label))
    if not path:
        raise ValueError(f"Missing component path: {label}")
    return Path(path).name


def assemble(work):
    cfg = check_config(work)
    if (work / 'tokenized/tokenizer_info.json').read_bytes() != \
            (work / 'tokenized_native/tokenizer_info.json').read_bytes():
        raise ValueError('DFM10 tokenizer info differs between the two tokenization modes')
    manifest, labels, counts = component_tasks()
    components = work / 'components'
    components.mkdir(exist_ok=True)
    for label in labels:
        tree = components / component_tree_name(manifest, label)
        if tree.is_symlink():
            raise ValueError(f"Component directory must not be a symlink: {tree}")
        tree.mkdir(exist_ok=True)
        write_json(tree / 'tokenizer_info.json', cfg['tokenizer_info'])
        for item in cfg['tasks']:
            if item['component'] != label:
                continue
            source = work / ('tokenized_native' if item['native'] else 'tokenized') \
                / item['task']
            link(source, tree / item['task'], roots(work))
        if label == 'dst_table_prompts_repaired':
            shutil.copyfile(work / 'production_gate.json',
                            tree / 'production_gate.json')
    union = work / 'union'
    argv = [sys.executable, str(work / 'build_dfm10_union.py'),
            '--base', str(BASE_UNION), '--output', str(union)]
    for label in labels:
        argv += ['--' + LABEL_TO_FLAG[label],
                 str(components / component_tree_name(manifest, label))]
    subprocess.run(argv, check=True, cwd=work)
    produced = {x.name for x in union.iterdir() if x.is_dir()}
    wanted = {x.name for x in REFERENCE.iterdir() if x.is_dir()}
    if produced != wanted:
        raise ValueError('Union task inventory differs from historical DFM10')
    write_json(work / 'assemble-receipt.json', dict(
        status='assembled', base_tasks=cfg['composition']['base_tasks'],
        additions=cfg['composition']['addition_tasks'],
        total_tasks=cfg['composition']['total_tasks']))


def verify(work):
    cfg = check_config(work)
    union = work / 'union'
    for i, item in enumerate(cfg['tasks'], 1):
        # Production arrays are read-only comparison targets, never rebuild inputs.
        reference = (REFERENCE / item['task']).resolve(strict=True)
        allowed(union / item['task'], [QUEUE])
        for field in FIELDS:
            equal_arrays(np.load(union / item['task'] / f'{field}.npy', mmap_mode='r'),
                         np.load(reference / f'{field}.npy', mmap_mode='r'),
                         item['task'] + '/' + field)
        if i % 250 == 0:
            print(f'Compared DFM10 additions {i}/{len(cfg["tasks"])}', flush=True)
    print(f'Compared {len(cfg["tasks"])} fresh tasks against the historical arrays',
          flush=True)
    write_json(work / 'all-token-comparison.json', dict(
        status='matched', tasks=len(cfg['tasks']),
        inventory=cfg['composition']['total_tasks'],
        scope='fresh additions plus the DFM9 base verified in the DFM9 receipt'))


def main():
    global CONFIG
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('recover-lock', 'prepare', 'tokenize',
                                     'assemble', 'verify'))
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--config', type=Path, default=CONFIG)
    args = p.parse_args()
    CONFIG = args.config.resolve()
    if load(CONFIG).get('recipe') == 'dfm10-hf-v1':
        raise ValueError('Legacy local-source DFM10 recipe disabled: HF-only acquisition and source reconstruction required')
    args.work.mkdir(parents=True, exist_ok=True)
    with (args.work / 'stage.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        {'recover-lock': recover_lock, 'prepare': prepare, 'tokenize': tokenize,
         'assemble': assemble, 'verify': verify}[args.stage](args.work)


if __name__ == '__main__':
    main()
