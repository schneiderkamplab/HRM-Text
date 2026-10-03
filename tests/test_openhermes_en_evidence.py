"""Evidence bookkeeping tests; no quality judgments or model calls."""
import pytest

from scripts.prepare_openhermes_en_evidence import digest, disposition


@pytest.mark.parametrize('audit,repair,verdict,published,expected', [
    (None, None, None, None, 'missing_source_audit'),
    ({'row_failure': True}, None, None, None, 'source_audit_operational_failure'),
    ({'exclude': True}, None, None, None, 'source_excluded_by_existing_judge'),
    ({'repair_needed': True}, None, None, None, 'repair_missing'),
    ({'repair_needed': True}, {'ok': False}, None, None, 'repair_generation_failure'),
    ({'repair_needed': True}, {'ok': True}, None, None, 'repair_audit_missing'),
    ({'repair_needed': True}, {'ok': True}, {'row_failure': True}, None,
     'repair_audit_operational_failure'),
    ({'repair_needed': True}, {'ok': True}, {'keep': False}, None,
     'repair_rejected_by_existing_judge'),
    ({'repair_needed': True}, {'ok': True}, {'keep': True}, None,
     'accepted_repair_missing_from_package'),
    ({'clean': True}, None, None, {'kind': 'openhermes_en_clean'}, 'accepted_original'),
    ({'clean': True}, {'ok': True}, {'keep': True}, {'kind': 'openhermes_en_repaired'},
     'accepted_repaired'),
])
def test_disposition(audit, repair, verdict, published, expected):
    assert disposition({}, audit, repair, verdict, published) == expected


def test_hash_preserves_text_but_normalizes_mapping_order():
    assert digest({'a': 1, 'b': 2}) == digest({'b': 2, 'a': 1})
    assert digest([{'content': 'hello '}]) != digest([{'content': 'hello'}])
