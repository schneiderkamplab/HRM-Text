import json
import pytest
from dfm12.io import write_json,file_hash
from scripts.slovak_chunked_preflight import chunks


def setup(tmp_path):
    source=tmp_path/'source.jsonl'
    source.write_text(''.join(json.dumps({'id':i})+'\n' for i in range(7)))
    return dict(component='sk-additive-v1-direct-en-sk',path=str(source),sha256=file_hash(source),rows=7)


def test_exact_parts_resume_and_no_mutation(tmp_path):
    entry=setup(tmp_path);root=tmp_path/'root';base=tmp_path/'base'
    first=list(chunks(root,base,[entry],size=3))
    assert [name for name,_ in first]==[entry['component']+f'-part{i:05d}' for i in range(3)]
    assert [json.loads(line)['id'] for _,p in first for line in p.read_text().splitlines()]==list(range(7))
    assert list(chunks(root,base,[entry],size=3))==first
    first[0][1].write_text('{}\n')
    with pytest.raises(ValueError,match='chunk changed'):list(chunks(root,base,[entry],size=3))


def test_existing_whole_prevents_duplicate_parts(tmp_path):
    entry=setup(tmp_path);base=tmp_path/'base'
    write_json(base/'audit-ready'/entry['component']/'receipt.json',{'sealed':True})
    result=list(chunks(tmp_path/'root',base,[entry],size=3))
    assert result[0][0]==entry['component'] and len(result)==1


def test_missing_rows_cannot_seal_complete(tmp_path):
    entry=setup(tmp_path);entry['rows']=8
    with pytest.raises(ValueError,match='coverage mismatch'):list(chunks(tmp_path/'root',tmp_path/'base',[entry],size=3))
    assert not (tmp_path/'root/audit-chunks'/entry['component']/'receipt.json').exists()


def test_local_wait_retries_only_lock_timeout(monkeypatch,tmp_path):
    from scripts import slovak_chunked_preflight as m
    from dfm12 import wave4_cpu
    calls=[]
    def enqueue(*args):
        calls.append(args)
        if len(calls)==1:raise TimeoutError('Audit enqueue lock remained busy')
        return 'queued'
    monkeypatch.setattr(wave4_cpu,'enqueue',enqueue)
    assert m.enqueue_with_wait(tmp_path,'part',tmp_path/'part',wait_seconds=3600)=='queued'
    assert len(calls)==2 and calls[0]==calls[1]


@pytest.mark.parametrize('error',[TimeoutError('Other timeout'),ValueError('Source changed')])
def test_local_wait_never_retries_other_errors(monkeypatch,tmp_path,error):
    from scripts import slovak_chunked_preflight as m
    from dfm12 import wave4_cpu
    calls=[]
    def enqueue(*args):calls.append(args);raise error
    monkeypatch.setattr(wave4_cpu,'enqueue',enqueue)
    with pytest.raises(type(error),match=str(error)):
        m.enqueue_with_wait(tmp_path,'part',tmp_path/'part')
    assert len(calls)==1


def test_local_wait_deadline(monkeypatch,tmp_path):
    from scripts import slovak_chunked_preflight as m
    from dfm12 import wave4_cpu
    ticks=iter([0,1800]);monkeypatch.setattr(m.time,'monotonic',lambda:next(ticks))
    def enqueue(*args):raise TimeoutError('Audit enqueue lock remained busy')
    monkeypatch.setattr(wave4_cpu,'enqueue',enqueue)
    with pytest.raises(TimeoutError):m.enqueue_with_wait(tmp_path,'part',tmp_path/'part',wait_seconds=1800)
    with pytest.raises(ValueError):m.enqueue_with_wait(tmp_path,'part',tmp_path/'part',wait_seconds=1)


@pytest.mark.parametrize('phase,waiting,expected',[('pivot_enqueue','hrtimer_nanosleep',True),
    ('pivot_build','hrtimer_nanosleep',False),('pivot_enqueue','0',False)])
def test_yield_only_to_identified_waiter(tmp_path,monkeypatch,phase,waiting,expected):
    from scripts import slovak_chunked_preflight as m
    from dfm12 import diagnostic_server
    peer=dict(pid=123,start_ticks='pin',session_id=1,cmdline=['owned'])
    write_json(tmp_path/'enqueue-peer.json',peer)
    write_json(tmp_path/'coverage-continuation-status.json',dict(pid=123,phase=phase))
    monkeypatch.setattr(diagnostic_server,'identity',lambda pid:peer)
    original=m.Path.read_text
    monkeypatch.setattr(m.Path,'read_text',lambda self,*a,**k:waiting if str(self)=='/proc/123/wchan' else original(self,*a,**k))
    sleeps=[];monkeypatch.setattr(m.time,'sleep',sleeps.append)
    assert m.yield_to_waiting_peer(tmp_path,tmp_path)==expected
    assert sleeps==([2.] if expected else [])
