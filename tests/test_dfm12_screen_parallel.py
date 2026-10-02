from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing

import pytest

from dfm12.european_screen import connect, screen_component, queue_component, index_reference
from dfm12.io import file_hash, write_json, digest
from dfm12.jobs import Queue, audit_payload
from dfm12.screen_parallel import batches, ordered


def row(text, **extra):
    return dict(id=text, messages=[dict(role='user', content=text), dict(role='assistant', content='Answer')],
                language='en', task='instruction', rendered_tokens=5, provenance={}, **extra)


def source(root, name, records):
    path = root/'candidates'/name/'candidates.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(x, ensure_ascii=False)+'\n' for x in records))
    write_json(path.parent/'receipt.json',dict(sha256=file_hash(path)))
    return path


def identity(value):
    return value


def test_batches_bounded_and_ordered(tmp_path):
    path = tmp_path/'input.jsonl'
    path.write_bytes(b'1\n2\n3\n4\n5\n')
    assert list(batches(path,max_rows=2,max_bytes=3)) == [[b'1\n'],[b'2\n'],[b'3\n'],[b'4\n'],[b'5\n']]
    with ProcessPoolExecutor(2, mp_context=multiprocessing.get_context('spawn')) as pool:
        assert list(ordered(pool,identity,range(20),3)) == list(range(20))


def test_parallel_screen_queue_parity_and_resume(tmp_path):
    outputs = []
    for parallel in (False, True):
        root = tmp_path/str(parallel)
        write_json(root/'screened/reference-inputs.json',dict(files=[]))
        db = connect(root/'screened/overlap.sqlite')
        heldout = source(root,'heldout',[row('held out '*30)])
        index_reference(db,dict(path=str(heldout),sha256=file_hash(heldout),scope='heldout'))
        records = [row(str(i)) for i in range(130)] + [row('0'),row('held out '*30),row('<tool_call>bad</tool_call>')]
        records.append(row('reverse',reverse_messages=row('2')['messages']))
        source(root,'first',records)
        source(root,'second',[row('1'),row('fresh')])
        pool = ProcessPoolExecutor(2, mp_context=multiprocessing.get_context('spawn')) if parallel else None
        try:
            for name in ('first','second'):
                screen_component(root,name,db,pool,max_pending=3)
                # Simulate a previously committed partial queue, including a finished job.
                q = Queue(root/'screened/jobs.sqlite')
                existing = dict(row('0' if name=='first' else 'fresh'),component=name)
                key = q.add('audit',audit_payload(existing,'model'))
                q.db.execute("UPDATE jobs SET status='done',result='{}',attempts=1 WHERE id=?",(key,))
                q.close()
                queue_component(root,name,'model',pool,max_pending=3)
                screen_component(root,name,db,pool,max_pending=3)
                queue_component(root,name,'model',pool,max_pending=3)
            q = Queue(root/'screened/jobs.sqlite')
            jobs = q.db.execute('SELECT id,payload,status,attempts FROM jobs ORDER BY rowid').fetchall()
            assert len(jobs)==131
            assert sum(j[2]=='done' for j in jobs)==2
            for key,payload,_,_ in jobs:
                assert key==digest(['audit',json.loads(payload)])
            q.close()
            outputs.append(([((root/'screened/candidates'/n/'candidates.jsonl').read_bytes(),
                               (root/'screened/candidates'/n/'exclusions.jsonl').read_bytes()) for n in ('first','second')],jobs))
        finally:
            if pool:
                pool.shutdown()
            db.close()
    assert outputs[0]==outputs[1]


def test_worker_failure_leaves_no_completed_component(tmp_path):
    write_json(tmp_path/'screened/reference-inputs.json',dict(files=[]))
    db=connect(tmp_path/'screened/overlap.sqlite')
    bad=row('bad'); bad['messages'][1]['role']='user'
    source(tmp_path,'new',[row('ok')]*70+[bad])
    with ProcessPoolExecutor(2,mp_context=multiprocessing.get_context('spawn')) as pool:
        with pytest.raises(ValueError):
            screen_component(tmp_path,'new',db,pool,max_pending=2)
    assert not (tmp_path/'screened/candidates/new/receipt.json').exists()
    assert db.execute('SELECT count(*) FROM retained').fetchone()[0]==0
    db.close()
