import json

import pytest

from dfm12.io import file_hash
from scripts.tokenize_wave_releases import eligible, prepare


def test_only_uploaded_waves():
    entry = dict(name='dfm13_wave4_test', status='accepted_uploaded', uploaded=True, hf_revision='abc')
    assert eligible(entry)
    assert not eligible({**entry, 'uploaded': False})
    assert not eligible({**entry, 'name': 'unrelated'})


def test_chunk_and_hash_validation(tmp_path):
    source = tmp_path / 'source.jsonl'
    row = dict(messages=[{'role': 'user', 'content': 'Q'}, {'role': 'assistant', 'content': 'A'}],
               target_message_index=1)
    source.write_text((json.dumps(row) + '\n') * 5001)
    entry = dict(output=str(source), output_sha256=file_hash(source), rows=5001)
    stage = tmp_path / 'stage'
    prepare(entry, stage)
    assert len(list(stage.glob('*.jsonl'))) == 2
    assert len((stage / 'part-000001.jsonl').read_text().splitlines()) == 1
    with pytest.raises(ValueError, match='hash mismatch'):
        prepare({**entry, 'output_sha256': 'bad'}, stage)
    assert (stage / 'part-000001.jsonl').exists()


def test_missing_target_is_rejected(tmp_path):
    source = tmp_path / 'source.jsonl'
    source.write_text(json.dumps({'messages': [{'role': 'assistant', 'content': 'A'}]}) + '\n')
    with pytest.raises(ValueError, match='supervision'):
        prepare(dict(output=str(source), output_sha256=file_hash(source), rows=1), tmp_path / 'stage')
