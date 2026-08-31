from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from scripts import dfm10_persona_doms_chats as chats


def accepted_item(request_id: str, turns: int) -> dict:
    return {
        "request": {
            "request_id": request_id,
            "source": "test/source",
            "source_id": request_id,
            "focus": "test",
        },
        "generated": {
            "messages": [
                {"role": "user", "content": "Spørgsmål"},
                {"role": "assistant", "content": "Et fyldestgørende svar."},
            ],
            "exchange_count": turns,
            "training_tokens": 20,
            "teacher_model": "teacher",
        },
        "audit": {"judge_model": "judge", "decision": {"keep": True}},
    }


def build_args(tmp_path: Path, campaign: str) -> argparse.Namespace:
    return argparse.Namespace(
        work=tmp_path,
        campaign=campaign,
        shards=1,
        persona_output=tmp_path / "persona.jsonl",
        doms_output=tmp_path / "doms.jsonl",
        doms_minimum=1,
    )


def test_persona_build_retains_rows_above_minimum(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(chats, "PERSONA_ACCEPTED_QUOTAS", {3: 1, 4: 1})
    accepted = [accepted_item("a", 3), accepted_item("b", 3), accepted_item("c", 4)]
    monkeypatch.setattr(chats, "all_accepted", lambda *_: accepted)

    args = build_args(tmp_path, "persona")
    chats.cmd_build(args)

    rows = [json.loads(line) for line in args.persona_output.read_text().splitlines()]
    assert {row["row_id"] for row in rows} == {"persona:a", "persona:b", "persona:c"}
    summary = json.loads(args.persona_output.with_suffix(".summary.json").read_text())
    assert summary["accepted_rows_retained"] == "all"
    assert summary["rows"] == 3


def test_doms_build_does_not_cap_accepted_rows(monkeypatch, tmp_path: Path) -> None:
    accepted = [accepted_item(str(index), 4) for index in range(5)]
    monkeypatch.setattr(chats, "all_accepted", lambda *_: accepted)

    args = build_args(tmp_path, "doms")
    chats.cmd_build(args)

    assert len(args.doms_output.read_text().splitlines()) == 5


def test_persona_candidates_have_expected_turn_distribution() -> None:
    requests = chats.persona_requests(chats.DEFAULT_PERSONAS)
    counts: dict[int, int] = {}
    for row in requests:
        counts[row["target_turns"]] = counts.get(row["target_turns"], 0) + 1
    assert counts == chats.PERSONA_CANDIDATE_QUOTAS


def test_doms_requests_only_use_pseudonymized_field(tmp_path: Path) -> None:
    raw_secret = "RÅ KILDE MED PERSONNAVN " * 80
    pseudonymized = "Pseudonymiseret sagsfremstilling med faktiske oplysninger. " * 80
    path = tmp_path / "doms.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "case_id": "case-1",
                    "Overskrift": "Prøvesag",
                    "Afgørelsesstatus": "Afgjort",
                    "Faggruppe": "Civil",
                    "Ret": "Retten",
                    "Sagstype": "Sag",
                    "Instans": "Første",
                    "Sagsemner": "Prøve",
                    "text": raw_secret,
                    "text_anonymized": pseudonymized,
                }
            ]
        ),
        path,
    )
    requests = chats.doms_requests(path, target=1)
    assert len(requests) == 1
    assert "Pseudonymiseret" in requests[0]["source_text"]
    assert "PERSONNAVN" not in requests[0]["source_text"]
