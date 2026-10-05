import json
import sqlite3
import pytest
from dfm12 import wave4_gemma31_transition as m


def test_nonterminal_queue_blocks(tmp_path):
    path = tmp_path / 'jobs.sqlite'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE jobs(status TEXT)')
        db.execute("INSERT INTO jobs VALUES ('running')")
    with pytest.raises(ValueError, match='Nonterminal'):
        m.terminal_database(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE jobs SET status='failed'")
    assert m.terminal_database(path) == {'failed': 1}


def test_empty_inventory_cannot_authorize():
    with pytest.raises(ValueError):
        m.readiness({})
    with pytest.raises(ValueError, match='inventory'):
        m.readiness({'cpu_preparation_complete': True, 'producers_frozen': True})


def test_live_client_blocks(tmp_path, monkeypatch):
    receipt = tmp_path / 'done.json'
    receipt.write_text('{}')
    monkeypatch.setattr(m, 'alive', lambda p: True)
    with pytest.raises(ValueError, match='still alive'):
        m.readiness({'cpu_preparation_complete': True, 'producers_frozen': True,
            'completion_receipts': {str(receipt): m.file_hash(receipt)},
            'clients_and_producers': [{'pid': 123}], 'databases': ['unused']})


def test_incomplete_weights_block(tmp_path):
    (tmp_path / 'config.json').write_text(json.dumps({'model_type': 'gemma4'}))
    (tmp_path / 'model.safetensors.index.json').write_text(json.dumps({'weight_map': {'a': 'missing'}}))
    with pytest.raises(ValueError, match='Incomplete'):
        m.model_files(tmp_path)


def test_receipt_drift_blocks(tmp_path):
    receipt = tmp_path / 'done.json'
    receipt.write_text('{}')
    with pytest.raises(ValueError, match='receipt changed'):
        m.readiness({'cpu_preparation_complete': True, 'producers_frozen': True,
            'completion_receipts': {str(receipt): 'wrong'},
            'clients_and_producers': [{'pid': 123}], 'databases': ['unused']})
