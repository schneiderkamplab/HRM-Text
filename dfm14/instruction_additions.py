"""Licensed Japanese, Arabic and Russian instruction candidates."""
import json
from pathlib import Path


def sources():
    entries = [
        ('llm-jp/magpie-sft-v1.0', 'ja', ['magpie-sft-v1.0.jsonl'], 'apache-2.0', {}),
        ('llm-jp/llm-jp-instructions', 'ja', ['v1.0/train-*.parquet'], 'cc-by-4.0',
         {'field_mapping': {'text': 'instruction'}}),
        ('FreedomIntelligence/Evol-Instruct-Arabic-GPT4', 'ar', ['data/train-*.parquet'], 'apache-2.0', {}),
        ('Vikhrmodels/Grounded-RAG-Chat-RU', 'ru', ['data/train-*.parquet'], 'apache-2.0',
         {'adapter': 'vikhr_grounded_chat', 'max_row_chars': 500000,
          'attribution_note': 'Preserve Wikipedia document titles and supplied links; underlying evidence retains source terms.'}),
    ]
    return [dict(repo=repo, component=repo.replace('/', '--'), kind='instruction',
                 languages=[lang], patterns=patterns, license=license,
                 max_training_tokens=4096, **options)
            for repo, lang, patterns, license, options in entries]


def grounded_messages(row):
    turns = row['conversation']
    if not turns or turns[0]['role'] != 'documents' or (len(turns)-1) % 3:
        raise ValueError('unexpected_grounded_chat_structure')
    documents = json.loads(turns[0]['content'])
    if not isinstance(documents, list) or not documents:
        raise ValueError('missing_grounding_documents')
    ids = [d['doc_id'] for d in documents]
    if any(type(i) is not int for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('invalid_grounding_ids')
    for d in documents:
        if not isinstance(d.get('content'), str) or not d['content'].strip():
            raise ValueError('empty_grounding_document')
    messages = []
    instruction = ('Ответьте на вопрос по предоставленным документам. '
                   'Сначала укажите идентификаторы использованных документов, затем дайте ответ.')
    for offset in range(1, len(turns), 3):
        question, selection, answer = turns[offset:offset+3]
        if [m['role'] for m in (question, selection, answer)] != ['user', 'assistant', 'assistant']:
            raise ValueError('unexpected_grounded_chat_roles')
        selected = json.loads(selection['content'])
        if not isinstance(selected, list) or any(type(i) is not int or i not in ids for i in selected):
            raise ValueError('invalid_selected_document')
        prompt = question['content']
        if offset == 1:
            prompt = instruction + '\n\nДокументы:\n' + turns[0]['content'] + '\n\nВопрос:\n' + prompt
        messages.extend([dict(role='user', content=prompt),
                         dict(role='assistant', content='Документы: ' + json.dumps(selected) + '\n\n' + answer['content'])])
    return messages


if __name__ == '__main__':
    from dfm12.io import write_json
    from dfm14.prepare import run
    root = Path('data/dfm14/ja-ar-ru-additions-v1')
    manifest = root / 'sources.json'
    write_json(manifest, sources())
    run(root=root, workers=8, download_workers=4, max_files=100, source_gib=8,
        rows_per_file=1000000, download_root=Path('data/dfm14/downloads'),
        curated_supplements=False, source_manifest=manifest)
