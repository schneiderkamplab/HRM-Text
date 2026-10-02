"""Extract compact source metadata on the remote host, without token payloads."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


PREFIXES = ('dfm11-folketingets-dokumenter-error-correction__',
    'giannor_tv2r_instruction__giannor_gec_dala_tv2r_it__',
    'common-pile-denoising__', 'danish-dynaword-denoising__',
    'folketingets-dokumenter-denoising__', 'posttrain_coedit__',
    'dfm8-synthetic-danish-summarization-rewrite-controls__')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''): h.update(b)
    return h.hexdigest()


def records(path):
    if path.suffix == '.parquet':
        import pyarrow.parquet as pq
        for batch in pq.ParquetFile(path).iter_batches(batch_size=2048):
            yield from batch.to_pylist()
        return
    with (gzip.open(path, 'rt') if path.suffix == '.gz' else path.open()) as f:
        for line in f: yield json.loads(line)


def resolve(root, name):
    relative = name.replace('__', '/')
    bases = ('exports_dfm11', 'export-upload', 'export-upload-dfm8-synthetic',
             'data/dfm8_special_sources', 'data/dfm10_folketing_transform_sources_audited',
             'data/converted_sources', 'data/converted_sources_posttrain')
    found = [root / b / relative for b in bases if (root / b / relative).is_file()]
    if len(found) != 1:
        raise ValueError(f'{name}: expected one source, found {found}')
    return found[0]


def compact(row, ordinal):
    messages = row.get('messages', [])
    result = {k: v for k, v in row.items() if k != 'messages'}
    result['ordinal'] = ordinal
    result['messages_sha256'] = hashlib.sha256(json.dumps(messages, ensure_ascii=False,
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    result['assistant_messages'] = sum(m.get('role') == 'assistant' for m in messages)
    result['nonempty_assistant_messages'] = sum(m.get('role') == 'assistant' and
        bool(str(m.get('content') or '').strip() or m.get('tool_calls')) for m in messages)
    result['user_prefix'] = next((m.get('content', '')[:512] for m in messages
        if m.get('role') == 'user'), '')
    # Preserve native affected-token fields, never synthesize edits from a diff.
    if 'corruption_type' in row:
        result['declared_edit_pair'] = [row.get('affected_token_1'), row.get('affected_token_2')]
    if len(messages) == 2:
        result['prompt_prefix'] = messages[0].get('content', '')[:160]
        result['target_equals_input_sentence'] = (messages[0].get('content', '').partition('\n\n')[2]
            == messages[1].get('content'))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path('/work/dfm/HRM-Text'))
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--only-prefix', action='append')
    p.add_argument('--inventory-existing',action='store_true',help='Validate completed compact extracts and rebuild their manifest without re-extraction')
    a = p.parse_args(); a.output.mkdir(parents=True, exist_ok=True)
    manifest = {'schema_version': 1, 'remote_root': str(a.root), 'sources': [], 'missing': []}
    for tokenized in sorted((a.root / 'data/tokenized_dfm11').iterdir()):
        if not tokenized.name.startswith(tuple(a.only_prefix or PREFIXES)): continue
        try: source = resolve(a.root, tokenized.name)
        except ValueError as e:
            manifest['missing'].append(str(e)); continue
        out = a.output / (tokenized.name + '.metadata.jsonl.gz')
        n = 0
        try:
            if a.inventory_existing:
                for i,row in enumerate(records(out)):
                    if row['ordinal']!=i:raise ValueError('Non-contiguous compact ordinals')
                    n+=1
                if not n:raise ValueError('Empty existing extract requires explicit separate verification')
            else:
                with gzip.open(out, 'wt') as f:
                    for i, row in enumerate(records(source)):
                        f.write(json.dumps(compact(row, i), ensure_ascii=False) + '\n'); n += 1
        except Exception as e:
            manifest['missing'].append(f'{tokenized.name}: {type(e).__name__}: {e}')
            if not a.inventory_existing:out.unlink(missing_ok=True)
            continue
        manifest['sources'].append({'component': tokenized.name, 'source': str(source),
            'source_sha256': digest(source), 'rows': n, 'metadata': out.name,
            'metadata_sha256': digest(out)})
        print(tokenized.name, n, flush=True)
        (a.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (a.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__': main()
