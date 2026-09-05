from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts/prepare_dfm11_koolbardi_exports.py"
SPEC = importlib.util.spec_from_file_location("prepare_dfm11_koolbardi_exports", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def valid_row(language: str = "en") -> dict:
    return {
        "id": "row-1",
        "messages": [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Answer"},
            {"role": "user", "content": "Follow-up"},
            {"role": "assistant", "content": "Follow-up answer"},
        ],
        "language_lane": language,
        "user_complexity_level": "general",
        "length_band": "short",
        "desired_exchanges": 2,
        "actual_exchanges": 2,
        "rendered_token_count": 100,
        "finish_reason": "desired_exchanges",
        "diversity": {
            "topic_id": "testing",
            "persona_source": MODULE.PERSONA_SOURCES[language],
            "persona_source_id": "private-join-key",
        },
        "generator": {"model": "/local/model", "seed": 1},
        "instruction_audit": {"accepted": True, "model": "/local/model", "reason": "long text"},
        "turn_audits": [
            {"accepted": True, "model": "/local/model", "reason": "long text"},
            {"accepted": True, "model": "/local/model", "reason": "long text"},
        ],
        "audit": {"accepted": True, "turns": 2, "model": "/local/model"},
    }


def test_publication_row_strips_private_and_local_metadata() -> None:
    row = MODULE.publication_row(valid_row())
    assert "persona_source_id" not in row["diversity"]
    assert row["generator"]["model"] == MODULE.MODEL_ID
    assert row["audit"]["model"] == MODULE.MODEL_ID
    assert "reason" not in row["instruction_audit"]


def test_publication_row_rejects_non_native_roles() -> None:
    row = valid_row()
    row["messages"][1]["role"] = "system"
    with pytest.raises(ValueError, match="role sequence"):
        MODULE.publication_row(row)
