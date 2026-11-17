import os
import subprocess
from scripts.qualify_cycle_variants import idle,trial_passed,belongs_to_worker


def test_admission_and_memory_verdict():
    assert idle({'0':dict(util=0,used_mib=0)})
    assert not idle({'0':dict(util=0,used_mib=0,pids=[123])})
    ranks=[dict(rank=0,passed=True,mixed_steps=100)]
    assert trial_passed(0,ranks,1,{'0':2048},[])
    assert not trial_passed(0,ranks,1,{'0':2047},[])
    assert not trial_passed(0,ranks,1,{'0':float('inf')},[])
    assert not trial_passed(0,ranks,1,{'0':9000},['monitor failed'])
    assert not trial_passed(1,ranks,1,{'0':9000},[])
    assert not trial_passed(0,[],1,{'0':9000},[])
    assert not trial_passed(0,[dict(rank=0,passed=True,mixed_steps=99)],1,{'0':9000},[])


def test_worker_ancestry_across_new_process_group():
    p=subprocess.Popen(['sleep','10'],start_new_session=True)
    try:
        assert os.getpgid(p.pid)!=os.getpgid(os.getpid())
        assert belongs_to_worker(p.pid,os.getpid())
        assert not belongs_to_worker(os.getpid(),p.pid)
    finally:p.terminate();p.wait()


def test_only_memory_failures_allow_bp15_fallback():
    from scripts.qualify_cycle_variants import memory_failure
    complete=[dict(rank=0,passed=True,mixed_steps=100)]
    assert memory_failure(1,'CUDA out of memory',[],1,{'0':100})
    assert memory_failure(1,'QUALIFICATION_HEADROOM',[],1,{'0':100})
    assert memory_failure(0,'',complete,1,{'0':100})
    assert not memory_failure(1,'Compiler failed',[],1,{'0':100})
    assert not memory_failure(0,'',[],1,{'0':100})
    assert not memory_failure(0,'',complete,1,{'0':float('inf')})
