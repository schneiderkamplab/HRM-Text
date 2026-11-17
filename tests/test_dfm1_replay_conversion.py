from argparse import Namespace
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from scripts import convert_filtered_sources as converter
from scripts import queue_dfm_hf_rebuild as queue


def args():
    return Namespace(force=False, copy_ready=True, dynaword_chars=12000,
                     batch_size=4096, require_convert_meta=True)


def test_missing_text_reports_source(tmp_path):
    src = tmp_path / 'metadata.parquet'
    pq.write_table(pa.table({'id': [1]}), src)
    with pytest.raises(ValueError, match='metadata.parquet'):
        converter.convert_dynaword(src, tmp_path / 'out.parquet', 12000, 4096)


def test_partial_without_receipt_is_not_complete(tmp_path):
    source = tmp_path / 'input/a.parquet'
    source.parent.mkdir()
    pq.write_table(pa.table({'text': ['data']}), source)
    output = tmp_path / 'output'
    output.mkdir()
    (output / source.name).write_bytes(b'partial')
    assert not converter.is_current_output(source, source.parent, output, args())


def test_ready_jsonl_keeps_extension_and_is_incremental(tmp_path):
    source = tmp_path / 'input/a.jsonl'
    source.parent.mkdir()
    source.write_text('{"condition":"direct","instruction":"Q","response":"A"}\n')
    output = tmp_path / 'output'
    assert converter.convert_file(source, source.parent, output, args())[0] == 'ready'
    assert (output / 'a.jsonl').exists()
    assert converter.is_current_output(source, source.parent, output, args())


def test_layout_includes_ready_jsonl(tmp_path, monkeypatch):
    reference = tmp_path / 'data/tokenized_mixed/a__b.jsonl'
    reference.mkdir(parents=True)
    converted = tmp_path / 'queue/dfm1/converted/a'
    converted.mkdir(parents=True)
    (converted / 'b.jsonl').write_text('{}\n')
    monkeypatch.setattr(queue, 'ROOT', tmp_path)
    queue.check_layout(tmp_path / 'queue')


def test_historical_swe_boundaries():
    boundaries = [round(i * 468 / 10) for i in range(11)]
    counts = [(b-a)*4096 for a, b in zip(boundaries, boundaries[1:])]
    counts[-1] -= 468*4096 - 1915306
    assert counts == [192512, 192512, 188416, 192512, 192512,
                      192512, 192512, 188416, 192512, 190890]


def test_tokenizer_metadata_only_drops_known_description(tmp_path, monkeypatch):
    reference = tmp_path / 'data/tokenized_mixed'
    reference.mkdir(parents=True)
    queue.write_json(reference / 'tokenizer_info.json', {'vocab_size': 65536})
    work = tmp_path / 'queue/dfm1/tokenized'
    work.mkdir(parents=True)
    queue.write_json(work / 'tokenizer_info.json', {'vocab_size': 65536, 'template_mode': 'Hrm'})
    monkeypatch.setattr(queue, 'ROOT', tmp_path)
    queue.historical_tokenizer_metadata(tmp_path / 'queue')
    assert queue.load(work / 'tokenizer_info.json') == {'vocab_size': 65536}
    queue.write_json(work / 'tokenizer_info.json', {'vocab_size': 65536, 'template_mode': 'Gemma4Chat'})
    with pytest.raises(ValueError, match='original HRM template'):
        queue.historical_tokenizer_metadata(tmp_path / 'queue')


def test_publication_requires_all_comparisons(tmp_path):
    from scripts.publish_dfm1_derivatives import require_verified
    (tmp_path / 'dfm1').mkdir()
    queue.write_json(tmp_path / 'dfm1/verified.json', {'version': 1, 'status': 'matched', 'verified_files': 1})
    with pytest.raises(ValueError, match='parity'):
        require_verified(tmp_path)
