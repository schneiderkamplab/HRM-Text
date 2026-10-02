import pytest

from scripts.dfm13_repochat_full_retry import eligible
from scripts.dfm13_repochat_full_retry import b, prepare
import sqlite3
import json


@pytest.mark.parametrize('error', ['ValueError: incomplete_final:stop', 'TimeoutError: ',
                                  'ServerDisconnectedError: Server disconnected'])
def test_bounded_technical_selection(error):
    assert eligible({'status': 'technical_failure', 'error': error})


@pytest.mark.parametrize('status,error', [
    ('reviewed', 'TimeoutError: '),
    ('reviewed', 'ValueError: incomplete_final:stop'),
    ('source_skip', 'TimeoutError: '),
    ('technical_failure', 'ValueError: audit_non_stop:length'),
    ('technical_failure', 'ValueError: tool_round_budget'),
    ('technical_failure', 'ValueError: teacher_context_exceeded_no_truncation'),
    ('technical_failure', 'ValueError: invalid_native_tool_completion'),
])
def test_never_replay_quality_or_contract_failures(status, error):
    assert not eligible({'status': status, 'error': error})


def test_separate_retry_reuses_history_and_excludes_success(tmp_path):
    parent = tmp_path / 'parent'
    root = tmp_path / 'retry'
    parent.mkdir()
    b.save(parent / 'manifest.json', {'pins': {}, 'tasks': [{'id': 'bad'}, {'id': 'good'}]})
    b.save(parent / 'progress.json', {'done': True})
    b.save(parent / 'completion.json', {'progress_sha256': b.file_sha(parent / 'progress.json')})
    with sqlite3.connect(parent / 'jobs.sqlite') as db:
        db.execute('CREATE TABLE jobs(id,status,outcome)')
        db.executemany('INSERT INTO jobs VALUES(?,?,?)', [
            ('bad', 'terminal', json.dumps({'status': 'technical_failure', 'error': 'ValueError: incomplete_final:stop'})),
            ('good', 'terminal', json.dumps({'status': 'reviewed', 'quality_pass': True}))])
    out = parent / 'trajectories' / 'bad'
    b.save(out / 'generate-00.json', {'response': {'choices': [{'message': {'tool_calls': [1]}}]}})
    b.save(out / 'generate-01.json', {'response': {'choices': [{'message': {'content': None}}]}})
    before = b.file_sha(parent / 'manifest.json')
    prepare(parent, root)
    assert [t['id'] for t in b.load(root / 'manifest.json')['tasks']] == ['bad']
    assert (root / 'trajectories/bad/generate-00.json').exists()
    assert not (root / 'trajectories/bad/generate-01.json').exists()
    assert not (root / 'trajectories/good').exists()
    b.save(root / 'trajectories/bad/generate-01.json', {'new': True})
    prepare(parent, root)
    assert b.load(root / 'trajectories/bad/generate-01.json') == {'new': True}
    assert b.file_sha(parent / 'manifest.json') == before
