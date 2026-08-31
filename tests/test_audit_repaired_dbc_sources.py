from scripts.audit_repaired_dbc_sources import stable_priority


def test_stable_priority_is_deterministic_and_row_specific() -> None:
    assert stable_priority("file.parquet", 1, 7) == stable_priority("file.parquet", 1, 7)
    assert stable_priority("file.parquet", 1, 7) != stable_priority("file.parquet", 2, 7)
