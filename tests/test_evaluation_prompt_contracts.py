from __future__ import annotations

from types import SimpleNamespace

import pytest

from evaluation.benchmarks import MMLU, StandardMCQBenchmark
from evaluation.engines import VLLMEngine, _atomic_token_id, _hrm_marker_ids
from evaluation.main import _extract_choice_letter


class FakeTokenizer:
    def __init__(self, tokens: dict[str, int], eos_token: str):
        self.tokens = tokens
        self.eos_token = eos_token

    def __call__(self, text: str, **_: object) -> dict[str, list[int]]:
        if text in self.tokens:
            return {"input_ids": [self.tokens[text]]}
        return {"input_ids": [900, 901]}


def test_atomic_token_id_rejects_marker_split_into_text_pieces() -> None:
    tokenizer = FakeTokenizer({"<turn|>": 106}, eos_token="<turn|>")
    assert _atomic_token_id(tokenizer, "<turn|>") == 106
    assert _atomic_token_id(tokenizer, "<|im_start|>") is None
    assert _hrm_marker_ids(tokenizer) is None


def test_hrm_stop_id_is_derived_from_checkpoint_tokenizer(monkeypatch: pytest.MonkeyPatch) -> None:
    token_ids = {
        "<|im_start|>": 7,
        "<|im_end|>": 8,
        "<|box_end|>": 123,
        "<|object_ref_start|>": 13,
        "<|object_ref_end|>": 14,
        "<|quad_start|>": 15,
        "<|quad_end|>": 16,
    }
    tokenizer = FakeTokenizer(token_ids, eos_token="<|box_end|>")
    monkeypatch.setattr("evaluation.engines.AutoTokenizer.from_pretrained", lambda *a, **k: tokenizer)
    monkeypatch.setattr("evaluation.engines.LLM", lambda *a, **k: SimpleNamespace())

    engine = VLLMEngine("checkpoint", prompt_mode="hrm_tokens")

    assert engine.hrm_eoa_id == 123


def test_legacy_prompt_mode_fails_closed_for_gemma_tokenizer(monkeypatch: pytest.MonkeyPatch) -> None:
    tokenizer = FakeTokenizer({"<turn|>": 106}, eos_token="<turn|>")
    monkeypatch.setattr("evaluation.engines.AutoTokenizer.from_pretrained", lambda *a, **k: tokenizer)

    with pytest.raises(ValueError, match="use prompt_mode='gemma_chat'"):
        VLLMEngine("checkpoint", prompt_mode="hrm_tokens")


def test_auto_selects_gemma_chat_for_gemma_terminator(monkeypatch: pytest.MonkeyPatch) -> None:
    tokenizer = FakeTokenizer({"<turn|>": 106}, eos_token="<turn|>")
    tokenizer.bos_token = "<bos>"
    monkeypatch.setattr("evaluation.engines.AutoTokenizer.from_pretrained", lambda *a, **k: tokenizer)
    monkeypatch.setattr("evaluation.engines.LLM", lambda *a, **k: SimpleNamespace())

    engine = VLLMEngine("checkpoint", prompt_mode="auto")

    assert engine.prompt_mode == "gemma_chat"
    assert engine.chat_template is not None


def test_invalid_standard_mcq_output_is_wrong_not_chance_credit() -> None:
    benchmark = StandardMCQBenchmark()
    benchmark.ground_truths = [{"valid_set": {"A", "B", "C", "D"}, "gold": "A"}]

    assert benchmark.compute_metrics([""]) == {"n": 1, "acc": 0.0, "invalid": 1.0}


def test_invalid_mmlu_output_is_wrong_not_chance_credit() -> None:
    benchmark = MMLU.__new__(MMLU)
    benchmark.ground_truths = [
        {"valid_set": {"A", "B", "C", "D"}, "gold": "A", "subject": "math"}
    ]

    metrics = benchmark.compute_metrics([""])

    assert metrics["acc"] == 0.0
    assert metrics["acc_math"] == 0.0
    assert metrics["invalid"] == 1.0
    assert metrics["invalid_math"] == 1.0


@pytest.mark.parametrize(
    ("text", "expected"),
    [("A", "A"), ("(b)", "B"), ("Answer: C.", "C"), ("Final answer is d", "D")],
)
def test_choice_letter_extractor_accepts_unambiguous_formatting(text: str, expected: str) -> None:
    assert _extract_choice_letter(text) == expected


@pytest.mark.parametrize("text", ["A or B", "I think C", "Answer: A or B", ""])
def test_choice_letter_extractor_preserves_ambiguous_or_empty_output(text: str) -> None:
    assert _extract_choice_letter(text) == text
