from scripts.dfm13_search_temporal_followup import POLICY, PREFIXES


def test_bounded_unique_cases():
    assert len(PREFIXES) == len(set(PREFIXES)) == 8


def test_policy_preserves_historical_request_and_sources():
    assert 'Never silently substitute' in POLICY
    assert 'explicit historical dates preserve the requested period' in POLICY
    assert 'Unknown source URLs and genuinely unsupported claims remain disallowed' in POLICY
