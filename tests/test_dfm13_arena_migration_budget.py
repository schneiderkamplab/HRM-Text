import asyncio
import pytest
from scripts.dfm13_arena_migration_budget import retry_numbers, take


def test_third_interrupted_preserved_does_not_exhaust():
    prior=[(1,'invalid_response','h','a'),(2,'abort_status_unknown','h','b'),(3,'interrupted_unknown','h','c')]
    assert list(retry_numbers(prior,3,{(7,'correction',3,'h')},7,'correction')) == [4]
    assert prior[2][0]==3


def test_finished_timeout_counts_and_numbers_never_reused():
    assert list(retry_numbers([(4,'abort_status_unknown','h','')],3,set(),1,'retry_audit')) == [5,6]
    assert list(retry_numbers([(i,'invalid_response','h','') for i in (1,2,3)],3,set(),1,'x')) == []


def test_unapproved_and_repeated_interruptions_fail():
    with pytest.raises(ValueError):retry_numbers([(1,'interrupted_unknown','h','')],3,set(),1,'x')
    with pytest.raises(ValueError):retry_numbers([(1,'inflight','h','')],3,set(),1,'x')
    with pytest.raises(ValueError):retry_numbers([(i,'interrupted_unknown','h','') for i in (1,2)],3,{(1,'x',i,'h') for i in (1,2)},1,'x')


def test_workstealing_exactly_once():
    qs=[asyncio.Queue() for _ in range(8)]
    for i in range(50):qs[1].put_nowait(i)
    seen=[]
    for i in range(80):
        result=take(qs,i%8)
        if result is not None:
            owner,value=result;seen.append(value);qs[owner].task_done()
    assert sorted(seen)==list(range(50))
    assert take(qs,0) is None
