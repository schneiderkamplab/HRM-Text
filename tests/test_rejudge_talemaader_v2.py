import json
import zipfile

import pytest

from scripts.rejudge_talemaader_v2 import PREFIX, aggregate, cache_key, load_cache, load_samples


def test_saved_answers_and_references_are_preserved(tmp_path):
    p = tmp_path/'saved.eval'
    record = dict(id='one', metadata={'talemaade_udtryk': 'example'},
                  target=['reference'], output={'completion': 'answer'})
    with zipfile.ZipFile(p, 'w') as z:
        z.writestr('samples/one.json', json.dumps(record))
    point = dict(id='cp', inputs=[str(p)], expected_n=1, epoch=10, train_step=2877261)
    items = load_samples(point)
    assert items[0]['answer'] == 'answer'
    assert items[0]['criterion'] == 'reference'
    row = aggregate(point, items, {cache_key(items[0]): {'value': 0.5}})
    assert row[f'{PREFIX}/accuracy'] == 0.5
    assert row['dfm_eval/epoch'] == 10
    with pytest.raises(ValueError, match='expected'):
        load_samples(dict(point, expected_n=2))


def test_invalid_judge_result_is_not_a_cached_zero(tmp_path):
    p = tmp_path/'ledger.jsonl'
    p.write_text(json.dumps({'key': 'bad', 'error': 'invalid'}) + '\n' +
                 json.dumps({'key': 'good', 'value': 0}) + '\n')
    assert load_cache(p) == {'good': {'key': 'good', 'value': 0}}
