import copy
import json

import numpy as np
import pytest

from dfm12.io import file_hash
from scripts.pack_identity_preference_sft import pack, validate_row


def row():
    return dict(id='one', split='train', input_ids=[1, 2, 3, 4, 5],
                labels=[-100, -100, -100, 4, 5], attention_mask=[1]*5,
                prompt_token_count=3)


def test_final_answer_shift():
    value = row()
    boundary = validate_row(value, 'train', 8, 5)
    assert [-100]*(boundary-1) + value['input_ids'][boundary:] == value['labels'][1:]


@pytest.mark.parametrize('change', [
    {'labels': [-100, 2, -100, 4, 5]},
    {'labels': [-100, -100, -100, -100, 5]},
    {'prompt_token_count': 0}, {'prompt_token_count': 5},
    {'input_ids': [1, 2, 3, 4, 9]}, {'split': 'validation'},
    {'attention_mask': [1, 1, 1, 1, 0]},
])
def test_refuse_unsafe_rows(change):
    value = copy.deepcopy(row())
    value.update(change)
    with pytest.raises(ValueError):
        validate_row(value, 'train', 8, 5)


def test_no_silent_truncation():
    with pytest.raises(ValueError, match='truncation'):
        validate_row(row(), 'train', 8, 4)


def fixture(tmp_path):
    source = tmp_path / 'source'
    (source / 'chosen-sft-tokenized').mkdir(parents=True)
    tokenizer, template = tmp_path / 'tokenizer', tmp_path / 'template'
    tokenizer.write_text('tokenizer')
    template.write_text('template')
    info = dict(tokenizer_path=str(tokenizer), chat_template_path=str(template),
                vocab_size=8, enable_thinking=False, template_mode='jinja_chat_template')
    metadata = tmp_path / 'metadata.json'
    metadata.write_text(json.dumps(dict(tokenizer_info=info, max_seq_len=6,
                                        total_length=999, vocab_size=None)))
    manifest = dict(source_mode='EMA_ONLY', review_complete=True, unreviewed_turns=0,
                    prior_assistant_loss=False, runtime_asset_binding=dict(vocab_size=8,
                    tokenizer_info=info, assets=dict(tokenizer=dict(sha256=file_hash(tokenizer)),
                    template=dict(sha256=file_hash(template)))), files={}, split_counts={})
    for split in ('train', 'validation'):
        value = row() | dict(id=split, split=split)
        rel = f'chosen-sft-tokenized/{split}.jsonl'
        (source / rel).write_text(json.dumps(value)+'\n')
        manifest['files'][rel] = file_hash(source / rel)
        manifest['split_counts'][split] = {'sft': 1}
    (source / 'manifest.json').write_text(json.dumps(manifest))
    return source, metadata


def test_packed_spans_and_split_isolation(tmp_path):
    source, metadata = fixture(tmp_path)
    output = tmp_path / 'packed'
    report = pack(source, output, metadata)
    for split in ('train', 'validation'):
        path = output / split
        values = np.load(path / 'tokens.npy')
        fields = {k: int(np.load(path/'epoch_0'/f'{k}.npy')[0])
                  for k in ('inst_start', 'inst_len', 'resp_start', 'resp_len')}
        assert values[fields['inst_start']:fields['inst_start']+fields['inst_len']].tolist() == [1,2,3]
        assert values[fields['resp_start']:fields['resp_start']+fields['resp_len']].tolist() == [4,5]
        assert report['splits'][split]['target_tokens'] == 2
        assert json.loads((path/'metadata.json').read_text())['total_length'] == 5
    with pytest.raises(FileExistsError):
        pack(source, output, metadata)


def test_changed_source_fails_before_output(tmp_path):
    source, metadata = fixture(tmp_path)
    (source/'chosen-sft-tokenized/train.jsonl').write_text('{}\n')
    output = tmp_path / 'packed'
    with pytest.raises(ValueError, match='Unpinned'):
        pack(source, output, metadata)
    assert not output.exists()
