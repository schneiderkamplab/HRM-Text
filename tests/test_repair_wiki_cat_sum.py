from argparse import Namespace

import scripts.repair_wiki_cat_sum as repair


def test_support_score_rewards_grounded_phrase() -> None:
    target = "The film was released in 2014 by Tribeca Film."
    grounded = "Tribeca Film released the film in March 2014."
    unrelated = "The director discussed a different production."
    assert sum(repair.support_score(target, grounded)) > sum(
        repair.support_score(target, unrelated)
    )


def test_split_evidence_removes_web_boilerplate() -> None:
    paragraphs = [
        "The company was founded in 2002 and developed two games.\n"
        "Click here to sign up for our newsletter.\n"
        "All rights reserved copyright 2020."
    ]
    assert repair.split_evidence(paragraphs) == [
        "The company was founded in 2002 and developed two games."
    ]


def test_build_row_keeps_only_supported_summary_sentences(monkeypatch) -> None:
    monkeypatch.setattr(repair, "fits", lambda instruction, response, max_seq_len: True)
    row = {
        "title": "Example company",
        "summary": [
            {"text": "Example company was founded in 2002 in Edinburgh."},
            {"text": "It employed 10,000 people in Tokyo."},
        ],
        "paragraphs": [
            "Example company was founded in Edinburgh in 2002 by two developers."
        ],
    }
    args = Namespace(
        min_content_recall=0.60,
        min_bigram_recall=0.15,
        min_response_chars=20,
        max_seq_len=4096,
    )
    stats = repair.ShardStats(source="test", part=0)
    result = repair.build_row(row, args, stats)
    assert result is not None
    assert "founded in 2002" in result["response"]
    assert "10,000" not in result["response"]
    assert "Source evidence:" in result["instruction"]


def test_title_anchor_rejects_pronoun_only_fragment() -> None:
    assert repair.title_anchored("Example company", "Example company was founded in 2002.")
    assert not repair.title_anchored("Example company", "It was founded in 2002.")


def test_byte_ranges_cover_file_without_overlap(tmp_path) -> None:
    source = tmp_path / "rows.jsonl"
    source.write_text("".join(f'{{"row": {index}}}\n' for index in range(100)))
    seen = []
    for part in range(7):
        stats = repair.ShardStats(source=source.name, part=part)
        seen.extend(row["row"] for row in repair.iter_partition(source, part, 7, stats))
    assert sorted(seen) == list(range(100))
    assert len(seen) == len(set(seen))
