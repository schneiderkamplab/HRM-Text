import pytest
from scripts import dfm13_search_eoir_cached_repair as repair


def cached_body():
    return next(p['content'] for p in repair.parent.read(repair.SOURCE)['data'] if p['url'] == repair.URL)


def test_exact_complete_cached_clauses():
    body = cached_body()
    chunks = repair.extract(body)
    assert all(body[c['start']:c['end']] == c['text'] for c in chunks)
    sections = {c['section']:c['text'] for c in chunks}
    assert 'first page of Form I-881' in sections['uscis_eoir40_legacy_exception']
    assert 'Otherwise, USCIS will not accept' in sections['uscis_eoir40_legacy_exception']
    assert 'Otherwise, the Immigration Court will not accept' in sections['court_eoir40_legacy_exception']
    assert 'battered' in sections['court_only_clause_complete_scope']
    assert 'seven years' in sections['substantive_standards_and_exceptions']
    assert 'ten years' in sections['substantive_standards_and_exceptions']


def test_changed_or_ambiguous_anchor_fails_closed():
    body = cached_body()
    with pytest.raises(ValueError, match='missing or ambiguous'):
        repair.extract(body.replace('# Who May File Form I-881?', '# Changed'))
    with pytest.raises(ValueError, match='missing or ambiguous'):
        repair.extract(body+'\n# Who May File Form I-881?')
