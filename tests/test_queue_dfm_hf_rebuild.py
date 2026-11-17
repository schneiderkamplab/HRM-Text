import json

import pytest

from scripts import queue_dfm_hf_rebuild as queue


def test_serial_plan_and_failure_gate(tmp_path, monkeypatch):
    root = tmp_path / 'queue'
    queue.initialize(root, tmp_path / 'acquisition')
    plan = queue.load(root / 'plan.json')
    assert len(plan['rows']) == 15
    assert [r['depends_on'] for r in plan['rows']] == [None, *range(1, 15)]

    def fail(_):
        raise ValueError('missing HF payload')

    monkeypatch.setattr(queue, 'prepare', fail)
    queue.run(root)
    result = queue.load(root / 'plan.json')
    assert result['rows'][0]['status'] == 'blocked'
    assert all(r['status'] == 'pending' for r in result['rows'][1:])


def test_source_guard_rejects_external_symlink(tmp_path):
    allowed = tmp_path / 'hf'
    allowed.mkdir()
    forbidden = tmp_path / 'old_tokens.npy'
    forbidden.write_bytes(b'old local data')
    link = allowed / 'tokens.npy'
    link.symlink_to(forbidden)
    with pytest.raises(ValueError, match='Forbidden local rebuild input'):
        queue.require_allowed(link, [allowed])


def test_next_version_requires_real_receipt(tmp_path):
    root = tmp_path / 'queue'
    queue.initialize(root, tmp_path / 'acquisition')
    plan = queue.load(root / 'plan.json')
    plan['rows'][0]['status'] = 'done'
    queue.write_json(root / 'plan.json', plan)
    queue.run(root)
    plan = queue.load(root / 'plan.json')
    assert plan['rows'][1]['status'] == 'blocked'
    assert 'Predecessor' in plan['rows'][1]['error']


def test_tokenization_uses_configured_safe_workers(tmp_path):
    root = tmp_path / 'queue'
    queue.initialize(root, tmp_path / 'acquisition')
    argv = queue.command(root, 'tokenize')
    workers = queue.safe_tokenizer_workers()
    assert 1 <= workers <= 64
    assert argv[argv.index('--workers')+1] == str(workers)
