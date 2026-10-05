import json
from pathlib import Path

import numpy as np
import pytest

from dfm12.io import file_hash
from scripts.tokenize_dfm13_nonwave import command, stage, statistics


def test_no_truncation_flags():
    args = command(Path('input'), Path('output'), 16)
    assert '--max-seq-len' not in args
    assert '--skip-bad-json' not in args
    assert '--enable-thinking' not in args
    assert args[-1] == '16'


@pytest.mark.parametrize('workers', [0, 17, True, -1])
def test_worker_limit(workers):
    with pytest.raises(ValueError):
        command(Path('a'), Path('b'), workers)


def test_stage_preserves_native_fields_and_nonfinal_target(tmp_path):
    row = dict(id='x', messages=[dict(role='user', content='Q'),
        dict(role='assistant', tool_calls=[dict(id='call', function=dict(name='f', arguments={}))]),
        dict(role='tool', tool_call_id='call', content='result')], tools=[dict(type='function')],
        target_message_index=1, metadata=dict(source='original'))
    source = tmp_path/'source.jsonl'; source.write_text(json.dumps(row)+'\n')
    entry = dict(output=str(source), output_sha256=file_hash(source), rows=1)
    stage(entry, tmp_path/'input')
    assert (tmp_path/'input/part-000000.jsonl').read_bytes() == source.read_bytes()
    with pytest.raises(FileExistsError):
        stage(entry, tmp_path/'input')


def test_long_rows_are_counted_not_removed(tmp_path):
    part = tmp_path/'part-000000.jsonl'; part.mkdir()
    np.save(part/'inst_len.npy', np.array([5, 4096]))
    np.save(part/'resp_len.npy', np.array([2, 10]))
    np.save(part/'tokens.npy', np.zeros(4113, dtype=np.uint32))
    assert statistics(tmp_path) == dict(rows=2, tokens=4113,
        sequences_over_4096=1, max_sequence_tokens=4106)
