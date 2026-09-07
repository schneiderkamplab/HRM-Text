from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts/prepare_dfm11_fineinstructions_danish.py"
SPEC = importlib.util.spec_from_file_location("prepare_dfm11_fineinstructions_danish", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_portable_pair_removes_document_but_retains_receipt() -> None:
    pair = {
        "id": "pair-1",
        "source_document": "private grounding text",
        "document_provenance": {
            "source_id": "source/repo",
            "source_path": "/work/cache/train.parquet",
            "source_row": 7,
        },
    }
    portable = MODULE.portable_pair(pair)
    assert portable["source_document"] is None
    assert portable["source_document_chars"] == len("private grounding text")
    assert len(portable["source_document_sha256"]) == 64
    assert portable["document_provenance"]["source_path"] == "source/repo/train.parquet"
    assert pair["source_document"] == "private grounding text"


def test_portable_row_normalizes_known_model_snapshot() -> None:
    row = {
        "generator_repo": "/cache/models--google--gemma-4-26B-A4B-it/snapshots/abc",
        "query_provenance": {
            "source_id": "query/source",
            "source_path": "/cache/queries.parquet",
        },
    }
    portable = MODULE.portable_row(row)
    assert portable["generator_repo"] == "google/gemma-4-26B-A4B-it"
    assert portable["query_provenance"]["source_path"] == "query/source/queries.parquet"
