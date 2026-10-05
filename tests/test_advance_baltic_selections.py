from types import SimpleNamespace

from dfm12.io import load, write_json
from scripts import advance_baltic_selections as worker


def test_revisit_only_incomplete_pairs(tmp_path, monkeypatch):
    write_json(tmp_path / 'translations/config.json',
               {'requested_pairs': [['en', 'lt'], ['en', 'lv']]})
    ready = tmp_path / 'translation-release/en-lt/receipt.json'
    write_json(ready, {'ready': True, 'sha256': 'immutable'})
    before = ready.read_bytes()
    calls = []
    def select(root, pair):
        calls.append(pair)
        write_json(root / f'translation-release/{pair}/receipt.json', {'ready': True})
    monkeypatch.setattr(worker, 'select', select)
    assert worker.advance(tmp_path) == {'en-lt': 'ready', 'en-lv': 'ready'}
    assert calls == ['en-lv']
    assert ready.read_bytes() == before
    worker.advance(tmp_path)
    assert calls == ['en-lv']


def test_wait_is_based_on_live_process(monkeypatch):
    processes = [SimpleNamespace(info={'cmdline': ['python', '-m',
                  'scripts.select_baltic_translations']})]
    monkeypatch.setattr(worker.psutil, 'process_iter', lambda fields: processes)
    assert worker.initial_selector_running()
    processes.clear()
    assert not worker.initial_selector_running()
