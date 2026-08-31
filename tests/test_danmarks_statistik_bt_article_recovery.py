import argparse
import json

from scripts.generate_danmarks_statistik_bt_article_recovery import (
    PROMPT_VERSION,
    fail_close_errors,
    parse_content,
)
from scripts.recover_danmarks_statistik_bt_from_articles import SCHEMA, excerpt, extract_article


def test_extract_article_decodes_danish_as_utf8():
    raw = """<html><body><div class="cludoContent"><h1>Priser på boliger</h1>
    <p>Flere købere søgte mod større byer.</p></div></body></html>""".encode()
    result = extract_article(raw)
    assert "Priser på boliger" in result
    assert "købere" in result
    assert "Ã" not in result


def test_excerpt_keeps_target_and_following_article_context():
    article = "A" * 4000 + "MÅLPASSAGE med tallet 12." + "B" * 12000
    result = excerpt(article, "MÅLPASSAGE med tallet 12.", 8000)
    assert "MÅLPASSAGE med tallet 12." in result
    assert result.endswith("B" * 100)
    assert len(result) == 8000


def test_parse_content_recovers_complete_fields_from_stalled_json():
    content = '{"usable":true,"prompt":"Hvad skete der?","answer":"Det steg med 4 pct.","reason":"Understøttet"'
    result, recovered = parse_content(content)
    assert recovered
    assert result["usable"] is True
    assert result["answer"] == "Det steg med 4 pct."


def test_generation_prompt_version_is_model_specific_and_stable():
    assert PROMPT_VERSION == "dst_article_recovery_31b_v1_20260829"


def test_candidate_schema_preserves_untrusted_generator_self_rating():
    assert "generator_self_usable" in SCHEMA.names


def test_fail_close_errors_preserves_model_provenance(tmp_path):
    partition_root = tmp_path / "partitions"
    partition_root.mkdir()
    path = partition_root / "partition_0.jsonl"
    path.write_text(
        json.dumps(
            {
                "sample_id": "sample-1",
                "source_row": 1,
                "generator_model": "test-model",
                "generator_prompt_version": PROMPT_VERSION,
                "generation_error": "timeout",
            }
        )
        + "\n"
    )

    fail_close_errors(
        argparse.Namespace(
            partition_root=partition_root, partitions=1, expected_model="test-model"
        )
    )

    row = json.loads(path.read_text())
    assert row["usable"] is False
    assert row["terminal_generation_rejection"] is True
    assert row["generator_model"] == "test-model"
    assert "generation_error" not in row
