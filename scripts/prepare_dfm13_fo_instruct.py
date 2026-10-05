"""Prepare pinned Setur Faroese instruction pairs without rewriting their text."""
import json
import os
from pathlib import Path
import subprocess
import sys

from dfm12.io import file_hash, load, lock, write_json

NAME = 'setur_fo_instruct'
REPO = 'Setur/fo-instruct'
REVISION = '55a97b043e1a3f2778492c72bf124f4091341402'
ROOT = Path('data/dfm13/setur-fo-instruct-20261005-v1')
RAW = Path('data/downloads/datasets/setur_fo_instruct') / REVISION


def convert(row, ordinal):
    for key in ('instruction', 'output'):
        if not isinstance(row.get(key), str) or not row[key].strip():
            raise ValueError('Missing instruction/answer')
    return dict(id=f'{NAME}:{ordinal}', messages=[
        dict(role='user', content=row['instruction']),
        dict(role='assistant', content=row['output'])], target_message_index=1,
        chat_template_kwargs=dict(enable_thinking=False), metadata=dict(
            source=REPO, revision=REVISION, split='train', language='fo',
            contributor_id=row.get('contributor_id'), source_row_index=ordinal,
            license='cc-by-4.0', quality_basis='upstream instruction pairs; not model audited'))


def run():
    from huggingface_hub import snapshot_download
    from scripts import assemble_dfm13_additions as api
    from dfm12.fo_instruct_assembly import verify
    with lock(ROOT / '.lock'):
        snapshot_download(REPO, repo_type='dataset', revision=REVISION, local_dir=RAW)
        raw = RAW / 'data/train.jsonl'
        rows = [convert(json.loads(line), i) for i, line in enumerate(raw.read_text().splitlines())]
        if len(rows) != 571:
            raise ValueError('Pinned source count changed')
        source = ROOT / 'input/train.jsonl'
        source.parent.mkdir(parents=True, exist_ok=True)
        payload = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows)
        if source.exists() and source.read_text() != payload:
            raise ValueError('Converted source changed')
        if not source.exists():
            source.write_text(payload)
        tokens = ROOT / 'tokens'
        if not (tokens / 'completion.json').exists():
            if tokens.exists():
                raise ValueError('Incomplete tokens: inspect before restarting')
            command = [sys.executable, '-m', 'scripts.tokenize_chat_template', str(source.parent),
                       '-o', str(tokens), '--tokenizer-path', 'data/dfm11_tokenizer/tokenizer.json',
                       '--chat-template', 'data/dfm11_tokenizer/chat_template.jinja', '--workers', '1']
            with (ROOT / 'tokenization.log').open('w') as log:
                subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT,
                               env=dict(os.environ, CUDA_VISIBLE_DEVICES='', TOKENIZERS_PARALLELISM='false'))
        entry = dict(name=NAME, repo_id=REPO, revision=REVISION, license='cc-by-4.0',
            split='train', language='fo', repeat=10, rows=len(rows),
            publication_contract='setur-fo-instruct-native-v1', status='source_native_tokenized',
            output=str(source.resolve()), output_sha256=file_hash(source),
            raw_source=str(raw.resolve()), raw_source_sha256=file_hash(raw),
            source_card=str((RAW / 'README.md').resolve()), source_card_sha256=file_hash(RAW / 'README.md'),
            tokenized_path=str(tokens.resolve()), tokenization_performed=True,
            token_files={str(p.resolve()): file_hash(p) for p in tokens.rglob('*') if p.is_file()},
            target_policy='single_assistant_native_gemma', hard_truncation=False)
        contract = api.token_contract(load('data/sampled_dfm12/metadata.json')['tokenizer_info'], {})
        result = verify(entry, contract, {}, api)
        entry.update(tokens=result['tokens'], tokenized_tokens=result['tokens'], tokenized_rows=result['rows'])
        registry = Path('config/dfm13_sources.json')
        with lock(registry.with_suffix('.lock')):
            config = load(registry)
            old = [e for e in config['additions'] if e['name'] == NAME]
            if old and old != [entry]:
                raise ValueError('Conflicting existing Setur registration')
            if not old:
                config['additions'].append(entry)
                write_json(registry, config)
        write_json(ROOT / 'completion.json', dict(entry=entry, verification=result,
            weighted_tokens=result['tokens'] * 10, weighted_rows=len(rows) * 10))
        print(json.dumps(dict(rows=len(rows), tokens=result['tokens'], repeat=10,
                              weighted_tokens=result['tokens'] * 10)), flush=True)


if __name__ == '__main__':
    run()
