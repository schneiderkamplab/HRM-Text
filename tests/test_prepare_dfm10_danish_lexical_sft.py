import csv
import json
from pathlib import Path

from scripts.prepare_dfm10_danish_lexical_sft import framenet_rows, sentiment_rows


def test_sentiment_rows_preserve_gold_polarities(tmp_path: Path) -> None:
    source = tmp_path / "sentiment.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["glad", "", "adj.", "1", "3", "glad;glade"])
        writer.writerow(["trist", "", "adj.", "2", "-2", "trist;triste"])
    rows = list(sentiment_rows(source, batch_size=8, seed=1))
    assert len(rows) == 1
    target = json.loads(rows[0]["messages"][1]["content"])
    assert {item["ord"]: item["polaritet"] for item in target} == {"glad": 3, "trist": -2}


def test_framenet_rows_drop_null_and_deduplicate(tmp_path: Path) -> None:
    source = tmp_path / "frames.tsv"
    source.write_text(
        "id\tgruppenr\tudtryk\tlemma\tlemklas\tkernevb\tframe\tkomm\n"
        "1\t1\tløbe\tløbe\tvb.\tløbe\tSelf_motion\t\n"
        "2\t1\tløbe\tløbe\tvb.\tløbe\tSelf_motion\t\n"
        "3\t1\tx\tx\tsb.\tNULL\tNULL\t\n",
        encoding="utf-8",
    )
    rows = list(framenet_rows(source, batch_size=8, seed=1))
    target = json.loads(rows[0]["messages"][1]["content"])
    assert target == [{"udtryk": "løbe", "semantisk_frame": "Self_motion"}]
