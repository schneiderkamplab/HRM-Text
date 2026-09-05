import argparse
import gzip
import json

from scripts.prepare_dfm11_folketing_error_correction import (
    PROMPT_PREFIX,
    corruption_edit_count,
    finalize,
    target_quality_failure,
    validate_row,
)


def row(source: str, target: str) -> dict:
    return {
        "messages": [
            {"role": "user", "content": PROMPT_PREFIX + source},
            {"role": "assistant", "content": target},
        ]
    }


def test_declared_corruptions_are_counted() -> None:
    target = "Denne almindelige tekst om loven indeholder mere end tyve ord, så kvalitetskravet er opfyldt uden problemer i denne lille test."
    source = target.replace("Denne", "Dcnne", 1).replace("almindelige", "alrnindelige", 1)
    assert corruption_edit_count(source, target) == 2
    assert validate_row(row(source, target)) == (None, 2)


def test_generator_inherits_lowercase_mapping_for_uppercase_characters() -> None:
    target = "Denne Moderne Lovtekst indeholder mere end tyve almindelige danske ord, så den kan bruges til at teste store bogstaver i generatoren sikkert."
    source = target.replace("Moderne", "rnoderne", 1).replace("Lovtekst", "1ovtekst", 1)
    assert corruption_edit_count(source, target) == 2


def test_undeclared_change_is_rejected() -> None:
    target = "Denne almindelige tekst om loven indeholder mere end tyve ord, så kvalitetskravet er opfyldt uden problemer i denne lille test."
    source = target.replace("loven", "katten")
    assert corruption_edit_count(source, target) is None
    assert validate_row(row(source, target))[0] == "source_target_not_declared_corruption"


def test_noop_is_rejected() -> None:
    target = "Denne almindelige tekst om loven indeholder mere end tyve ord, så kvalitetskravet er opfyldt uden problemer i denne lille test."
    assert validate_row(row(target, target))[0] == "normalized_noop"


def test_fragmented_index_is_rejected() -> None:
    text = "\n".join(["Opslag....................", "1", "Andet....................", "2"] * 8)
    assert target_quality_failure(text) in {"target_fragmented_lines", "target_index_or_dot_leaders"}


def test_finalize_removes_rejected_rows_and_writes_package(tmp_path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    audit = tmp_path / "audit.jsonl"
    data = source / "data" / "train-00000.jsonl.gz"
    data.parent.mkdir(parents=True)
    target = (
        "Denne almindelige danske lovtekst indeholder mere end tyve ord, så den "
        "kan bruges som en sammenhængende prøve på korrekt filtrering af datasættet."
    )
    rows = []
    for index in range(2):
        item = row(target.replace("Denne", "Dcnne", 1), target)
        item["metadata"] = {
            "source_id": f"row-{index}",
            "dfm11_repair": {"declared_ocr_edits": 1},
        }
        rows.append(item)
    with gzip.open(data, "wt", encoding="utf-8") as handle:
        for item in rows:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    audit.write_text(
        "\n".join(
            json.dumps({"row_id": f"train-00000.jsonl.gz:{index}", "keep": index == 0})
            for index in range(2)
        )
        + "\n"
    )

    finalize(
        argparse.Namespace(
            input=source,
            output=output,
            audit=[audit],
            expected_rows=2,
            workers=1,
            force=False,
        )
    )

    with gzip.open(output / "data" / "train-00000.jsonl.gz", "rt", encoding="utf-8") as handle:
        kept = [json.loads(line) for line in handle]
    manifest = json.loads((output / "metadata" / "manifest.json").read_text())
    assert [item["metadata"]["source_id"] for item in kept] == ["row-0"]
    assert manifest["counts"] == {"seen": 2, "kept": 1, "rejected": 1}
    assert manifest["data_files"][0]["rows"] == 1
    assert (output / "README.md").is_file()
    assert (output / "validate_dataset.py").is_file()
