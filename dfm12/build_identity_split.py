"""Fresh remaining-step 95/2.5/2.5 replay; never modify the running mixture."""
import argparse
from pathlib import Path
import json
import tempfile

import numpy as np

from . import build_identity_adaptation as shared
from . import build_identity_corrective as corrective
from . import identity_correction
from .identity_extension import NativeRenderer
from .io import file_hash, load, rows, write_json

END = 2897261
GBS = 262144


def prepare_synthetic_evidence(review, root, tokenized, metadata, output):
    """Reuse frozen independent source evidence without claiming a new review."""
    review, root, tokenized, metadata, output = [Path(p).resolve() for p in
        (review, root, tokenized, metadata, output)]
    evidence = load(review)
    if (evidence.get('schema') != 'dfm12-identity-v4-source-evaluator-readiness-v1'
            or evidence.get('status') != 'ready'
            or evidence.get('source_review_ready') is not True
            or evidence.get('blocking_semantic_findings') != []
            or evidence.get('manifest_sha256') != file_hash(root / 'manifest.json')):
        raise ValueError('Independent frozen source review does not clear this manifest')
    if output.exists():
        raise FileExistsError(output)
    pins = {str(p): file_hash(p) for p in [review, root / 'manifest.json',
        *sorted(p.resolve() for p in tokenized.rglob('*') if p.is_file())]}
    receipt = dict(schema='dfm12-v4-synthetic-admission-v1', verdict='PASS',
        training_only=True, heldout_and_development_excluded=True,
        source_root=str(root), tokenized_root=str(tokenized), pins=pins,
        independent_review=str(review), independent_review_reused=True,
        new_handoff_signoff=False,
        scope='CPU source reconstruction and token-span verification; not a new independent handoff sign-off')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        candidate = Path(temporary) / 'receipt.json'
        write_json(candidate, receipt)
        sources = validate_synthetic(candidate, metadata)
        receipt['verified_targets'] = {s['name']: len(s['arrays']['inst_len']) for s in sources}
        write_json(candidate, receipt)
        candidate.rename(output)
    return receipt


def budgets(start):
    if not 2887261 < start < END:
        raise ValueError('Invalid remaining-step start')
    total = (END - start) * GBS
    small = round(total * .025)
    return {'DFM11': total - 2 * small, 'identity-corrective': small,
            'identity-synthetic': small}


def validate_synthetic(receipt_path, metadata):
    review = load(receipt_path)
    if (review.get('schema') != 'dfm12-v4-synthetic-admission-v1'
            or review.get('verdict') != 'PASS'
            or review.get('training_only') is not True
            or review.get('heldout_and_development_excluded') is not True):
        raise ValueError('Require independent synthetic PASS admission receipt')
    root, tokenized = Path(review['source_root']).resolve(), Path(review['tokenized_root']).resolve()
    expected_pins = {str(root / 'manifest.json')} | {
        str(p.resolve()) for p in tokenized.rglob('*') if p.is_file()}
    if not expected_pins.issubset(review['pins']):
        raise ValueError('Admission must pin manifest and all tokenized files')
    for path, sha in review['pins'].items():
        if file_hash(path) != sha:
            raise ValueError('Synthetic admission pin drift: ' + path)
    identity_correction.verify(root)
    manifest = load(root / 'manifest.json')
    if manifest['schema'] != identity_correction.SCHEMA:
        raise ValueError('Require latest corrected v4, not an earlier corpus')
    completion = load(tokenized / 'completion.json')
    if completion['files'] != 2 or completion['skipped_rows_this_run'] != 0:
        raise ValueError('Synthetic tokenization skipped or included extra files')
    expected_dirs = {f'dfm12-identity-xl-full-bp-{lang}__train-00000.jsonl.gz' for lang in ('da', 'en')}
    if {p.name for p in tokenized.iterdir() if p.is_dir()} != expected_dirs:
        raise ValueError('Unexpected synthetic input directory')
    info = load(metadata)['tokenizer_info']
    shared.check_tokenizer(info, load(tokenized / 'tokenizer_info.json'))
    renderer = NativeRenderer(metadata)
    from scripts.tokenize_chat_template import examples_from_messages, tokenize_example
    sources = []
    for lang in ('da', 'en'):
        path = tokenized / f'dfm12-identity-xl-full-bp-{lang}__train-00000.jsonl.gz'
        arrays = shared.indices(path)
        tokens = np.load(path / 'tokens.npy', mmap_mode='r')
        source_path = (root / manifest['languages'][lang]['input']).resolve()
        if not source_path.is_relative_to(root / 'inputs'):
            raise ValueError('Synthetic source is not training input')
        cursor = 0
        for row in rows(source_path):
            for example in examples_from_messages(row['messages'], []):
                encoded = tokenize_example(renderer.tokenizer, renderer.template, example, False)
                if encoded is None or sum(map(len, encoded)) > 4096:
                    raise ValueError('Invalid untruncated synthetic render')
                if cursor >= len(arrays['inst_len']):
                    raise ValueError('Missing synthetic target')
                for part, expected in zip(('inst', 'resp'), encoded):
                    offset, length = int(arrays[part + '_start'][cursor]), int(arrays[part + '_len'][cursor])
                    if tokens[offset:offset+length].tolist() != expected:
                        raise ValueError('Synthetic tokenized target does not match sealed training source')
                cursor += 1
        if cursor != len(arrays['inst_len']):
            raise ValueError('Extra synthetic targets')
        sources.append(dict(name='identity-synthetic-' + lang, path=str(path), arrays=arrays,
                            tokens=tokens, supply=int(arrays['inst_len'].sum() + arrays['resp_len'].sum())))
    return sources


def build(ready, synthetic_admission, output, start=2887400, data_epoch=16,
          base=Path('data/sampled_dfm11'), seed=20261002):
    ready, synthetic_admission = Path(ready).resolve(), Path(synthetic_admission).resolve()
    output, base = Path(output).resolve(), Path(base).resolve()
    if output.exists():
        raise FileExistsError(output)
    budget = budgets(start)
    steps = END - start
    packed, _ = corrective.validate_final(ready)
    metadata = load(base / 'metadata.json')
    shared.check_tokenizer(metadata['tokenizer_info'], load(packed / 'train/metadata.json')['tokenizer_info'])
    synthetic = validate_synthetic(synthetic_admission, base / 'metadata.json')
    rng = np.random.default_rng(seed)
    sources = []
    for name, path, allocation, repeat in (
            ('DFM11', base, budget['DFM11'], False),
            ('identity-corrective', packed / 'train', budget['identity-corrective'], True)):
        arrays = shared.indices(path / 'epoch_0')
        selected, total = shared.select_rows(arrays, allocation, rng, repeat,
            load(path / 'metadata.json')['total_length'] / len(arrays['inst_len']))
        sources.append(dict(name=name, path=str(path), arrays=arrays, selected=selected,
                            rendered_tokens=total, tokens=np.load(path / 'tokens.npy', mmap_mode='r')))
    supply = sum(s['supply'] for s in synthetic)
    da_budget = round(budget['identity-synthetic'] * synthetic[0]['supply'] / supply)
    for source, allocation in zip(synthetic, (da_budget, budget['identity-synthetic'] - da_budget)):
        source['selected'], source['rendered_tokens'] = shared.select_rows(source['arrays'], allocation, rng, True)
        sources.append(source)
    output.mkdir(parents=True)
    for source in sources:
        lengths = source['arrays']['inst_len'][source['selected']] + source['arrays']['resp_len'][source['selected']]
        # DFM11 stores the final next-token label too: 4097 stored, 4096 model positions.
        if np.any(lengths > metadata['max_seq_len']) or np.any(lengths < 2):
            raise ValueError('Out-of-context row; no clipping')
        np.save(output / (source['name'] + '-source-rows.npy'), source['selected'])
    arrays, labels, stored = shared.compact_copy(sources, output, rng)
    packing = shared.packing_report(arrays, labels, steps, GBS, 8, 8)
    epoch = output / 'epoch_0'
    epoch.mkdir()
    for key, values in arrays.items():
        np.save(epoch / (key + '.npy'), values)
    np.save(output / 'source-labels.npy', labels)
    (output / f'epoch_{data_epoch}').symlink_to('epoch_0', target_is_directory=True)
    total = sum(s['rendered_tokens'] for s in sources)
    metadata['total_length'] = total
    write_json(output / 'metadata.json', metadata)
    supervision = {}
    for scope, end in (('prepared', len(labels)), ('at_stop', packing['row_end_at_stop'])):
        supervision[scope] = {s['name']: dict(
            response_tokens=int(arrays['resp_len'][:end][labels[:end] == i].sum()),
            nonpadding_tokens=int((arrays['inst_len'][:end] + arrays['resp_len'][:end] - 1)[labels[:end] == i].sum()),
            rows=int((labels[:end] == i).sum())) for i, s in enumerate(sources)}
    source_reports = []
    for source in sources:
        repetitions = np.bincount(source['selected'], minlength=len(source['arrays']['inst_len']))
        source_reports.append(dict(name=source['name'], path=source['path'],
            sampled_rows=len(source['selected']), unique_rows=len(source['unique']),
            rendered_tokens=source['rendered_tokens'], repeat_min=int(repetitions.min()),
            repeat_max=int(repetitions.max())))
    receipt = dict(schema='dfm12-split-identity-mixture-v1', steps=steps, global_batch=GBS,
        gas=8, world_size=8, seed=seed, budgets=budget, rendered_tokens=total, stored_tokens=stored,
        sources=source_reports, packing=packing, supervision=supervision,
        recipe={'DFM11': .95, 'identity-corrective': .025, 'identity-synthetic': .025},
        **shared.continuation_contract(start, steps, f'ephemeral_step_{start}', data_epoch),
        source_receipts={str(p): file_hash(p) for p in (ready, synthetic_admission)},
        builder_sha256=file_hash(Path(__file__)), helper_sha256=file_hash(Path(shared.__file__)),
        heldout_and_validation_excluded=True, target_only=True,
        synthetic_assistant_history='Every sealed assistant target retained, reconstructed from training inputs only',
        corrective_assistant_history='Final-answer-only labels, prior assistant history masked')
    receipt['output_files'] = {str(p.relative_to(output)): file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()}
    for path, sha in load(synthetic_admission)['pins'].items():
        if file_hash(path) != sha:
            raise ValueError('Synthetic source changed during build')
    write_json(output / 'build-receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--synthetic-admission', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--start', type=int, default=2887400)
    parser.add_argument('--data-epoch', type=int, default=16)
    parser.add_argument('--seed', type=int, default=20261002)
    print(json.dumps(build(**vars(parser.parse_args())), indent=2))
