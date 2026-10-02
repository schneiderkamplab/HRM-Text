import json

import pytest

from dfm12.european_screen import connect, index_reference, reasons, screen_component, queue_component
from dfm12.io import file_hash, write_json
from dfm12.jobs import Queue


def chat(text, answer='Answer'):
    return dict(messages=[dict(role='user', content=text), dict(role='assistant', content=answer)],
                id=text, language='en', task='instruction', rendered_tokens=8, provenance={})


def jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r) + '\n' for r in records))


def test_reference_index_resumes_and_detects_changed_pin(tmp_path):
    path = tmp_path / 'reference.jsonl'
    jsonl(path, [chat('hello')])
    entry = dict(path=str(path), sha256=file_hash(path), scope='inherited')
    db = connect(tmp_path / 'db.sqlite')
    index_reference(db, entry)
    index_reference(db, entry)
    assert db.execute('SELECT count(*) FROM files').fetchone()[0] == 1
    assert reasons(db, chat('hello'), 'new') == ['inherited_chat']
    with pytest.raises(ValueError, match='version changed'):
        index_reference(db, dict(entry, sha256='other'))
    db.close()


def test_heldout_text_and_reverse_direction(tmp_path):
    path = tmp_path / 'reference.jsonl'
    prompt = 'A long held out prompt. ' * 20
    jsonl(path, [chat(prompt)])
    db = connect(tmp_path / 'db.sqlite')
    index_reference(db, dict(path=str(path), sha256=file_hash(path), scope='heldout'))
    assert 'heldout_text' in reasons(db, chat(prompt, 'Different answer'), 'new')
    row = chat('Different prompt')
    row['reverse_messages'] = chat(prompt)['messages']
    assert 'heldout_chat' in reasons(db, row, 'new')
    db.close()


def test_screen_and_queue_are_idempotent(tmp_path):
    source = tmp_path / 'candidates/new'
    path = source / 'candidates.jsonl'
    jsonl(path, [chat('a'), chat('a'), chat('b')])
    write_json(source / 'receipt.json', dict(sha256=file_hash(path)))
    write_json(tmp_path / 'screened/reference-inputs.json', dict(files=[]))
    db = connect(tmp_path / 'screened/overlap.sqlite')
    result = screen_component(tmp_path, 'new', db)
    assert result['counts']['candidates'] == 2
    assert result['counts']['duplicate_chat'] == 1
    assert screen_component(tmp_path, 'new', db) == result
    queue_component(tmp_path, 'new', 'model')
    queue_component(tmp_path, 'new', 'model')
    q = Queue(tmp_path / 'screened/jobs.sqlite')
    assert q.status() == [dict(stage='audit', status='pending', count=2)]
    q.close()
    db.close()


def test_orphaned_component_ownership_recovered(tmp_path):
    from dfm12.records import chat_fingerprint
    db = connect(tmp_path / 'screened/overlap.sqlite')
    row = chat('a')
    with db:
        db.execute('INSERT INTO retained VALUES (?,?)', (chat_fingerprint(row['messages']), 'new'))
    path = tmp_path / 'candidates/new/candidates.jsonl'
    jsonl(path, [row])
    write_json(path.parent / 'receipt.json', dict(sha256=file_hash(path)))
    write_json(tmp_path / 'screened/reference-inputs.json', dict(files=[]))
    assert screen_component(tmp_path, 'new', db)['counts']['candidates'] == 1
    db.close()


def test_bad_reference_does_not_enter_index(tmp_path):
    path = tmp_path / 'bad.jsonl'
    jsonl(path, [chat('a')])
    db = connect(tmp_path / 'db.sqlite')
    with pytest.raises(ValueError, match='checksum'):
        index_reference(db, dict(path=str(path), sha256='wrong', scope='heldout'))
    assert db.execute('SELECT count(*) FROM files').fetchone()[0] == 0
    db.close()
