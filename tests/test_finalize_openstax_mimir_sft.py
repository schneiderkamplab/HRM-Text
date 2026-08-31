from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_script():
    path = ROOT / "scripts/finalize_openstax_mimir_sft.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(*, tokens: int = 200, score: int = 5) -> dict:
    return {
        "row_id": "0123456789abcdef0123456789abcdef",
        "source": "mimir_openstax_grounded_sft_v1",
        "messages": [
            {"role": "user", "content": "Explain the concept."},
            {"role": "assistant", "content": "A grounded explanation."},
        ],
        "training_tokens": tokens,
        "provenance": {"license": "CC-BY-4.0", "book_slug": "physics"},
        "quality_audit": {
            "scores": {
                "keep": True,
                "factuality": score,
                "reasoning_correctness": score,
                "instruction_answer_coherence": score,
                "pedagogical_value": score,
                "standalone_and_original": score,
            }
        },
    }


def test_accepts_fully_audited_fitting_row() -> None:
    script = load_script()
    script.validate_row(row(), set())


@pytest.mark.parametrize("tokens,score", [(4097, 5), (200, 3)])
def test_rejects_overlength_or_low_scored_row(tokens: int, score: int) -> None:
    script = load_script()
    with pytest.raises(ValueError):
        script.validate_row(row(tokens=tokens, score=score), set())
