import argparse
import json
from pathlib import Path

import jinja2
from tokenizers import Tokenizer

from scripts.mimir_grounded_500k_model import deterministic_checks, render_generation
from scripts.prepare_mimir_grounded_500k_requests import cmd_prepare


def source(path: Path, category: str) -> None:
    row = {
        "category": category,
        "dataset": "test/source",
        "document_id": "doc-1",
        "license": "CC-BY-4.0",
        "passage": "Momentum is conserved in an isolated system. Forces change momentum over time.",
        "passage_sha256": "a" * 64,
        "source_url": "https://example.test/source",
    }
    path.write_text(json.dumps(row) + "\n")


def test_prepare_exact_balanced_candidate_counts(tmp_path: Path) -> None:
    paths = {}
    for category in ("technical_stem", "professional_domains", "compositional_reasoning", "grounded_factual_qa"):
        paths[category] = tmp_path / f"{category}.jsonl"
        source(paths[category], category)
    config = {
        "version": "test-v1",
        "target_per_category": 2,
        "candidate_per_category": 3,
        "shards": 4,
        "categories": {
            category: {"source": str(paths[category]), "task_variants": ["a", "b"]}
            for category in paths
        },
    }
    config["categories"]["mcq_answer_contract"] = {
        "sources": [str(paths["technical_stem"])], "task_variants": ["mcq"]
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    output = tmp_path / "output"
    cmd_prepare(argparse.Namespace(config=config_path, output=output, seed=7))
    summary = json.loads((output / "requests/summary.json").read_text())
    assert summary["total_candidates"] == 15
    assert set(summary["categories"].values()) == {3}
    assert len(list((output / "requests/shards").glob("part-*.jsonl"))) == 4


def test_mcq_contract_requires_requested_answer_position() -> None:
    request = {
        "category": "mcq_answer_contract",
        "answer_position": 2,
        "grounding_passage": "The force changes momentum over time in an isolated example.",
    }
    value = {
        "question": "Which statement describes the relationship?",
        "options": ["One", "Two", "Force changes momentum", "Four"],
        "correct_index": 2,
        "rationale": "The third option is directly supported by the stated physical relationship.",
        "verification": {"supported": True},
    }
    generated = render_generation(request, value)
    tokenizer = Tokenizer.from_file("data_io/trained_tokenizers/bpe/tokenizer.json")
    template = jinja2.Environment().from_string(
        Path("data_io/chat_templates/gemma4_native_chat.jinja").read_text()
    )
    checks = deterministic_checks(request, generated, tokenizer, template, 4096)
    assert all(checks.values())
    assert generated["response"] == "C"


def test_substantive_string_verification_is_valid() -> None:
    request = {
        "category": "technical_stem",
        "grounding_passage": "Momentum is conserved in an isolated system.",
    }
    generated = {
        "instruction": "Explain when momentum is conserved in a physical system.",
        "response": "Momentum is conserved when the system is isolated from external forces.",
        "verification": "The response states the same isolation condition as the grounding source.",
    }
    tokenizer = Tokenizer.from_file("data_io/trained_tokenizers/bpe/tokenizer.json")
    template = jinja2.Environment().from_string(
        Path("data_io/chat_templates/gemma4_native_chat.jinja").read_text()
    )
    checks = deterministic_checks(request, generated, tokenizer, template, 4096)
    assert all(checks.values())
