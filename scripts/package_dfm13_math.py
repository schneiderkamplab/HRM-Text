"""Prepare the existing worked-MATH bytes for publication; never mutate registry."""
import argparse
import json
from pathlib import Path
import shutil

from dfm12.io import file_hash, load, lock, write_json
from dfm12 import math_assembly
from scripts import assemble_dfm13_additions as assembly

DESTINATION = 'schneiderkamplab/dfm13-hendrycks-math-worked'


def validate(root):
    root = Path(root)
    manifest = load(root / 'manifest.json')
    if manifest['repeat'] != 5 or manifest['physical_repetition'] != 1:
        raise ValueError('Repeat must remain metadata only')
    if manifest['files']['data/train.jsonl'] != manifest['source_sha256']:
        raise ValueError('Export differs from verified source')
    for relative, sha in manifest['files'].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or file_hash(path) != sha:
            raise ValueError('Package hash/path mismatch')
    seen, problems = set(), set()
    for line in (root / 'data/train.jsonl').open():
        row = json.loads(line)
        problem = ' '.join(row['messages'][0]['content'].split())
        if row['id'] in seen or problem in problems:
            raise ValueError('Duplicate physical row/problem')
        if (row['metadata']['split'] != 'train' or row['metadata']['source'] != math_assembly.REPO
                or row['metadata']['revision'] != math_assembly.REVISION
                or row['metadata']['license'] != 'mit' or row['target_message_index'] != 1
                or [m['role'] for m in row['messages']] != ['user', 'assistant']):
            raise ValueError('Source/target contract changed')
        seen.add(row['id']); problems.add(problem)
    if len(seen) != manifest['rows'] or len(seen) != math_assembly.ROWS:
        raise ValueError('MATH count mismatch')
    return dict(valid=True, rows=len(seen), repeat=5, physical_repetition=1,
                manifest_sha256=file_hash(root / 'manifest.json'))


def prepare(root, registry=Path('config/dfm13_sources.json')):
    root = Path(root)
    with lock(str(root) + '.lock'):
        if root.exists():
            raise ValueError('Fresh package required; existing package preserved')
        entry, = [e for e in load(registry)['additions'] if e['name'] == math_assembly.NAME]
        pins = {}
        contract = assembly.token_contract(load('data/sampled_dfm12/metadata.json')['tokenizer_info'], pins)
        verified = math_assembly.verify(entry, contract, pins)
        original = load(entry['manifest'])
        (root / 'data').mkdir(parents=True)
        (root / 'provenance').mkdir()
        shutil.copyfile(entry['output'], root / 'data/train.jsonl')
        shutil.copyfile(original['license_evidence']['path'], root / 'SOURCE_README.md')
        shutil.copyfile(entry['manifest'], root / 'provenance/original-conversion-manifest.json')
        shutil.copyfile(Path(entry['manifest']).parent / 'screening.jsonl', root / 'provenance/screening.jsonl')
        write_json(root / 'provenance/source-files.json', [dict(
            config=f['config'], split=f['split'], rows=f['rows'], sha256=f['sha256'],
            upstream_path=f['config']+'/'+Path(f['path']).name) for f in original['source_files']])
        (root / 'LICENSE_PROVENANCE.md').write_text(
            '# License and attribution\n\nThe pinned EleutherAI/hendrycks_math dataset card declares MIT.\n'
            'SOURCE_README.md is copied byte-for-byte as license and author/citation evidence.\n'
            'No new copyright ownership or additional license clearance is asserted.\n'
            f'Source revision: {math_assembly.REVISION}.\n'
            'Authors: Dan Hendrycks, Collin Burns, Saurav Kadavath, Akul Arora, Steven Basart, '
            'Eric Tang, Dawn Song, Jacob Steinhardt. NeurIPS 2021.\n')
        (root / 'README.md').write_text(f'''---
license: mit
language:
- en
task_categories:
- text-generation
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train.jsonl
---
# DFM13 MATH Worked Solutions

7,496 unique training conversations from [EleutherAI/hendrycks_math](https://huggingface.co/datasets/EleutherAI/hendrycks_math/tree/{math_assembly.REVISION}).
Original worked solutions, not model-audited or certified gold. Row metadata
preserves config, split, source row/file hashes, level/type and answer handling.
User message is the problem; only the final assistant is supervised. Entire
original solution is retained; canonical final answer boxes were appended by
the documented conversion. No further transformation is performed for export.

## Deduplication and evaluation protection
7,500 train rows were screened against all5,000 test problems using exact and
collapsed-whitespace matching: one test overlap, one train duplicate and two
invalid solutions excluded. Test is screening-only, never a training split.
No exhaustive inherited/fuzzy/translated overlap claim. Shared problems with
the inherited RLVR MATH direct-answer source are intentional.

## Repeat and native tokenization
Repeat5 is sampling metadata, NOT five physical copies. This file contains
7,496 rows once. Historical conversion manifest repeat1 is preserved as evidence
and superseded by the October2 user repeat5 policy. Stored native Gemma4 tokens:
2,431,145; no Mistral regex fix, hard truncation or skipped targets. The existing
token arrays and registry are unchanged. No new sampling or training was run.

## Provenance
See SOURCE_README.md for the pinned MIT declaration and citation, and
LICENSE_PROVENANCE.md. Original conversion and four exclusions are preserved
under provenance/. Source inventory hashes include test files for screening
evidence only. Local paths in the original manifest are historical provenance,
not required consumer dependencies. Proposed HF destination: {DESTINATION}.
''')
        files = {str(p.relative_to(root)): file_hash(p) for p in root.rglob('*') if p.is_file()}
        manifest = dict(schema='dfm13-math-hf-package-v1', name=entry['name'],
            hf_repo_id=DESTINATION, source_repo_id=math_assembly.REPO,
            source_revision=math_assembly.REVISION, license='mit', rows=math_assembly.ROWS,
            repeat=5, physical_repetition=1, uploaded=False, tokenized_tokens=verified['tokens'],
            target_policy=entry['target_policy'], source_sha256=entry['output_sha256'],
            historical_manifest_sha256=entry['manifest_sha256'],
            overlap_policy=original['overlap_policy'], inherited_complete=False,
            files=files)
        write_json(root / 'manifest.json', manifest)
        receipt = validate(root)
        receipt.update(upload_ready=True, uploaded=False, registry_changed=False,
                       hf_repo_id=DESTINATION, verified_input_pins=pins)
        write_json(str(root) + '.ready.json', receipt)
        return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'validate'])
    parser.add_argument('--root', type=Path, default=Path('exports_dfm13/dfm13-hendrycks-math-worked'))
    args = parser.parse_args()
    result = prepare(args.root) if args.command == 'prepare' else validate(args.root)
    print(json.dumps({k: v for k, v in result.items() if k != 'verified_input_pins'}, indent=2))
