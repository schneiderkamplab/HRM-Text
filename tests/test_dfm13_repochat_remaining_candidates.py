import pytest
from scripts.dfm13_repochat_remaining_candidates import remaining_tasks


def test_only_unattempted_candidates():
    tasks = [{'id': 'a', 'repository': 'a/a'}, {'id': 'b', 'repository': 'b/b'}, {'id': 'c', 'repository': 'c/c'}]
    assert remaining_tasks(tasks, {'a'}, {'b/b'}) == [tasks[2]]


def test_shared_repo_keeps_distinct_questions():
    tasks = [{'id': 'a', 'repository': 'a/a'}, {'id': 'b', 'repository': 'a/a'}]
    assert remaining_tasks(tasks, {'a'}, set()) == [tasks[1]]


def test_identity_mismatch_fails():
    with pytest.raises(ValueError):
        remaining_tasks([{'id': 'a', 'repository': 'a/a'}], {'unknown'}, set())
    with pytest.raises(ValueError):
        remaining_tasks([{'id': 'a', 'repository': 'a/a'}] * 2, set(), set())
