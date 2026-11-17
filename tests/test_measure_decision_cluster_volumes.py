import importlib.util
from pathlib import Path

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location(
    "volumes", Path(__file__).resolve().parents[1] / "scripts/measure_decision_cluster_volumes.py")
volumes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(volumes)


@pytest.mark.parametrize("name,cluster", [
    ("giannor_gec_dala__train", "gec"),
    ("dfm12-dala-ca-acceptability__train", "acceptability"),
    ("folketingets-dokumenter-error-correction__part", "span_denoise"),
    ("common-pile-paragraph-reordering__part", "paragraph_order"),
    ("flan_factual__bool_q_1.0.parquet", "direct_labels"),
    ("dfm_dyna_instruct__when2call", "direct_labels"),
    ("dolci_instruct_sft_no_tools__part", "mixed_chat"),
    ("dfm12-dolci-translated-it__part", "mixed_chat"),
    ("faroese-dyna-instruct__part-000000", "mixed_chat"),
    ("dfm11-fineinstructions-en-controlled__part", "mixed_chat"),
    ("nemotron_instruction_reasoning_off", "instruction_constraints"),
    ("nemotron_terminal_corpus_native__code", "tool_actions"),
    ("allenai_big_reasoning_traces__DeepSeek:native", "reasoning_mixed"),
    ("openmathinstruct2_repaired", "math"),
    ("code_meta_reasoning_repaired", "code"),
    ("common-pile-prefix-continuation", "raw_unknown"),
    ("ai_arenaen_preferred", "preference"),
    ("opus_da_en_repaired", "translation"),
    ("scientific_summaries_repaired", "summary"),
    ("laerebogen_with_followups", "qa_evidence"),
])
def test_narrative_precedence(name, cluster):
    assert volumes.classify(name)[0] == cluster


def test_header_only(tmp_path):
    path = tmp_path / "inst_start.npy"
    with path.open("wb") as f:
        np.lib.format.write_array_header_1_0(
            f, dict(descr="<i8", fortran_order=False, shape=(123456789,)))
    # No payload exists; header count must still work.
    assert volumes.index_rows(path) == 123456789


def fixture():
    r = dict(start=0, end=20, source="s", stage="dfm11", category=0)
    m = dict(epoch=0, index_sha256={}, stored_tokens=20, ranges=[r])
    c = dict(status="verified", uncovered_rows=0, epoch=0, index_sha256={},
             manifest_sha256="hash", rows=6, token_exposure=60,
             sources=[dict(r, rows=6, token_exposure=60)])
    return m, c


def test_repeated_exposure_not_backing():
    m, c = fixture()
    volumes.validate(m, c, "hash")
    assert c["token_exposure"] == 3 * m["stored_tokens"]


@pytest.mark.parametrize("change", ["hash", "gap", "total", "source", "missing"])
def test_invalid_receipt(change):
    m, c = fixture()
    if change == "hash":
        c["manifest_sha256"] = "bad"
    elif change == "gap":
        m["ranges"][0]["start"] = 1
    elif change == "total":
        c["rows"] = 5
    elif change == "source":
        c["sources"][0]["source"] = "other"
    else:
        c["sources"] = []
    with pytest.raises(ValueError):
        volumes.validate(m, c, "hash")
