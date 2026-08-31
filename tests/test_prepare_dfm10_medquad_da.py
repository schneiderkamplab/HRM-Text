from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "prepare_dfm10_medquad_da", ROOT / "scripts/prepare_dfm10_medquad_da.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_xml(path: Path, answer: str, *, source: str = "GARD") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'''<?xml version="1.0" encoding="UTF-8"?>
<Document id="42" source="{source}" url="https://example.org/42">
  <Focus>Example disease</Focus>
  <FocusAnnotations><Category>Disease</Category><UMLS><CUIs><CUI>C123</CUI></CUIs>
  <SemanticTypes><SemanticType>T047</SemanticType></SemanticTypes><SemanticGroup>Disorders</SemanticGroup></UMLS>
  <Synonyms><Synonym>Example syndrome</Synonym></Synonyms></FocusAnnotations>
  <QAPairs><QAPair pid="1"><Question qid="42-1" qtype="symptoms">What are the symptoms? ?</Question>
  <Answer>{answer}</Answer></QAPair></QAPairs>
</Document>''',
        encoding="utf-8",
    )


def test_extract_preserves_provenance_and_normalizes_question(tmp_path: Path) -> None:
    write_xml(tmp_path / "2_GARD_QA/42.xml", "Symptoms occur in 25% of patients.")
    rows, summary = MODULE.extract_rows(tmp_path, 12000)
    assert summary["accepted_requests"] == 1
    assert rows[0]["question_en"] == "What are the symptoms?"
    assert rows[0]["source_url"] == "https://example.org/42"
    assert rows[0]["cuis"] == ["C123"]
    assert rows[0]["question_type"] == "symptoms"


def test_extract_never_admits_withheld_or_oversized_answers(tmp_path: Path) -> None:
    write_xml(tmp_path / "10_MPlus_ADAM_QA/1.xml", "")
    write_xml(tmp_path / "2_GARD_QA/2.xml", "x" * 101)
    rows, summary = MODULE.extract_rows(tmp_path, 100)
    assert rows == []
    assert summary["rejected"] == {
        "answer_exceeds_translation_context_budget": 1,
        "copyright_withheld_answer": 1,
    }


def test_translation_validation_requires_numbers_and_units() -> None:
    source = {
        "request_id": "abc",
        "question_en": "What happens after 5 days?",
        "answer_en": "Give 20 mg daily for 5 days when instructed.",
    }
    good = {
        "request_id": "abc",
        "question_da": "Hvad sker der efter 5 dage?",
        "answer_da": "Giv 20 mg dagligt i 5 dage, når det er ordineret.",
    }
    assert MODULE.validate_translation(source, good) == []
    bad = {**good, "answer_da": "Giv 40 mg dagligt i 5 dage, når det er ordineret."}
    assert "numeric_values_changed" in MODULE.validate_translation(source, bad)
