from pathlib import Path
from dfm12.wave4_cpu import configuration, LANGUAGES, queue_lock
from dfm12.wave4_transforms import transform, PROMPTS


def test_pair_mesh_and_budgets():
    cfg = configuration()
    assert len(cfg['languages']) == 34
    pairs = cfg['requested_pairs']
    assert len(pairs) == 308
    assert len(set(map(tuple,pairs))) == len(pairs)
    for a,b in pairs:
        assert a != b
        assert {a,b} & LANGUAGES.keys()
        assert cfg['pair_budgets'][a+'-'+b]['fraction'] == (.25 if 'en' in (a,b) else .0625)


def test_native_transform_contracts():
    assert set(PROMPTS) == set(LANGUAGES)
    text = '\n\n'.join(('This is paragraph '+str(i)+' with a coherent set of words describing a distinct subject. ')*4 for i in range(4))
    for lang in LANGUAGES:
        for task in ('denoising','prefix-continuation','span-filling','paragraph-reordering'):
            row = transform(text,lang,task,dict(source='test'))
            assert row['messages'][0]['role'] == 'user'
            assert row['messages'][1]['role'] == 'assistant'
            assert row['audit_context']['original'] == text
            assert row['language'] == lang
            if task in ('denoising','paragraph-reordering'):
                assert row['messages'][1]['content'] == text


def test_lock_releases(tmp_path):
    for _ in range(2):
        with queue_lock(tmp_path/'queue.lock'):
            assert (tmp_path/'queue.lock').exists()


def test_enqueue_chunk_resume_does_not_duplicate(tmp_path,monkeypatch):
    import json
    import sqlite3
    from dfm12 import wave4_cpu
    from dfm12.io import file_hash
    path=tmp_path/'source.jsonl'
    path.write_text(''.join(json.dumps({'id':str(i),'messages':[]})+'\n' for i in range(513)))
    sealed=dict(path=str(path),sha256=file_hash(path))
    monkeypatch.setattr(wave4_cpu,'preflight',lambda args:sealed)
    wave4_cpu.enqueue(tmp_path,'test',path)
    with sqlite3.connect(tmp_path/'audit/jobs.sqlite') as db:
        assert db.execute('SELECT count(*) FROM jobs').fetchone()[0]==513
        db.execute('DELETE FROM components')
        db.commit()
    # Simulate an interrupted import with committed rows but no completion seal.
    wave4_cpu.enqueue(tmp_path,'test',path)
    with sqlite3.connect(tmp_path/'audit/jobs.sqlite') as db:
        assert db.execute('SELECT count(*) FROM jobs').fetchone()[0]==513
        assert db.execute('SELECT sha FROM components').fetchone()[0]==sealed['sha256']
