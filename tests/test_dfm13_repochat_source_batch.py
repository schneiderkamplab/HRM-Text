from scripts.dfm13_repochat_source_batch import select


def job(key, repo, error, kind='source'):
    return {'id': key, 'kind': kind, 'task': {'repository': repo, 'source_suffix': []}, 'source_failure': {'error': error}}


def test_source_batch_deduplicates_and_prioritizes_infrastructure():
    plan = {'jobs': [job('a', 'a/a', 'HTTP Error 401'), job('b', 'b/b', 'rate limit exceeded'),
                     job('c', 'b/b', 'rate limit exceeded'), job('d', 'c/c', 'download size limit'),
                     job('e', 'd/d', 'rate limit exceeded', 'audit')]}
    selected = select(plan, 1)
    assert len(selected) == 1
    assert [j['id'] for j in selected[0]] == ['b', 'c']
