from __future__ import annotations

import subprocess
import sys

import pyarrow as pa
import pyarrow.parquet as pq

from scripts.filter_opus_da_en import OUTPUT_SCHEMA


def test_builder_emits_both_directions_without_provenance_in_prompt(tmp_path) -> None:
    scored = tmp_path / "scored"
    output = tmp_path / "output"
    scored.mkdir()
    row = {
        "row_index": 7,
        "id": "OPUS-test-7",
        "source": "DGT",
        "da": "Dette er dansk.",
        "en": "This is Danish.",
        "da_lid": "dan_Latn",
        "da_lid_score": 0.99,
        "en_lid": "eng_Latn",
        "en_lid_score": 0.99,
        "alignment_score": 0.95,
        "accepted": True,
        "reason": "accepted",
    }
    pq.write_table(
        pa.Table.from_pylist([row], schema=OUTPUT_SCHEMA),
        scored / "part-00000-of-00001.parquet",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/build_opus_da_en_repaired.py",
            "--scored-root",
            str(scored),
            "--output-root",
            str(output),
        ],
        check=True,
    )
    rows = pq.read_table(output / "part-00000-of-00001.parquet").to_pylist()
    assert len(rows) == 2
    assert rows[0]["instruction"] == "Translate this Danish text to English:\n\nDette er dansk."
    assert rows[0]["response"] == "This is Danish."
    assert rows[1]["instruction"] == "Translate this English text to Danish:\n\nThis is Danish."
    assert rows[1]["response"] == "Dette er dansk."
    assert all("OPUS DGT" not in row["instruction"] for row in rows)
    assert all(row["opus_source"] == "DGT" for row in rows)
