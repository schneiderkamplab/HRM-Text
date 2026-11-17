import json
from pathlib import Path
import subprocess
import sys

import jinja2
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from tokenizers import Tokenizer, models, pre_tokenizers

from scripts import tokenize_historical_chat as driver
from scripts import rebuild_dfm6 as recipe
from scripts import queue_dfm_hf_rebuild as queue


@pytest.mark.parametrize('extension', ['jsonl', 'parquet'])
def test_bounded_writer_matches_historical_and_repairs_partial(tmp_path, extension):
    adapter = tmp_path / 'adapter.py'
    adapter.write_bytes(subprocess.check_output(['git', 'show',
        '038e9a5:scripts/tokenize_chat_template.py'], cwd=recipe.ROOT))
    tokenizer = Tokenizer(models.WordLevel({'[UNK]': 0, 'user': 1, 'assistant': 2,
        'Hello': 3, 'World': 4, 'Answer': 5}, unk_token='[UNK]'))
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    tokpath = tmp_path / 'tokenizer.json'
    tokenizer.save(str(tokpath))
    template = tmp_path / 'template.jinja'
    template.write_text('{% for m in messages %}{{ m.role }} {{ m.content }} '
                        '{% endfor %}{% if add_generation_prompt %}assistant {% endif %}')
    source = tmp_path / ('source.' + extension)
    rows = [dict(condition='direct', instruction='Hello', response='World Answer'),
            dict(condition='cot', instruction='World', response='Hello Answer')]
    if extension == 'parquet':
        pq.write_table(pa.Table.from_pylist(rows), source)
    else:
        source.write_text(''.join(json.dumps(x) + '\n' for x in rows))
    module = driver.adapter(adapter)
    expected = tmp_path / 'expected'
    module.process_file(module.FoundFile(source, source.name), expected, tokenizer,
                        jinja2.Environment().from_string(template.read_text()), True, False)
    driver.initialize(str(adapter), str(tokpath), str(template))
    out = tmp_path / 'actual' / source.name
    job = (str(source), str(out), 'test-fingerprint')
    assert driver.process(job)[1] == 2
    for key in driver.DTYPES:
        np.testing.assert_array_equal(np.load(out / f'{key}.npy'),
            np.load(expected / source.name / f'{key}.npy'))
    assert driver.process(job)[1] == 'cached'
    (out / 'tokens.npy').write_bytes(b'incomplete')
    assert driver.process(job)[1] == 2
    (out / 'hf_receipt.json').unlink()
    assert driver.process(job)[1] == 2


def test_sampling_requires_source_equivalence(tmp_path):
    work = tmp_path / 'dfm6'
    work.mkdir()
    (work / 'all-token-comparison.json').write_text('{"status":"mismatch"}')
    with pytest.raises(ValueError, match='must match'):
        queue.dfm6_command(tmp_path, 'sample')


def test_tokenization_uses_bounded_driver(tmp_path):
    cmd = queue.dfm6_command(tmp_path, 'tokenize')
    assert any(x.endswith('rebuild_dfm6.py') for x in cmd)
    assert 'tokenize' in cmd
    cmd = recipe.tokenizer_command(tmp_path, tmp_path / 'sources', tmp_path / 'tokens', 32)
    assert any(x.endswith('tokenize_historical_chat.py') for x in cmd)
    assert '--workers' in cmd
    assert not any('/target/release' in x for x in cmd)


def test_corrupt_tool_call_cleaning_is_exact(tmp_path):
    source, target = tmp_path / 'raw', tmp_path / 'clean'
    source.write_bytes(b'{}\n' * 8443 + b'bad\x00line\n')
    recipe.clean_tool_calling(source, target)
    assert target.read_bytes() == b'{}\n' * 8443
    target.unlink()
    source.write_bytes(b'{}\n')
    with pytest.raises(ValueError, match='corruption changed'):
        recipe.clean_tool_calling(source, target)
    assert not target.exists()


def test_frozen_inventory_has_no_production_payload_paths():
    cfg = recipe.load(recipe.CONFIG)
    assert len(cfg['tasks']) == len({x['task'] for x in cfg['tasks']}) == 10523
    for item in cfg['tasks']:
        assert 'rebuild_hf_dfm/' in item['path']
        assert '/tokenized' not in item['path']
        if item['mode'] == 'hf':
            assert len(item['revision']) == 40


def test_conversation_shards_join_matches_monolithic(tmp_path):
    adapter = tmp_path / 'adapter.py'
    adapter.write_bytes(subprocess.check_output(['git', 'show',
        '038e9a5:scripts/tokenize_chat_template.py'], cwd=recipe.ROOT))
    tok = Tokenizer(models.WordLevel({'[UNK]': 0, 'user': 1, 'assistant': 2,
        'Hello': 3, 'World': 4, 'Answer': 5}, unk_token='[UNK]'))
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    tokpath = tmp_path / 'tokenizer.json'
    tok.save(str(tokpath))
    template = tmp_path / 'template.jinja'
    template.write_text('{% for m in messages %}{{ m.role }} {{ m.content }} '
                        '{% endfor %}{% if add_generation_prompt %}assistant {% endif %}')
    source = tmp_path / 'source.jsonl'
    conversation = dict(messages=[dict(role='user', content='Hello'),
        dict(role='assistant', content='World Answer'), dict(role='user', content='World'),
        dict(role='assistant', content='Hello Answer')])
    # Multi-line objects must not split an assistant target from its history.
    source.write_text('\n'.join(json.dumps(conversation, indent=2) for _ in range(8)) + '\n')
    split, tokens = tmp_path / 'split', tmp_path / 'shard_tokens'
    subprocess.run([sys.executable, str(recipe.ROOT / 'scripts/split_jsonl_objects.py'),
        str(source), '--output-dir', str(split), '--shards', '3'], check=True)
    driver.initialize(str(adapter), str(tokpath), str(template))
    full = tmp_path / 'monolithic' / 'full'
    driver.process((str(source), str(full), 'test'))
    for path in sorted(split.glob('*.jsonl')):
        driver.process((str(path), str(tokens / path.name), 'test'))
    subprocess.run([sys.executable, str(recipe.ROOT / 'scripts/join_tokenized_shards.py'),
        '--tokenized-root', str(tokens), '--shard-prefix', 'shard-', '--output-name', 'joined',
        '--source-file', str(source)], check=True)
    for field in driver.DTYPES:
        np.testing.assert_array_equal(np.load(full / f'{field}.npy'),
                                      np.load(tokens / 'joined' / f'{field}.npy'))
