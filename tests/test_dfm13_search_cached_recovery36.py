from scripts.dfm13_search_cached_recovery36 import failure_bucket


def test_provider_failure_not_claimed_as_evidence_absence():
    assert failure_bucket([dict(status='error',error='Jina HTTP 402')],dict(error='no complete relevant cached paragraphs'))=='provider_payment_or_credit_failure_no_new_evidence'
    assert failure_bucket([dict(status='error',error='Jina HTTP 422')],dict(error='no complete relevant cached paragraphs'))=='provider_request_failure_no_new_evidence'


def test_successful_cache_selection_and_model_failures_distinct():
    assert failure_bucket([dict(status='done')],dict(error='no complete relevant cached paragraphs'))=='cached_evidence_selection_failure'
    assert failure_bucket([dict(status='done')],dict(error='invalid action types'))=='generation_invalid_action'
