"""CPU-only serial HF rebuild queue, isolated from the training scheduler.

Only completed, comparison-verified predecessors release a successor. Recipes
not yet recovered are explicit holds, never substituted with production data.
"""
import argparse
import fcntl
import hashlib
from itertools import zip_longest
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import numpy as np
import pyarrow.parquet as pq

from scripts.replay_dfm_serial import equal_arrays, FIELDS, write_json

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
# Preserved sampling exposure per version: DFM4-6 shipped five epochs; DFM7's
# preserved sample is the documented six-epoch extension (epochs 0-4 unchanged);
# DFM8's preserved sample is the seven-epoch extension (epochs 0-5 unchanged).
SAMPLE_EPOCHS = {4: 5, 5: 5, 6: 5, 7: 6, 8: 7, 9: 10, 10: 10, 11: 10}


def safe_tokenizer_workers():
    settings = load(ROOT / 'config/data/hf_rebuild_runtime.json')
    if settings['tokenizer_driver'] != 'scripts/tokenize_hrm_hf.py':
        raise ValueError('Historical rebuild requires the bounded-memory HF tokenizer')
    workers = int(settings['tokenizer_workers'])
    if not 1 <= workers <= 64:
        raise ValueError('HF rebuild tokenizer workers must be between 1 and 64')
    return workers


def load(path):
    return json.loads(path.read_text())


def require_allowed(path, roots):
    resolved = path.resolve(strict=True)
    if not any(resolved.is_relative_to(root.resolve()) for root in roots):
        raise ValueError(f'Forbidden local rebuild input: {path} -> {resolved}')


def initialize(queue, acquisition):
    queue.mkdir(parents=True, exist_ok=False)
    work = queue / 'dfm1'
    work.mkdir()
    historical = subprocess.check_output(
        ['git', 'show', '45a297f:config/data/source_filter.yaml'], cwd=ROOT)
    (work / 'source_filter.yaml').write_bytes(historical)
    shutil.copyfile(ROOT / 'data_io/prefix_config_dfm.yaml', work / 'prefix_config.yaml')
    stages = ['prepare', 'filter', 'convert', 'split_swe', 'layout', 'tokenize', 'sample', 'compare']
    rows = []
    for version in range(1, 16):
        rows.append(dict(version=version, depends_on=version-1 if version > 1 else None,
                         status='pending', phase=None, completed_stages=[],
                         recipe='dfm1-hf-v1' if version == 1 else None,
                         stages=stages if version == 1 else
                         ['acquire_hf_additions', 'convert', 'tokenize', 'assemble', 'sample', 'compare'],
                         recipe_hold=None if version == 1 else
                         'HF-only recipe/input lock must be recovered; local reservoirs forbidden'))
    write_json(queue / 'plan.json', dict(
        policy='HF-only; local lexdk/DBC only; serial successful comparisons required',
        acquisition=str(acquisition.resolve()), tokenizer_workers=32, rows=rows))


def prepare(queue):
    plan = load(queue / 'plan.json')
    acquisition = Path(plan['acquisition'])
    manifest = load(acquisition / 'dfm1-hf-inputs.json')
    if manifest['status'] != 'inputs_downloaded':
        raise ValueError('HF acquisition incomplete')
    work = queue / 'dfm1'
    inputs = work / 'inputs'
    inputs.mkdir(exist_ok=True)
    for source in manifest['hf_sources']:
        if source['status'] != 'downloaded':
            raise ValueError(f'Incomplete source: {source["name"]}')
        root = Path(source['download_path'])
        require_allowed(root, [acquisition / 'downloads'])
        for file in source['files']:
            path = root / file['path']
            require_allowed(path, [acquisition / 'downloads'])
            if path.stat().st_size != file['size']:
                raise ValueError(f'Download size mismatch: {path}')
            # Restore the original root-level OPUS input layout from the HF package.
            rel = Path(file['path'])
            if source['name'] == 'opus' and rel == Path('data/opus_da_en.jsonl.gz'):
                rel = Path('opus_da_en.jsonl.gz')
            destination = inputs / source['name'] / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                destination.symlink_to(path.resolve())
    for name in ('lexdk', 'dbc'):
        destination = inputs / name
        destination.mkdir(exist_ok=True)
        for path in (ROOT / 'data/downloads/datasets' / name).glob('*.jsonl.gz'):
            target = destination / path.name
            if not target.exists():
                target.symlink_to(path.resolve())
        if not any(destination.iterdir()):
            raise ValueError(f'Missing agreement source: {name}')
    write_json(work / 'input-provenance.json', dict(
        acquisition_manifest=manifest,
        agreements=[str(ROOT / 'data/downloads/datasets' / name) for name in ('dbc', 'lexdk')],
        filter_git_revision='45a297f',
        converter_sha256=hashlib.sha256((ROOT / 'scripts/convert_filtered_sources.py').read_bytes()).hexdigest()))


def check_layout(queue):
    converted = queue / 'dfm1/converted'
    actual = {'__'.join(p.relative_to(converted).parts) for p in converted.rglob('*')
              if p.is_file() and p.suffix in ('.parquet', '.jsonl')}
    reference = {p.name for p in (ROOT / 'data/tokenized_mixed').iterdir() if p.is_dir()}
    report = dict(missing=sorted(reference-actual), extra=sorted(actual-reference),
                  reference_tasks=len(reference), rebuilt_tasks=len(actual))
    write_json(queue / 'dfm1/layout-comparison.json', report)
    if report['missing'] or report['extra']:
        raise ValueError('Source/task layout differs; inspect layout-comparison.json before tokenizing')


def split_swe(queue):
    """Replay the historical contiguous 468-row-group split, not equal row cuts."""
    root = queue / 'dfm1/converted/nemotron_swe/data'
    source = root / 'swe.parquet'
    parked = root / 'swe.parquet.unsplit'
    pf = pq.ParquetFile(source if source.exists() else parked)
    if pf.num_row_groups != 468 or pf.metadata.num_rows != 1915306:
        raise ValueError('SWE conversion differs from the historical 468 groups / 1915306 rows')
    counts = []
    for i in range(10):
        destination = root / f'swe_part_{i:02d}.parquet'
        temporary = destination.with_suffix('.tmp')
        count = 0
        with pq.ParquetWriter(temporary, pf.schema_arrow, compression='zstd') as writer:
            for group in range(round(i * 468 / 10), round((i + 1) * 468 / 10)):
                table = pf.read_row_group(group)
                writer.write_table(table)
                count += table.num_rows
        os.replace(temporary, destination)
        counts.append(count)
    if source.exists():
        source.rename(parked)
    write_json(root / 'split-receipt.json', dict(row_counts=counts, method='rounded row-group boundaries'))


def compare(queue, version=1):
    sample = queue / f'dfm{version}/sampled'
    reference = ROOT / ('data/sampled_dfm' if version == 1 else f'data/sampled_dfm{version}')
    epochs = sorted(p.name for p in reference.glob('epoch_*') if p.is_dir())
    expected_epochs = [f'epoch_{i}' for i in range(SAMPLE_EPOCHS.get(version, 4))]
    if epochs != expected_epochs or sorted(p.name for p in sample.glob('epoch_*')
                                          if p.is_dir()) != epochs:
        raise ValueError('Preserved/rebuilt epoch inventory mismatch')
    files = [Path('tokens.npy')] + [Path(epoch) / f'{field}.npy'
                                  for epoch in epochs for field in FIELDS]
    for rel in files:
        print(f'Comparing {rel}', flush=True)
        equal_arrays(np.load(sample / rel, mmap_mode='r'),
                     np.load(reference / rel, mmap_mode='r'), str(rel))
    rebuilt, expected = load(sample / 'metadata.json'), load(reference / 'metadata.json')
    if rebuilt != expected:
        raise ValueError('Sample metadata mismatch')
    write_json(queue / f'dfm{version}/verified.json', dict(
        version=version, status='matched', input_policy=(
            'HF-rebuilt DFM9 base plus digest-pinned local DFM10 additions; not HF-only'
            if version == 10 else 'HF-only plus lexdk/DBC'),
        scope='all token and epoch-index values; metadata', verified_files=len(files)))


def enable_dfm2(queue, regenerate=False):
    with (queue / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if load(queue / 'dfm1/verified.json')['status'] != 'matched':
            raise ValueError('DFM1 must be verified first')
        work = queue / 'dfm2'
        work.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / 'data_io/prefix_config_dfm2.yaml', work / 'prefix_config.yaml')
        plan = load(queue / 'plan.json')
        row = next(r for r in plan['rows'] if r['version'] == 2)
        row.update(recipe='dfm2-hf-v1', recipe_hold=None, status='pending',
                   transform_source='regenerate' if regenerate else 'hf-package',
                   stages=['prepare', 'generate', 'tokenize', 'assemble', 'sample', 'compare'])
        row.pop('error', None)
        plan['tokenizer_workers'] = 16
        write_json(queue / 'plan.json', plan)


def prepare_dfm2(queue):
    source = queue / 'dfm1/converted/danish_dynaword'
    files = sorted(source.rglob('*.parquet'))
    if len(files) != 45:
        raise ValueError(f'Expected 45 reconstructed DynaWord files, found {len(files)}')
    require_allowed(source, [queue / 'dfm1/converted'])
    provenance = load(queue / 'dfm1/input-provenance.json')
    write_json(queue / 'dfm2/input-provenance.json', dict(
        predecessor=load(queue / 'dfm1/verified.json'),
        hf_sources=[s for s in provenance['acquisition_manifest']['hf_sources']
                    if s['name'] == 'danish_dynaword'],
        input_root=str(source), seed=20260530, max_chars=3000,
        historical_full_reconstruction=True,
        generator_sha256=hashlib.sha256(
            (ROOT / 'scripts/generate_dfm2_dynaword_tasks.py').read_bytes()).hexdigest()))


def repair_dfm2(queue, version=2):
    with (queue / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = load(queue / 'plan.json')
        row = next(r for r in plan['rows'] if r['version'] == version)
        if row['status'] == 'done':
            raise ValueError(f'Refusing to reset a verified DFM{version}')
        write_json(queue / f'dfm{version}/shortened-reconstruction-failure.json', row)
        retained = [s for s in row['completed_stages'] if s in ('acquire', 'convert')] if version == 3 else []
        row.update(status='pending', phase=None, completed_stages=retained)
        row.pop('error', None)
        write_json(queue / 'plan.json', plan)


def verify_dfm2_rows(work, version=2):
    rebuilt = work / 'converted'
    historical = ROOT / ('data/converted_sources_dfm2_dynaword_tasks' if version == 2
                         else 'data/converted_sources_dfm3_common_pile_tasks')
    files = sorted(rebuilt.rglob('*.parquet'))
    expected_count = 450 if version == 2 else 2862
    if len(files) != expected_count:
        raise ValueError(f'Expected {expected_count} generated files, found {len(files)}')
    total = 0
    for path in files:
        reference = historical / path.relative_to(rebuilt)
        left, right = pq.ParquetFile(path), pq.ParquetFile(reference)
        if left.metadata.num_rows != right.metadata.num_rows:
            raise ValueError(f'Generated row count mismatch: {path}')
        for a, b in zip_longest(left.iter_batches(batch_size=4096),
                               right.iter_batches(batch_size=4096)):
            if a is None or b is None or not a.equals(b):
                raise ValueError(f'Generated content mismatch: {path}')
        total += left.metadata.num_rows
    write_json(work / 'generated-row-comparison.json',
               dict(status='matched', files=len(files), rows=total))


def enable_dfm3(queue, regenerate=False):
    # The running coordinator owns the plan until its current recipe finishes.
    # Wait rather than racing its whole-plan writes.
    with (queue / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        work = queue / 'dfm3'
        work.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / 'data_io/prefix_config_dfm3.yaml', work / 'prefix_config.yaml')
        plan = load(queue / 'plan.json')
        for row in plan['rows']:
            if row['version'] >= 3:
                row['tokenizer_workers'] = 32
            if row['version'] == 3:
                row.update(recipe='dfm3-hf-v1', recipe_hold=None, status='pending',
                           transform_source='regenerate' if regenerate else 'hf-package',
                           stages=['acquire', 'convert', 'generate', 'tokenize',
                                   'assemble', 'sample', 'compare'])
                row.pop('error', None)
        plan['tokenizer_workers'] = 32
        write_json(queue / 'plan.json', plan)


def dfm3_command(queue, stage):
    work = queue / 'dfm3'
    package_command = package_stage(queue, stage, 3)
    if package_command is not None:
        return package_command
    if stage == 'acquire':
        return [PYTHON, str(ROOT / 'scripts/acquire_dfm3_rebuild.py'), '--work', str(work)]
    if stage == 'convert':
        return [PYTHON, str(ROOT / 'scripts/convert_filtered_sources.py'),
                '--input-root', str(work / 'inputs'), '--output-root', str(work / 'raw_converted'),
                '--workers', '8', '--copy-ready', '--require-convert-meta',
                '--dynaword-chars', '12000']
    if stage == 'generate':
        return [PYTHON, str(ROOT / 'scripts/generate_dfm3_common_pile_tasks.py'),
                '--input-root', str(work / 'raw_converted'),
                '--output-root', str(work / 'converted'), '--max-chars', '3000',
                '--seed', '20260531', '--historical-full-reconstruction', '--force']
    if stage == 'tokenize':
        if not (work / 'package-input.json').exists():
            verify_dfm2_rows(work, version=3)
        actual = {'__'.join(p.relative_to(work / 'converted').parts)
                  for p in (work / 'converted').rglob('*.parquet')}
        reference = {p.name for p in (ROOT / 'data/tokenized_dfm3_common_pile_tasks').iterdir()
                     if p.is_dir()}
        write_json(work / 'layout-comparison.json',
                   dict(missing=sorted(reference-actual), extra=sorted(actual-reference)))
        if actual != reference:
            raise ValueError('DFM3 generated task layout differs')
        workers = safe_tokenizer_workers()
        return [PYTHON, str(ROOT / 'scripts/tokenize_hrm_hf.py'), str(work / 'converted'),
                '--tokenizer-path', str(ROOT / 'data_io/trained_tokenizers/bpe/tokenizer.json'),
                '--workers', str(workers), '-o', str(work / 'tokenized_extra')]
    if stage == 'assemble':
        # Enumerate physical rebuilt roots, not symlink unions (rglob skips symlink dirs).
        return [PYTHON, str(ROOT / 'scripts/build_tokenized_dfm3_tree.py'), '--roots',
                str(queue / 'dfm1/tokenized'), str(queue / 'dfm2/tokenized_extra'),
                str(work / 'tokenized_extra'), '--output', str(work / 'tokenized'), '--force']
    if stage == 'sample':
        return [PYTHON, str(ROOT / 'data_io/sample_tokenized.py'),
                f'tokenized_path={work / "tokenized"}', f'output_path={work / "sampled"}',
                f'prefix_config_path={work / "prefix_config.yaml"}',
                'epochs=4', 'seed=0', 'concat_workers=1']
    return None


def enable_dfm4(queue, regenerate=False):
    with (queue / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if load(queue / 'dfm3/verified.json')['status'] != 'matched':
            raise ValueError('DFM3 must pass before DFM4')
        if regenerate:
            for version in (2, 3):
                if load(queue / f'dfm{version}/hf-publication.json')['status'] != 'uploaded_sha256_verified':
                    raise ValueError('Historical publication is incomplete')
        plan = load(queue / 'plan.json')
        row = next(r for r in plan['rows'] if r['version'] == 4)
        if row['status'] == 'done':
            raise ValueError('Refusing to alter completed DFM4')
        if regenerate:
            if load(queue / 'dfm4/preparation.json')['status'] != 'hf_additions_acquired':
                raise ValueError('DFM4 additions not downloaded')
            stages = ['paragraph', 'summary', 'verify-rows']
        else:
            spec = load(ROOT / 'config/data/historical_rebuild_packages.json').get('4', {})
            if not re.fullmatch('[0-9a-f]{40}', spec.get('revision', '')) or not re.fullmatch(
                    '[0-9a-f]{64}', spec.get('manifest_sha256', '')):
                raise ValueError('DFM4 requires a verified registry publication pin')
            stages = ['fetch-package']
        (queue / 'dfm4').mkdir(exist_ok=True)
        row.update(recipe='dfm4-hf-v1', recipe_hold=None, status='pending',
                   completed_stages=[], phase=None,
                   transform_source='regenerate' if regenerate else 'hf-package',
                   tokenizer_workers=safe_tokenizer_workers(),
                   stages=stages + ['tokenize-paragraph',
                           'tokenize-summary', 'verify-tokens', 'assemble', 'sample', 'compare'])
        row.pop('error', None)
        write_json(queue / 'plan.json', plan)


def dfm4_command(queue, stage):
    work = queue / 'dfm4'
    if stage == 'fetch-package':
        return [PYTHON, str(ROOT / 'scripts/fetch_dfm4_historical.py'), '--work', str(work)]
    if stage in ('paragraph', 'summary', 'verify-rows', 'verify-tokens'):
        return [PYTHON, str(ROOT / 'scripts/rebuild_dfm4_additions.py'), stage,
                '--work', str(work), '--workers', '8']
    if stage in ('tokenize-paragraph', 'tokenize-summary'):
        kind = stage.removeprefix('tokenize-')
        return [PYTHON, str(ROOT / 'scripts/tokenize_hrm_hf.py'), str(work / kind),
                '--tokenizer-path', str(ROOT / 'data_io/trained_tokenizers/bpe/tokenizer.json'),
                '--workers', str(safe_tokenizer_workers()), '-o', str(work / f'tokenized_{kind}')]
    if stage == 'assemble':
        return [PYTHON, str(ROOT / 'scripts/build_tokenized_dfm4_tree.py'), '--roots',
                str(queue / 'dfm3/tokenized'), str(work / 'tokenized_paragraph'),
                str(work / 'tokenized_summary'), '--output', str(work / 'tokenized'), '--force']
    if stage == 'sample':
        return [PYTHON, str(ROOT / 'data_io/sample_tokenized.py'),
                f'tokenized_path={work / "tokenized"}', f'output_path={work / "sampled"}',
                f'prefix_config_path={work / "prefix_config.yaml"}',
                'epochs=5', 'seed=0', 'concat_workers=1']
    return None


def enable_dfm5(queue):
    with (queue / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for version in range(1, 5):
            if load(queue / f'dfm{version}/verified.json')['status'] != 'matched':
                raise ValueError(f'DFM{version} must be verified before DFM5')
        plan = load(queue / 'plan.json')
        row = next(r for r in plan['rows'] if r['version'] == 5)
        if row['status'] == 'done':
            raise ValueError('Refusing to reset verified DFM5')
        if row.get('recipe') not in (None, 'dfm5-hf-v1'):
            raise ValueError('Unexpected existing DFM5 recipe')
        (queue / 'dfm5').mkdir(exist_ok=True)
        row.update(recipe='dfm5-hf-v1', recipe_hold=None, status='pending', phase=None,
                   tokenizer_workers=safe_tokenizer_workers(),
                   stages=['prepare', 'tokenize-sapient', 'verify-sapient',
                           'recover-synth', 'tokenize-synth', 'verify-synth',
                           'recover-exports', 'tokenize-exports', 'verify-exports',
                           'assemble', 'verify-all', 'sample', 'compare'])
        row.pop('error', None)
        write_json(queue / 'plan.json', plan)


def dfm5_command(queue, stage):
    work = queue / 'dfm5'
    if stage.startswith('tokenize-'):
        kind = stage.removeprefix('tokenize-')
        if kind not in ('sapient', 'synth', 'exports'):
            raise ValueError('Unknown DFM5 tokenizer stage')
        return [PYTHON, str(ROOT / 'scripts/tokenize_hrm_hf.py'), str(work / kind),
                '--tokenizer-path', str(ROOT / 'data_io/trained_tokenizers/bpe/tokenizer.json'),
                '--workers', str(safe_tokenizer_workers()), '-o', str(work / f'tokenized_{kind}')]
    if stage == 'sample':
        if load(work / 'all-token-comparison.json')['status'] != 'matched':
            raise ValueError('DFM5 source arrays must match before sampling')
        recipe = load(work / 'recipe.json')
        if hashlib.sha256((work / 'prefix_config.yaml').read_bytes()).hexdigest() != recipe['prefix_config_sha256']:
            raise ValueError('Frozen sampling policy changed')
        return [PYTHON, str(ROOT / 'data_io/sample_tokenized.py'),
                f'tokenized_path={work / "tokenized"}', f'output_path={work / "sampled"}',
                f'prefix_config_path={work / "prefix_config.yaml"}',
                'epochs=5', 'seed=0', 'concat_workers=1']
    if stage == 'compare':
        return None
    if stage not in ('prepare', 'verify-sapient', 'recover-synth', 'verify-synth',
                     'recover-exports', 'verify-exports', 'assemble', 'verify-all'):
        raise ValueError(f'Unknown DFM5 stage: {stage}')
    return [PYTHON, str(ROOT / 'scripts/rebuild_dfm5.py'), stage, '--work', str(work)]


def enable_dfm6(queue):
    with (queue / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if load(queue / 'dfm5/verified.json')['status'] != 'matched':
            raise ValueError('DFM5 must be verified before DFM6')
        config = load(ROOT / 'config/data/dfm6_hf_rebuild.json')
        if config['version'] != 6 or len(config['tasks']) != 10523:
            raise ValueError('DFM6 input lock incomplete')
        plan = load(queue / 'plan.json')
        row = next(r for r in plan['rows'] if r['version'] == 6)
        if row['status'] == 'done':
            raise ValueError('Refusing to reset verified DFM6')
        if row.get('recipe') not in (None, 'dfm6-hf-v1'):
            raise ValueError('Unexpected DFM6 recipe')
        (queue / 'dfm6').mkdir(exist_ok=True)
        row.update(recipe='dfm6-hf-v1', recipe_hold=None, status='pending', phase=None,
                   tokenizer_workers=safe_tokenizer_workers(),
                   stages=['prepare', 'smoke', 'tokenize', 'verify', 'sample', 'compare'])
        row.pop('error', None)
        write_json(queue / 'plan.json', plan)


def dfm6_command(queue, stage):
    work = queue / 'dfm6'
    if stage == 'sample':
        if load(work / 'all-token-comparison.json')['status'] != 'matched':
            raise ValueError('DFM6 source tokens must match before sampling')
        if hashlib.sha256((work / 'prefix_config.yaml').read_bytes()).hexdigest() != load(
                ROOT / 'config/data/dfm6_hf_rebuild.json')['prefix_config_sha256']:
            raise ValueError('Frozen sampling policy changed')
        return [PYTHON, str(ROOT / 'data_io/sample_tokenized.py'),
                f'tokenized_path={work / "tokenized"}', f'output_path={work / "sampled"}',
                f'prefix_config_path={work / "prefix_config.yaml"}',
                'epochs=5', 'seed=0', 'concat_workers=1']
    if stage == 'compare':
        return None
    if stage not in ('prepare', 'smoke', 'tokenize', 'verify'):
        raise ValueError(f'Unknown DFM6 stage: {stage}')
    return [PYTHON, str(ROOT / 'scripts/rebuild_dfm6.py'), stage, '--work', str(work)]


def enable_dfm7(queue):
    with (queue / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if load(queue / 'dfm6/verified.json')['status'] != 'matched':
            raise ValueError('DFM6 must be verified before DFM7')
        config = load(ROOT / 'config/data/dfm7_hf_rebuild.json')
        if (config['version'] != 7 or config['epochs'] != 6 or len(config['tasks']) != 130
                or len(config['base']['tasks']) != 10521):
            raise ValueError('DFM7 input lock incomplete')
        plan = load(queue / 'plan.json')
        row = next(r for r in plan['rows'] if r['version'] == 7)
        if row['status'] == 'done':
            raise ValueError('Refusing to reset verified DFM7')
        if row.get('recipe') not in (None, 'dfm7-hf-v1'):
            raise ValueError('Unexpected DFM7 recipe')
        (queue / 'dfm7').mkdir(exist_ok=True)
        row.update(recipe='dfm7-hf-v1', recipe_hold=None, status='pending', phase=None,
                   tokenizer_workers=safe_tokenizer_workers(),
                   stages=['prepare', 'convert', 'verify-rows', 'smoke', 'tokenize',
                           'assemble', 'verify', 'sample', 'compare'])
        row.pop('error', None)
        write_json(queue / 'plan.json', plan)


def dfm7_command(queue, stage):
    work = queue / 'dfm7'
    if stage == 'sample':
        if load(work / 'all-token-comparison.json')['status'] != 'matched':
            raise ValueError('DFM7 source tokens must match before sampling')
        if hashlib.sha256((work / 'prefix_config.yaml').read_bytes()).hexdigest() != load(
                ROOT / 'config/data/dfm7_hf_rebuild.json')['prefix_config_sha256']:
            raise ValueError('Frozen sampling policy changed')
        return [PYTHON, str(ROOT / 'data_io/sample_tokenized.py'),
                f'tokenized_path={work / "union"}', f'output_path={work / "sampled"}',
                f'prefix_config_path={work / "prefix_config.yaml"}',
                'epochs=6', 'seed=0', 'concat_workers=1']
    if stage == 'compare':
        return None
    if stage not in ('prepare', 'convert', 'verify-rows', 'smoke', 'tokenize', 'assemble', 'verify'):
        raise ValueError(f'Unknown DFM7 stage: {stage}')
    return [PYTHON, str(ROOT / 'scripts/rebuild_dfm7.py'), stage, '--work', str(work)]


def enable_dfm8(queue):
    with (queue / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if load(queue / 'dfm7/verified.json')['status'] != 'matched':
            raise ValueError('DFM7 must be verified before DFM8')
        config = load(ROOT / 'config/data/dfm8_hf_rebuild.json')
        if (config['version'] != 8 or config['epochs'] != 7 or len(config['tasks']) != 69
                or len(config['base']['tasks']) != 10651):
            raise ValueError('DFM8 input lock incomplete')
        plan = load(queue / 'plan.json')
        row = next(r for r in plan['rows'] if r['version'] == 8)
        if row['status'] == 'done':
            raise ValueError('Refusing to reset verified DFM8')
        if row.get('recipe') not in (None, 'dfm8-hf-v1'):
            raise ValueError('Unexpected DFM8 recipe')
        (queue / 'dfm8').mkdir(exist_ok=True)
        row.update(recipe='dfm8-hf-v1', recipe_hold=None, status='pending', phase=None,
                   tokenizer_workers=safe_tokenizer_workers(),
                   stages=['acquire', 'prepare', 'convert', 'verify-rows', 'smoke', 'tokenize',
                           'assemble', 'verify', 'sample', 'compare'])
        row.pop('error', None)
        plan['tokenizer_workers'] = safe_tokenizer_workers()
        write_json(queue / 'plan.json', plan)
        print('Enabled DFM8 (dfm8-hf-v1); run the guarded runner to execute it.')


def dfm8_command(queue, stage):
    work = queue / 'dfm8'
    if stage == 'sample':
        if load(work / 'all-token-comparison.json')['status'] != 'matched':
            raise ValueError('DFM8 source tokens must match before sampling')
        if hashlib.sha256((work / 'prefix_config.yaml').read_bytes()).hexdigest() != load(
                ROOT / 'config/data/dfm8_hf_rebuild.json')['prefix_config_sha256']:
            raise ValueError('Frozen sampling policy changed')
        return [PYTHON, str(ROOT / 'data_io/sample_tokenized.py'),
                f'tokenized_path={work / "union"}', f'output_path={work / "sampled"}',
                f'prefix_config_path={work / "prefix_config.yaml"}',
                'epochs=7', 'seed=0', 'concat_workers=4']
    if stage == 'compare':
        return None
    if stage not in ('acquire', 'prepare', 'convert', 'verify-rows', 'smoke', 'tokenize',
                     'assemble', 'verify'):
        raise ValueError(f'Unknown DFM8 stage: {stage}')
    return [PYTHON, str(ROOT / 'scripts/rebuild_dfm8.py'), stage, '--work', str(work)]


def enable_dfm9(queue):
    with (queue / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if load(queue / 'dfm8/verified.json')['status'] != 'matched':
            raise ValueError('DFM8 must be verified before DFM9')
        config = load(ROOT / 'config/data/dfm9_hf_rebuild.json')
        if (config['version'] != 9 or config['epochs'] != 10
                or len(config['tasks']) != 693
                or config['composition']['base_links'] != len(config['base'])
                or config['composition']['total_tasks']
                != len(config['base']) + len(config['tasks'])):
            raise ValueError('DFM9 input lock incomplete')
        plan = load(queue / 'plan.json')
        row = next(r for r in plan['rows'] if r['version'] == 9)
        if row['status'] == 'done':
            raise ValueError('Refusing to reset verified DFM9')
        if row.get('recipe') not in (None, 'dfm9-hf-v1'):
            raise ValueError('Unexpected DFM9 recipe')
        (queue / 'dfm9').mkdir(exist_ok=True)
        row.update(recipe='dfm9-hf-v1', recipe_hold=None, status='pending', phase=None,
                   tokenizer_workers=safe_tokenizer_workers(),
                   stages=['prepare', 'convert', 'verify-rows', 'tokenize',
                           'assemble', 'verify', 'sample', 'compare'])
        row.pop('error', None)
        plan['tokenizer_workers'] = safe_tokenizer_workers()
        write_json(queue / 'plan.json', plan)
        print('Enabled DFM9 (dfm9-hf-v1); run the guarded runner to execute it.')


def dfm9_command(queue, stage):
    work = queue / 'dfm9'
    if stage == 'sample':
        if load(work / 'all-token-comparison.json')['status'] != 'matched':
            raise ValueError('DFM9 fresh tokenizations must match before sampling')
        if hashlib.sha256((work / 'prefix_config.yaml').read_bytes()).hexdigest() != load(
                ROOT / 'config/data/dfm9_hf_rebuild.json')['prefix_config_sha256']:
            raise ValueError('Frozen sampling policy changed')
        return [PYTHON, str(ROOT / 'data_io/sample_tokenized.py'),
                f'tokenized_path={work / "union"}', f'output_path={work / "sampled"}',
                f'prefix_config_path={work / "prefix_config.yaml"}',
                'epochs=10', 'seed=0', 'concat_workers=4']
    if stage == 'compare':
        return None
    if stage not in ('prepare', 'convert', 'verify-rows', 'tokenize', 'assemble', 'verify'):
        raise ValueError(f'Unknown DFM9 stage: {stage}')
    return [PYTHON, str(ROOT / 'scripts/rebuild_dfm9.py'), stage, '--work', str(work)]


def enable_dfm10(queue):
    with (queue / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if load(queue / 'dfm9/verified.json')['status'] != 'matched':
            raise ValueError('DFM9 must be verified before DFM10')
        config = load(ROOT / 'config/data/dfm10_hf_rebuild.json')
        if (config['version'] != 10 or config['epochs'] != 10
                or config['composition']['addition_tasks'] != len(config['tasks'])
                or config['composition']['total_tasks']
                != config['composition']['base_tasks']
                + config['composition']['addition_tasks'] + 2):
            raise ValueError('DFM10 input lock incomplete')
        plan = load(queue / 'plan.json')
        row = next(r for r in plan['rows'] if r['version'] == 10)
        if row['status'] == 'done':
            raise ValueError('Refusing to reset verified DFM10')
        if row.get('recipe') not in (None, 'dfm10-hf-v1'):
            raise ValueError('Unexpected DFM10 recipe')
        (queue / 'dfm10').mkdir(exist_ok=True)
        row.update(recipe='dfm10-hf-v1', recipe_hold=None, status='pending', phase=None,
                   tokenizer_workers=safe_tokenizer_workers(),
                   stages=['prepare', 'tokenize', 'assemble', 'verify', 'sample', 'compare'])
        row.pop('error', None)
        plan['tokenizer_workers'] = safe_tokenizer_workers()
        write_json(queue / 'plan.json', plan)
        print('Enabled DFM10 (dfm10-hf-v1); run the guarded runner to execute it.')


def dfm10_command(queue, stage):
    work = queue / 'dfm10'
    if stage == 'sample':
        if load(work / 'all-token-comparison.json')['status'] != 'matched':
            raise ValueError('DFM10 fresh tokenizations must match before sampling')
        if hashlib.sha256((work / 'prefix_config.yaml').read_bytes()).hexdigest() != load(
                ROOT / 'config/data/dfm10_hf_rebuild.json')['prefix_config_sha256']:
            raise ValueError('Frozen sampling policy changed')
        return [PYTHON, str(ROOT / 'data_io/sample_tokenized.py'),
                f'tokenized_path={work / "union"}', f'output_path={work / "sampled"}',
                f'prefix_config_path={work / "prefix_config.yaml"}',
                'epochs=10', 'seed=0', 'concat_workers=4']
    if stage == 'compare':
        return None
    if stage not in ('prepare', 'tokenize', 'assemble', 'verify'):
        raise ValueError(f'Unknown DFM10 stage: {stage}')
    return [PYTHON, str(ROOT / 'scripts/rebuild_dfm10.py'), stage, '--work', str(work)]


def enable_dfm11(queue):
    with (queue / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        from scripts.dfm_hf_gate import require_dfm10
        require_dfm10(queue)
        for version in (9,):
            if load(queue / f'dfm{version}/verified.json')['status'] != 'matched':
                raise ValueError(f'DFM{version} must be verified before DFM11')
        config = load(ROOT / 'config/data/dfm11_hf_rebuild.json')
        if (config['version'] != 11 or config['epochs'] != 10
                or config['composition']['addition_tasks'] != len(config['tasks'])
                or config['composition']['total_tasks']
                != config['composition']['base_tasks']
                + config['composition']['addition_tasks'] + 2):
            raise ValueError('DFM11 input lock incomplete')
        plan = load(queue / 'plan.json')
        row = next(r for r in plan['rows'] if r['version'] == 11)
        if row['status'] == 'done':
            raise ValueError('Refusing to reset verified DFM11')
        if row.get('recipe') not in (None, 'dfm11-hf-v1'):
            raise ValueError('Unexpected DFM11 recipe')
        (queue / 'dfm11').mkdir(exist_ok=True)
        row.update(recipe='dfm11-hf-v1', recipe_hold=None, status='pending', phase=None,
                   tokenizer_workers=safe_tokenizer_workers(),
                   stages=['acquire', 'prepare', 'convert', 'verify-rows', 'assemble', 'verify',
                           'sample', 'compare'])
        row.pop('error', None)
        plan['tokenizer_workers'] = safe_tokenizer_workers()
        write_json(queue / 'plan.json', plan)
        print('Enabled DFM11 (dfm11-hf-v1); run the guarded runner to execute it.')


def dfm11_command(queue, stage):
    work = queue / 'dfm11'
    if stage == 'sample':
        if load(work / 'all-token-comparison.json')['status'] != 'matched':
            raise ValueError('DFM11 fresh tokenizations must match before sampling')
        if hashlib.sha256((work / 'prefix_config.yaml').read_bytes()).hexdigest() != load(
                ROOT / 'config/data/dfm11_hf_rebuild.json')['prefix_config_sha256']:
            raise ValueError('Frozen sampling policy changed')
        return [PYTHON, str(ROOT / 'data_io/sample_tokenized.py'),
                f'tokenized_path={work / "union"}', f'output_path={work / "sampled"}',
                f'prefix_config_path={work / "prefix_config.yaml"}',
                'epochs=10', 'seed=0', 'concat_workers=4']
    if stage == 'compare':
        return None
    if stage not in ('acquire', 'prepare', 'convert', 'verify-rows', 'assemble', 'verify'):
        raise ValueError(f'Unknown DFM11 stage: {stage}')
    return [PYTHON, str(ROOT / 'scripts/rebuild_dfm11.py'), stage, '--work', str(work)]


def dfm2_command(queue, stage):
    work = queue / 'dfm2'
    package_command = package_stage(queue, stage, 2)
    if package_command is not None:
        return package_command
    if stage == 'generate':
        return [PYTHON, str(ROOT / 'scripts/generate_dfm2_dynaword_tasks.py'),
                '--input-root', str(queue / 'dfm1/converted/danish_dynaword'),
                '--output-root', str(work / 'converted'), '--max-chars', '3000',
                '--seed', '20260530', '--historical-full-reconstruction', '--force']
    if stage == 'tokenize':
        if (work / 'package-input.json').exists():
            return [PYTHON, str(ROOT / 'scripts/tokenize_hrm_hf.py'), str(work / 'converted'),
                    '--tokenizer-path', str(ROOT / 'data_io/trained_tokenizers/bpe/tokenizer.json'),
                    '--workers', str(safe_tokenizer_workers()), '-o', str(work / 'tokenized_extra')]
        verify_dfm2_rows(work)
        generated = load(work / 'converted/manifest.json')
        historical = load(ROOT / 'data/converted_sources_dfm2_dynaword_tasks/manifest.json')
        for key in ('files', 'max_chars', 'seed', 'totals'):
            if generated[key] != historical[key]:
                raise ValueError(f'DFM2 generated manifest mismatch: {key}')
        return [PYTHON, str(ROOT / 'scripts/tokenize_hrm_hf.py'), str(work / 'converted'),
                '--tokenizer-path', str(ROOT / 'data_io/trained_tokenizers/bpe/tokenizer.json'),
                '--workers', str(safe_tokenizer_workers()), '-o', str(work / 'tokenized_extra')]
    if stage == 'assemble':
        return [PYTHON, str(ROOT / 'scripts/build_tokenized_dfm2_tree.py'),
                '--base-tokenized', str(queue / 'dfm1/tokenized'),
                '--extra-tokenized', str(work / 'tokenized_extra'),
                '--output', str(work / 'tokenized'), '--force']
    if stage == 'sample':
        manifest = load(work / 'tokenized/union_manifest.json')
        if (manifest['linked_base_tasks'], manifest['linked_extra_tasks']) != (1377, 450):
            raise ValueError('DFM2 task layout differs from historical union')
        return [PYTHON, str(ROOT / 'data_io/sample_tokenized.py'),
                f'tokenized_path={work / "tokenized"}', f'output_path={work / "sampled"}',
                f'prefix_config_path={work / "prefix_config.yaml"}',
                'epochs=4', 'seed=0', 'concat_workers=1']
    return None


def package_stage(queue, stage, version):
    plan_path = queue / 'plan.json'
    if not plan_path.exists():
        return None
    row = next(r for r in load(plan_path)['rows'] if r['version'] == version)
    # Existing verification jobs predate package publication and retain their
    # regeneration recipe. Newly enabled recipes explicitly select HF packages.
    if row.get('transform_source') != 'hf-package':
        return None
    if stage == 'generate':
        return [PYTHON, str(ROOT / 'scripts/fetch_historical_dfm_package.py'),
                '--work', str(queue / f'dfm{version}'), '--version', str(version)]
    if stage in ('acquire', 'convert'):
        return [PYTHON, '-c', 'print("Raw acquisition/conversion replaced by pinned HF package")']
    return None


def historical_tokenizer_metadata(queue):
    path = queue / 'dfm1/tokenized/tokenizer_info.json'
    info = load(path)
    original = dict(info)
    # Modern Rust adds this descriptive field; DFM1 predates the alternate template.
    if info.get('template_mode') not in (None, 'Hrm'):
        raise ValueError('DFM1 requires the original HRM template')
    info.pop('template_mode', None)
    expected = load(ROOT / 'data/tokenized_mixed/tokenizer_info.json')
    if info != expected:
        raise ValueError('Tokenizer configuration differs from historical DFM1')
    write_json(queue / 'dfm1/tokenizer-runtime-provenance.json', original)
    write_json(path, info)


def command(queue, stage):
    work = queue / 'dfm1'
    if stage == 'filter':
        return [PYTHON, str(ROOT / 'scripts/build_filtered_source_tree.py'),
                '--config', str(work / 'source_filter.yaml'), '--input-root', str(work / 'inputs'),
                '--output-root', str(work / 'filtered')]
    if stage == 'convert':
        return [PYTHON, str(ROOT / 'scripts/convert_filtered_sources.py'),
                '--input-root', str(work / 'filtered'), '--output-root', str(work / 'converted'),
                '--workers', '8', '--copy-ready', '--require-convert-meta']
    if stage == 'tokenize':
        workers = safe_tokenizer_workers()
        if workers < 1:
            raise ValueError('tokenizer_workers must be positive')
        return [PYTHON, str(ROOT / 'scripts/tokenize_hrm_hf.py'), str(work / 'converted'),
                '--tokenizer-path', str(ROOT / 'data_io/trained_tokenizers/bpe/tokenizer.json'),
                '--workers', str(workers), '-o', str(work / 'tokenized')]
    if stage == 'sample':
        return [PYTHON, str(ROOT / 'data_io/sample_tokenized.py'),
                f'tokenized_path={work / "tokenized"}', f'output_path={work / "sampled"}',
                f'prefix_config_path={work / "prefix_config.yaml"}',
                'epochs=4', 'seed=0', 'concat_workers=1']
    return None


def run(queue, through=None):
    with (queue / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = load(queue / 'plan.json')
        for row in plan['rows']:
            if through is not None and row['version'] > through:
                return
            if row['status'] == 'done':
                continue
            version = row['version']
            row['status'] = 'running'
            row['started_at'] = time.time()
            write_json(queue / 'plan.json', plan)
            try:
                if version > 1:
                    parent = queue / f'dfm{version-1}/verified.json'
                    if not parent.exists() or load(parent).get('status') != 'matched':
                        raise ValueError('Predecessor has not passed comparison')
                if version not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11) or row['recipe'] != {
                        1: 'dfm1-hf-v1', 2: 'dfm2-hf-v1', 3: 'dfm3-hf-v1',
                        4: 'dfm4-hf-v1', 5: 'dfm5-hf-v1', 6: 'dfm6-hf-v1',
                        7: 'dfm7-hf-v1', 8: 'dfm8-hf-v1', 9: 'dfm9-hf-v1',
                        10: 'dfm10-hf-v1', 11: 'dfm11-hf-v1'}[version]:
                    raise ValueError(row['recipe_hold'])
                for stage in row['stages']:
                    if stage in row['completed_stages']:
                        continue
                    row['phase'] = stage
                    write_json(queue / 'plan.json', plan)
                    print(f'DFM{version}: {stage}', flush=True)
                    argv = {1: command, 2: dfm2_command, 3: dfm3_command,
                            4: dfm4_command, 5: dfm5_command, 6: dfm6_command,
                            7: dfm7_command, 8: dfm8_command, 9: dfm9_command,
                            10: dfm10_command, 11: dfm11_command}[version](queue, stage)
                    if argv:
                        if stage == 'sample' and version == 1:
                            historical_tokenizer_metadata(queue)
                        row['command'] = argv
                        write_json(queue / 'plan.json', plan)
                        with (queue / f'dfm{version}/{stage}.log').open('a') as log:
                            subprocess.run(argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                           check=True, env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'OMP_NUM_THREADS': '1',
                                                            'MKL_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'})
                    else:
                        if version in (2, 3, 4, 5, 6, 7, 8, 9):
                            if stage == 'prepare' and version not in (7, 8, 9):
                                prepare_dfm2(queue)
                            elif stage == 'compare':
                                compare(queue, version=version)
                        elif version == 1:
                            {'prepare': prepare, 'split_swe': split_swe,
                             'layout': check_layout, 'compare': compare}[stage](queue)
                        elif stage == 'compare':
                            compare(queue, version=version)
                        else:
                            raise ValueError(f'Unexpected inline stage {stage} for DFM{version}')
                    row['completed_stages'].append(stage)
                    write_json(queue / 'plan.json', plan)
                row.update(status='done', finished_at=time.time())
                row.pop('error', None)
            except Exception as exc:
                row.update(status='blocked', error=f'{type(exc).__name__}: {exc}')
                write_json(queue / 'plan.json', plan)
                print(f'DFM{version} blocked: {row["error"]}', flush=True)
                return
            write_json(queue / 'plan.json', plan)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('init', 'enable-dfm2', 'repair-dfm2', 'repair-dfm3', 'enable-dfm3', 'enable-dfm4', 'enable-dfm5', 'enable-dfm6', 'enable-dfm7', 'enable-dfm8', 'enable-dfm9', 'enable-dfm10', 'enable-dfm11',
                                         'run', 'status', 'monitor'))
    parser.add_argument('--queue', type=Path, required=True)
    parser.add_argument('--through', type=int, choices=range(1, 16),
                        help='Run only through this dataset version, inclusive')
    parser.add_argument('--acquisition', type=Path)
    parser.add_argument('--regenerate-transforms', action='store_true',
                        help='Explicit fallback instead of published historical HF packages')
    parser.add_argument('--interval', type=float, default=300)
    parser.add_argument('--wait-pid', type=int,
                        help='Wait for an already-running converter before an incremental retry')
    args = parser.parse_args()
    queue = args.queue.resolve()
    if args.action == 'init':
        if args.acquisition is None:
            parser.error('--acquisition is required for init')
        initialize(queue, args.acquisition)
    elif args.action == 'enable-dfm2':
        enable_dfm2(queue, regenerate=args.regenerate_transforms)
    elif args.action == 'enable-dfm3':
        enable_dfm3(queue, regenerate=args.regenerate_transforms)
    elif args.action == 'repair-dfm2':
        repair_dfm2(queue)
    elif args.action == 'repair-dfm3':
        repair_dfm2(queue, version=3)
    elif args.action == 'enable-dfm4':
        enable_dfm4(queue, regenerate=args.regenerate_transforms)
    elif args.action == 'enable-dfm5':
        enable_dfm5(queue)
    elif args.action == 'enable-dfm6':
        enable_dfm6(queue)
    elif args.action == 'enable-dfm7':
        enable_dfm7(queue)
    elif args.action == 'enable-dfm8':
        enable_dfm8(queue)
    elif args.action == 'enable-dfm9':
        enable_dfm9(queue)
    elif args.action == 'enable-dfm10':
        enable_dfm10(queue)
    elif args.action == 'enable-dfm11':
        enable_dfm11(queue)
    elif args.action == 'run':
        if args.wait_pid:
            proc = Path(f'/proc/{args.wait_pid}')
            while proc.exists():
                try:
                    command_line = (proc / 'cmdline').read_bytes()
                except FileNotFoundError:
                    break
                if b'convert_filtered_sources.py' not in command_line:
                    break
                print(f'Waiting for existing conversion PID {args.wait_pid}', flush=True)
                time.sleep(30)
        run(queue, through=args.through)
    else:
        if args.interval <= 0:
            parser.error('--interval must be positive')
        while True:
            rows = load(queue / 'plan.json')['rows']
            print(time.strftime('%Y-%m-%d %H:%M:%S %z'), flush=True)
            for row in rows:
                print(f"DFM{row['version']}: {row['status']} {row['phase']} {row.get('error', '')}", flush=True)
            if args.action == 'status' or any(r['status'] == 'blocked' for r in rows) or all(
                    r['status'] == 'done' for r in rows):
                break
            time.sleep(args.interval)


if __name__ == '__main__':
    main()
