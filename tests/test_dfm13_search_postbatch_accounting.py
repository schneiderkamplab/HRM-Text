from scripts import dfm13_search_postbatch_accounting as accounting


def test_holds_are_hash_bound_but_global_math_hold_survives():
    holds = [dict(candidate_sha256='old', candidate_content_sha256='content')]
    assert accounting.held('someid', 'old', 'other', holds)
    assert accounting.held('someid', 'new', 'content', holds)
    assert not accounting.held('someid', 'new', 'changed', holds)
    assert accounting.held('032d2d0cxxxx', 'new', 'changed', [])


def test_stratified_sample_is_reproducible_and_unique():
    rows = [dict(id=p + 'suffix') for prefixes in accounting.STRATA.values() for p in prefixes]
    first = accounting.stratified(rows)
    assert first == accounting.stratified(list(reversed(rows)))
    assert len({row['id'] for _, row in first}) == 8
    assert all(sum(group == g for group, _ in first) == 2 for g in accounting.STRATA)


def test_fresh_review_holds_include_partial_cleanup(monkeypatch, tmp_path):
    receipt = tmp_path / 'receipt.json'
    rows = [dict(id=str(i), candidate_sha256=str(i), assessment=assessment)
            for i, assessment in enumerate((
                'useful_supported_identification',
                'useful_partial_with_sensitive_attribution_cleanup',
                'partial_useful_gap_statement_with_unsupported_background',
                'hard_hold_wrong_historical_scope'))]
    monkeypatch.setattr(accounting, 'REPORTS', [receipt])
    monkeypatch.setattr(accounting, 'read', lambda path: {'rows': rows} if path == receipt else {'holds': []})
    monkeypatch.setattr(accounting.base, 'file_hash', lambda path: 'receipt-hash')
    holds, supported = accounting.collect_holds()
    assert {row['candidate_sha256'] for row in holds} == {'1', '2', '3'}
    assert {row['candidate_sha256'] for row in supported} == {'0'}
