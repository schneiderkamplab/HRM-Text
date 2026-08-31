from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from scripts.audit_repaired_govreport import sample_file, stable_priority


def test_stable_priority_is_deterministic_and_row_specific() -> None:
    assert stable_priority("a.parquet", 1, 7) == stable_priority("a.parquet", 1, 7)
    assert stable_priority("a.parquet", 1, 7) != stable_priority("a.parquet", 2, 7)


def test_sample_file_records_context_specific_provenance(tmp_path: Path) -> None:
    path = tmp_path / "train.parquet"
    pq.write_table(
        pa.table({"instruction": ["Summarize this report."], "response": ["Summary."]}),
        path,
    )

    rows, seen = sample_file(
        path,
        10,
        7,
        source_id="ccdv/govreport-summarization-repaired-8k",
        task_name="govreport_summarization_repaired_8k",
        form="8K complete-report summary",
    )

    assert seen == 1
    assert rows[0]["source_id"].endswith("-8k")
    assert rows[0]["task_name"].endswith("_8k")
    assert rows[0]["form"] == "8K complete-report summary"
