from pathlib import Path

import pytest

import scripts.repair_danmarks_statistik_bt as repair
from scripts.generate_danmarks_statistik_bt_prompts import parse_generation


def test_target_filter_rejects_truncation_but_not_ordinary_preposition() -> None:
    assert not repair.target_is_candidate("A" * 120 + "...")[0]
    assert repair.target_is_candidate(
        "Danmarks Statistik beskriver de forhold, som opgørelsen tager højde for."
        + " Dette er en afsluttende og selvstændig forklaring med."
    )[0]


def test_prompt_filter_blocks_generation_context() -> None:
    assert repair.prompt_is_candidate(
        "Hvad oplyser Danmarks Statistik om udviklingen i eksporten?"
    )[0]
    assert not repair.prompt_is_candidate(
        "Sammenfat målteksten om udviklingen i eksporten."
    )[0]


def test_generated_rows_rejects_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "generated.jsonl"
    path.write_text('{"sample_id":"a"}\n{"sample_id":"a"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        repair.generated_rows(path)


def test_generation_parser_recovers_complete_fields_from_truncated_json() -> None:
    content = '{"usable": true, "prompt": "Hvad viser statistikken?", "reason": "Godt"\n  '
    parsed, recovered = parse_generation(content)
    assert recovered
    assert parsed == {
        "usable": True,
        "prompt": "Hvad viser statistikken?",
        "reason": "Godt",
    }


def test_generation_parser_does_not_invent_missing_prompt() -> None:
    with pytest.raises(ValueError, match="missing usable or prompt"):
        parse_generation('{"usable": true, "reason": "mangler"')
