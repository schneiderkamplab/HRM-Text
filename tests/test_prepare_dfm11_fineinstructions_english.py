from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts/prepare_dfm11_fineinstructions_english.py"
SPEC = importlib.util.spec_from_file_location("prepare_dfm11_fineinstructions_english", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_balanced_quotas_redistribute_small_source_capacity() -> None:
    quotas = MODULE.balanced_quotas(Counter({"small": 2, "a": 10, "b": 10}), 14)
    assert quotas == {"small": 2, "a": 6, "b": 6}


def test_portable_pair_retains_coordinates_but_removes_absolute_path() -> None:
    pair = {
        "id": "pair-1",
        "document_provenance": {
            "source_id": "common_pile_arxiv",
            "source_revision": "abc",
            "source_path": "/private/cache/arxiv-0000.json.gz",
            "source_row": 12,
            "window_index": 3,
        },
    }
    portable = MODULE.portable_pair(pair)
    assert portable["document_provenance"] == {
        "source_id": "common_pile_arxiv",
        "source_revision": "abc",
        "source_path": "common_pile_arxiv/arxiv-0000.json.gz",
        "source_row": 12,
        "window_index": 3,
    }
    assert pair["document_provenance"]["source_path"].startswith("/")


def test_portable_chat_normalizes_local_generator_snapshot() -> None:
    chat = {
        "generator_repo": (
            "/cache/models--google--gemma-4-26B-A4B-it/"
            "snapshots/4d7ae4984b7db7de8f8457170b3f1a419ee76d52"
        ),
        "generator_revision": "4d7ae4984b7db7de8f8457170b3f1a419ee76d52",
    }
    portable = MODULE.portable_chat(chat)
    assert portable["generator_repo"] == "google/gemma-4-26B-A4B-it"
    assert portable["generator_revision"] == chat["generator_revision"]
    assert chat["generator_repo"].startswith("/")


def test_rank_value_is_stable_and_source_scoped() -> None:
    first = MODULE.rank_value(11031, "source-a", "pair-1")
    assert first == MODULE.rank_value(11031, "source-a", "pair-1")
    assert first != MODULE.rank_value(11031, "source-b", "pair-1")


def test_controlled_ids_preserves_mode_mapping(tmp_path: Path) -> None:
    ledger = tmp_path / "accepted.jsonl"
    ledger.write_text(
        '{"pair_id":"legacy","audit":{"keep":true}}\n'
        '{"pair_id":"controlled","audit":{"interaction_mode":"revision"}}\n'
    )
    controlled, modes = MODULE.controlled_ids(ledger, {"legacy", "controlled"})
    assert controlled == {"controlled": "revision"}
    assert modes == Counter({"revision": 1})
