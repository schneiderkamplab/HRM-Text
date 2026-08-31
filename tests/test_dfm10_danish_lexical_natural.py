import json
from pathlib import Path

from scripts.dfm10_danish_lexical_natural import (
    contains_exact_number,
    prepare_requests,
    validate_generated,
)


def write_source(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_prepare_explodes_gold_batches_without_replacing_them(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    write_source(source / "dsldk_danish_sentiment_lexicon.jsonl", [{
        "messages": [
            {"role": "user", "content": "prompt\n\n[{\"ord\":\"idyllisk\"}]"},
            {"role": "assistant", "content": "[{\"ord\":\"idyllisk\",\"polaritet\":3,\"retning\":\"positiv\",\"styrke\":3}]"},
        ],
        "source": "sentiment", "source_id": "batch-00000", "license": "CC",
    }])
    write_source(source / "dsldk_danish_framenet.jsonl", [{
        "messages": [
            {"role": "user", "content": "prompt\n\n[{\"udtryk\":\"løbe\"}]"},
            {"role": "assistant", "content": "[{\"udtryk\":\"løbe\",\"semantisk_frame\":\"Self_motion\"}]"},
        ],
        "source": "framenet", "source_id": "batch-00000", "license": "notice",
    }])
    summary = prepare_requests(source, tmp_path / "work", shards=2, batch_size=8)
    assert summary["items"] == 2
    assert summary["sentiment_items"] == 1
    assert summary["framenet_items"] == 1
    assert sum(1 for _ in source.glob("*.jsonl")) == 2


def test_sentiment_validation_requires_signed_exact_polarity() -> None:
    item = {
        "item_id": "sentiment:0", "kind": "sentiment",
        "source_input": {"ord": "trist"},
        "gold": {"polaritet": -2, "retning": "negativ"},
    }
    good = {"item_id": "sentiment:0", "user": "Er trist et negativt ord?",
            "assistant": "Ja. Ordet er negativt med polariteten -2."}
    bad = {**good, "assistant": "Ja. Ordet er negativt med polariteten 2."}
    assert validate_generated(item, good) == []
    assert "exact_polarity_missing" in validate_generated(item, bad)
    assert contains_exact_number("polariteten -2", -2)
    assert not contains_exact_number("polariteten 2", -2)


def test_framenet_validation_requires_exact_frame() -> None:
    item = {
        "item_id": "framenet:0", "kind": "framenet",
        "source_input": {"udtryk": "løbe"},
        "gold": {"semantisk_frame": "Self_motion"},
    }
    result = {"item_id": "framenet:0", "user": "Hvilket frame aktiverer løbe?",
              "assistant": "Udtrykket aktiverer FrameNet-framet Self_motion."}
    assert validate_generated(item, result) == []
