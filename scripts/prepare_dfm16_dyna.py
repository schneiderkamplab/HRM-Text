"""Pinned Dyna additions: native chat conversion and bounded audit candidates.

This does not resample or mutate a published DFM16 dataset. Document derivatives
remain audit-only; use audit_pipeline for their review before admission.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
import json
from pathlib import Path

from huggingface_hub import hf_hub_download
from huggingface_hub.errors import GatedRepoError
from dfm12.io import atomic, digest, file_hash, load, lock, rows, write_json
from dfm12.prepare import Renderer
from dfm12.records import validate_messages
from dfm12.transform import window as character_window
from dfm14.transforms import TASKS, transform, window

INVENTORY = Path('docs/reports/dyna-source-scan-20261027/inventory.json')
ROOT = Path('data/dfm16/dyna-v1')
DOWNLOADS = Path('data/dfm16/dyna-downloads')
GROUNDING = {
    'danish-foundation-models/norwegian-dynaword': [
        'data/nva-cc-by/data.parquet', 'data/nva-cc-by-sa/data.parquet',
        'data/nva-cc0/data.parquet'],
    'danish-foundation-models/swedish-dynaword': [
        'data/rd-sou/rd-sou.parquet', 'data/rd-ds/rd-ds.parquet'],
}


def fetch(pin, filename):
    path = Path(hf_hub_download(pin['repo'], filename, repo_type='dataset',
        revision=pin['revision'], local_dir=DOWNLOADS/pin['repo'].replace('/', '__')))
    expected = pin['files'][filename].get('sha256')
    if expected and file_hash(path) != expected:
        raise ValueError(f'Payload hash mismatch: {filename}')
    return path


def instruction(row, revision, ordinal):
    messages = [dict(role='user', content=row['prompt']),
                dict(role='assistant', content=row['target'])]
    validate_messages(messages)
    return dict(id=row['id'], messages=messages, language='no',
        provenance=dict(repo_id='oliverkinch/dynaword-no-bt', revision=revision,
            split='train', row=ordinal, source_meta=row['meta'], sources=row['sources']))


def laya_access(pin):
    result = dict(repo=pin['repo'], revision=pin['revision'],
        selection='ctx1024 train only; doc_id overlap check with test required')
    try:
        files = [fetch(pin, f'data/ctx1024/{split}.parquet') for split in ('test', 'train')]
    except GatedRepoError:
        return result | dict(status='blocked_gated_403')
    return result | dict(status='downloaded_schema_inspection_and_conversion_pending',
                         files=[str(path) for path in files])


def prepare_instructions(pin, root, meta, workers):
    from scripts.prepare_dfm16_decisions import tokenize_source
    out = root/'dynaword-no-bt'
    path = fetch(pin, 'data/train-00000-of-00001.parquet')
    identity = dict(revision=pin['revision'], input_sha256=file_hash(path), version=1)
    receipt_path = out/'conversion.json'
    if receipt_path.exists():
        receipt = load(receipt_path)
        if receipt['identity'] != identity:
            raise ValueError('Changed instruction input; use a new preparation directory')
        for name, checksum in receipt['output_hashes'].items():
            if file_hash(out/name) != checksum:
                raise ValueError('Changed completed conversion')
    else:
        counts, seen = Counter(), set()
        with ExitStack() as stack:
            outputs = [stack.enter_context(atomic(out/'input/direct'/f'{i:03}.jsonl'))
                       for i in range(64)]
            rejected = stack.enter_context(atomic(out/'rejected.jsonl'))
            for ordinal, row in enumerate(rows(path)):
                counts['input'] += 1
                try:
                    value = instruction(row, pin['revision'], ordinal)
                    key = digest(value['messages'])
                    if key in seen:
                        raise ValueError('duplicate_conversation')
                    seen.add(key)
                except (ValueError, KeyError, TypeError) as exc:
                    counts['rejected'] += 1
                    rejected.write(json.dumps(dict(row=ordinal, reason=str(exc)))+'\n')
                    continue
                outputs[counts['direct'] % 64].write(json.dumps(value, ensure_ascii=False)+'\n')
                counts['direct'] += 1
        write_json(receipt_path, dict(identity=identity, counts=dict(counts),
            repo_id=pin['repo'], output_hashes={str(p.relative_to(out)): file_hash(p)
                for p in sorted((out/'input').rglob('*.jsonl'))}))
    tokenize_source(out, meta, workers)
    result = load(out/'prepared.json') | dict(repo_id=pin['repo'], revision=pin['revision'],
        inherited_content_overlap='not established; corpus-level exact check pending')
    write_json(out/'prepared.json', result)
    return result


def prepare_documents(pins, root, meta, cap):
    """Hash-ranked full-file document sampling, never the first N documents."""
    from lingua import Language, LanguageDetectorBuilder
    detector = LanguageDetectorBuilder.from_languages(Language.BOKMAL,
        Language.NYNORSK, Language.SWEDISH, Language.ENGLISH, Language.DANISH).build()
    langs = {Language.BOKMAL: 'nb', Language.NYNORSK: 'nn', Language.SWEDISH: 'sv'}
    renderer = Renderer(meta, max_length=4097)
    out = root/'grounding'
    identity = dict(version=2, cap_per_file=cap,
        revisions={repo: pins[repo]['revision'] for repo in GROUNDING},
        tokenizer_sha256=file_hash(meta['tokenizer_path']),
        template_sha256=file_hash(meta['chat_template_path']))
    if (out/'receipt.json').exists():
        receipt = load(out/'receipt.json')
        if receipt['identity'] != identity:
            raise ValueError('Changed grounding inputs/settings')
        for chunk in receipt['chunks']:
            if file_hash(out/chunk['input']) != chunk['sha256']:
                raise ValueError('Changed audit chunk')
        publish_audit_manifest(out, receipt['chunks'])
        return receipt
    counts, chunks, seen, pending = Counter(), [], set(), []

    def flush():
        if not pending:
            return
        name = f'chunks/{len(chunks):05}.jsonl'
        with atomic(out/name) as handle:
            for record in pending:
                handle.write(json.dumps(record, ensure_ascii=False)+'\n')
        chunks.append(dict(job_id=f'dyna-{len(chunks):05}', input=name,
            task='mixed-transformations', rows=len(pending), sha256=file_hash(out/name)))
        pending.clear()

    with atomic(out/'seeds.jsonl') as seeds, atomic(out/'holds.jsonl') as holds:
        for repo, files in GROUNDING.items():
            for filename in files:
                path = fetch(pins[repo], filename)
                # First pass retains only small IDs/ordinals, not whole documents.
                selected = sorted((digest([repo, row['id']]), ordinal)
                    for ordinal, row in enumerate(rows(path)))[:cap]
                selected = {ordinal for _, ordinal in selected}
                for ordinal, row in enumerate(rows(path)):
                    if ordinal not in selected:
                        continue
                    counts['selected_documents'] += 1
                    provenance = dict(repo=repo, revision=pins[repo]['revision'], file=filename,
                        row=ordinal, source_id=row['id'], source=row.get('source'),
                        license_partition=filename.split('/')[1])
                    try:
                        seed = digest(provenance)
                        # Some PDF exports are whole-book single paragraphs. Bound
                        # complete sentences before tokenizing, not arbitrary bytes.
                        candidate = character_window(row['text'], seed, max_chars=8000)
                        text = window(candidate, renderer.tokenizer, seed)
                        scores = detector.compute_language_confidence_values(text)
                        best = scores[0]
                        lang = langs.get(best.language)
                        allowed = {'nb', 'nn'} if 'norwegian' in repo else {'sv'}
                        if lang not in allowed or best.value < 0.8:
                            raise ValueError('uncertain_or_out_of_scope_language')
                        key = digest(text)
                        if key in seen:
                            raise ValueError('duplicate_window')
                        seen.add(key)
                    except ValueError as exc:
                        counts['held:'+str(exc)] += 1
                        holds.write(json.dumps(dict(provenance=provenance, reason=str(exc)))+'\n')
                        continue
                    seeds.write(json.dumps(dict(text=text, language=lang, provenance=provenance,
                        language_confidence=best.value), ensure_ascii=False)+'\n')
                    counts['seed:'+lang] += 1
                    for task in TASKS:
                        try:
                            record = transform(text, lang, task, provenance)
                            record['rendered_tokens'] = renderer.count(record['messages'])
                        except ValueError as exc:
                            counts['held:'+str(exc)] += 1
                            continue
                        record['audit_id'] = digest([identity, record['id']])
                        pending.append(record)
                        counts[task] += 1
                        if len(pending) >= 256:
                            flush()
                print(json.dumps(dict(file=filename, counts=dict(counts))), flush=True)
    flush()
    referenced = {chunk['input'] for chunk in chunks}
    for old in (out/'chunks').glob('*.jsonl'):
        if str(old.relative_to(out)) not in referenced:
            old.unlink()
    receipt = dict(identity=identity, chunks=chunks, counts=dict(counts),
        training_ready=False, inherited_overlap_check_pending=True)
    write_json(out/'receipt.json', receipt)
    publish_audit_manifest(out, chunks)
    return receipt


def publish_audit_manifest(out, chunks):
    write_json(out/'manifest.json', dict(status='ready_for_gpu_audit', chunks=chunks))
    write_json(out/'readiness.json', dict(status='cpu_complete_ready_for_gpu',
        manifest_sha256=file_hash(out/'manifest.json')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--workers', type=int, default=64)
    parser.add_argument('--documents-per-file', type=int, default=2000)
    parser.add_argument('--instructions-only', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.workers <= 64 or args.documents_per_file < 1:
        parser.error('workers must be 1..64; document cap must be positive')
    pins = {r['repo']: r for r in load(INVENTORY)}
    meta = load('data/dfm15/native-reasoning-v2/sampled_dfm15/metadata.json')['tokenizer_info']
    with lock(args.root/'.lock'):
        direct = prepare_instructions(pins['oliverkinch/dynaword-no-bt'], args.root, meta, args.workers)
        summary = dict(direct=direct, laya=laya_access(pins['syvai/danish-dynaword-laya']), sampled=False)
        write_json(args.root/'summary.json', summary)
        if not args.instructions_only:
            summary['grounding'] = prepare_documents(pins, args.root, meta, args.documents_per_file)
            write_json(args.root/'summary.json', summary)


if __name__ == '__main__':
    main()
