import asyncio
from copy import deepcopy
import json

import pytest

from dfm12 import source7_repair as repair
from dfm12.io import write_json


def candidate():
    return dict(id='original', language='en', family='grounded-instruct', tools=[],
        messages=[dict(role='user', content='Summarize.\nOriginal source error unchanged.'),
                  dict(role='assistant', content='Unsupported motive.')],
        provenance=dict(source=dict(text='Original source error unchanged.')))


def test_selection_retains_supported_originals():
    rows = [dict(id=k + 'x'*52, terminal=True, status='valid')
            for k in set(repair.NOTES) | repair.RETAIN]
    selected = repair.selected(dict(outcomes=rows))
    assert len(selected) == 5
    assert all(r['id'][:12] not in repair.RETAIN for r in selected)
    with pytest.raises(ValueError):
        repair.selected(dict(outcomes=rows + [rows[0]]))


def test_request_assistant_only_and_field_bound():
    payload, schema = repair.repair_request(candidate(), 'Remove unsupported motive.')
    assert schema['required'] == ['1']
    assert schema['properties']['1']['maxLength'] == 2400
    assert payload['model'] == repair.executor.MODEL
    assert payload['max_tokens'] == 4096
    assert 'silently' in payload['messages'][0]['content']


def test_repair_preserves_source_user_and_original(monkeypatch):
    monkeypatch.setattr(repair.executor, 'student_validate', lambda renderer, row: None)
    original = candidate()
    before = deepcopy(original)
    fixed = repair.apply(original, {'1': 'Source-bound answer.'}, None)
    assert original == before
    assert fixed['messages'][0] == original['messages'][0]
    assert fixed['provenance'] == original['provenance']
    assert fixed['id'] != original['id']
    assert fixed['admission_authorized'] is False
    with pytest.raises(Exception):
        repair.apply(original, {'0': 'Corrected source', '1': 'Answer'}, None)
    with pytest.raises(ValueError, match='overflow'):
        repair.apply(original, {'1': 'a'*2401}, None)


def test_fresh_review_does_not_leak_repair_note():
    row = candidate()
    row['repair_lineage'] = {'repair_note': 'SECRET'}
    data = json.loads(repair.compact.request(row)['messages'][1]['content'])
    assert 'SECRET' not in json.dumps(data)
    assert data['source']['text'] == row['provenance']['source']['text']


def test_existing_once_never_replays_failed_or_inflight(tmp_path):
    class Budget:
        def measure(self, payload):
            return {}
    calls = []
    async def query(*args):
        calls.append(1)
        raise TimeoutError('uncertain transport')
    async def exercise():
        args = (tmp_path, 'case', 'repair', {}, {}, 'endpoint', None, None, Budget(), query)
        first = await repair.executor.once(*args)
        second = await repair.executor.once(*args)
        assert first == second
        assert len(calls) == 1
        first['status'] = 'inflight'
        write_json(tmp_path / 'stages/case-repair.json', first)
        assert (await repair.executor.once(*args))['status'] == 'inflight'
        assert len(calls) == 1
    asyncio.run(exercise())


def test_unconfirmed_module_cannot_start(monkeypatch, tmp_path):
    monkeypatch.setattr(repair, 'verify', lambda root: {'compact_sha256': 'frozen'})
    with pytest.raises(ValueError, match='freeze hash'):
        asyncio.run(repair.run(tmp_path, 'other'))
