from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "prepare_dfm10_medical", ROOT / "scripts/prepare_dfm10_medical.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_elrc_conversion_is_bidirectional_and_filters_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "en-da.csv"
    output = tmp_path / "elrc.parquet"
    write_csv(
        source,
        ["id", "lang", "source_text", "target_text"],
        [
            {
                "id": 1,
                "lang": "en-da",
                "source_text": "The patient should contact a physician.",
                "target_text": "Patienten bør kontakte en læge.",
            },
            {
                "id": 2,
                "lang": "en-da",
                "source_text": 'TOC \\o "1-3" \\h Introduction 3',
                "target_text": 'TOC \\o "1-3" \\h Indledning 3',
            },
            {
                "id": 3,
                "lang": "en-da",
                "source_text": "The patient should contact a physician.",
                "target_text": "Patienten bør kontakte en læge.",
            },
        ],
    )

    manifest = MODULE.convert_elrc(source, output)
    rows = pq.read_table(output).to_pylist()

    assert manifest["accepted_pairs"] == 1
    assert manifest["output_rows"] == 2
    assert manifest["rejected"] == {"duplicate": 1, "word_toc_markup": 1}
    assert {row["task"] for row in rows} == {
        "medical_translation_en_da",
        "medical_translation_da_en",
    }
    assert {row["response"] for row in rows} == {
        "The patient should contact a physician.",
        "Patienten bør kontakte en læge.",
    }


def test_nhs_conversion_only_emits_grounded_targets(tmp_path: Path) -> None:
    source = tmp_path / "synthetic_clinical_notes.csv"
    output = tmp_path / "nhs.parquet"
    note = (
        "The synthetic patient attended the emergency department with a severe headache. "
        "Observations were recorded and a neurological assessment was completed before "
        "the patient was referred for a CT scan."
    )
    write_csv(
        source,
        ["clinical_note_id", "clean_note_text", "note_subject", "note_type"],
        [
            {
                "clinical_note_id": "note-1",
                "clean_note_text": note,
                "note_subject": "ED Triage Follow-Up",
                "note_type": "ED",
            },
            {
                "clinical_note_id": "note-2",
                "clean_note_text": "too short",
                "note_subject": "Short",
                "note_type": "ED",
            },
        ],
    )

    manifest = MODULE.convert_nhs(source, output)
    rows = pq.read_table(output).to_pylist()

    assert manifest["input_rows"] == 2
    assert manifest["output_rows"] == 3
    assert manifest["rejected"] == {"note_too_short": 1}
    assert {row["task"] for row in rows} == {
        "synthetic_clinical_note_type",
        "synthetic_clinical_note_subject",
        "synthetic_clinical_note_span_filling",
    }
    assert all(row["response"] for row in rows)


def test_synthetic_note_sanitization_removes_fake_identifiers_and_mojibake() -> None:
    note = (
        "Patient Name: Jane Example\nPatient ID: fake-123\nNHS Number: 123456789\n"
        "Temperature 38.8Â°C.\nNurse Jane Example\nNMC number: 12A3456B"
    )
    cleaned = MODULE.sanitize_synthetic_note(note)
    assert "Jane Example" not in cleaned
    assert "fake-123" not in cleaned
    assert "123456789" not in cleaned
    assert "Â" not in cleaned
    assert "38.8°C" in cleaned
