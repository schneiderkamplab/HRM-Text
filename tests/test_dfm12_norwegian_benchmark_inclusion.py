import json
from pathlib import Path

import pytest

from dfm12.norwegian_benchmark_inclusion import (
    adapt, qa_records, heldout_index, read_tsv, NORQUAD_REV, FLEURS_REV, RUTER_REV, PROMPT, POLICY,
)
from dfm12.records import language, validate_messages
from dfm12.jobs import audit_payload


def qa_fixture(overlap=True):
    text = "Title\nThe supplied passage contains the exact short answer."
    question = {"id": 1, "question": "What is contained?", "answers": [{"text": "short answer", "answer_start": text.index("short answer")} ]}
    payload = {"data": [{"paragraphs": [{"context": text, "qas": [question]}]}]}
    qa = qa_records(payload)
    key = next(iter(qa))
    row = {"id": key, "source": "norquad-wikipedia", "language": ["nob"], "task": "qa", "messages": [
        {"role": "user", "content": PROMPT.format(context=text, question=question["question"])},
        {"role": "assistant", "content": "short answer"}]}
    attr = {"id": key, "norquad_git_revision": NORQUAD_REV, "article_url_inferred": "https://no.wikipedia.org/wiki/Title", "wikipedia_page_revision_known": False}
    held = heldout_index({"test": payload if overlap else {"data": []}})
    return row, attr, qa, held


@pytest.mark.parametrize("overlap", [True, False])
def test_full_norquad_inclusion_no_passage_filter_or_assistant_attribution(overlap):
    row, attr, qa, held = qa_fixture(overlap)
    result = adapt(row, 0, attr, qa, held, {})
    assert result["messages"] == row["messages"]
    assert result["provenance"]["attribution"] == attr
    assert result["provenance"]["benchmark_lineage"]["heldout_passage_overlap"] is overlap
    assert result["provenance"]["benchmark_lineage"]["source_hold"] is False
    assert result["accepted"] is False
    payload = audit_payload(result, "teacher")
    delivered = json.loads(payload["request"]["messages"][1]["content"])
    assert delivered["audit_context"]["benchmark_lineage"]["policy"] == POLICY


def fleurs_fixture(match="exact"):
    english = 'The original "quoted" English sentence is preserved.'
    target = "Denne teksten er den opprinnelige oversettelsen."
    row = {"id": "fleurs-alpaca-en-no_1", "source": "fleurs-alpaca-en-no", "language": ["nob", "eng"], "task": "translation", "messages": [
        {"role": "user", "content": "Oversett teksten fra engelsk til norsk\n\n" + (english if match == "exact" else english.replace('"', ''))},
        {"role": "assistant", "content": target}]}
    attr = {"id": row["id"], "fleurs_sentence_id": "1", "fleurs_revision": FLEURS_REV, "upstream_revision": RUTER_REV,
            "fleurs_split": "train", "upstream_split": "train", "fleurs_norwegian_config": "nb_no", "flores_origin": "FLORES-101 dev/devtest", "english_match": match}
    return row, attr, {"1": (english, target)}


@pytest.mark.parametrize("match", ["exact", "ascii_double_quotes_removed"])
def test_fleurs_keeps_evaluation_origin_and_native_messages(match):
    row, attr, parallel = fleurs_fixture(match)
    result = adapt(row, 0, attr, {}, {}, parallel)
    assert result["messages"] == row["messages"]
    assert result["language"] == "nb"
    assert result["provenance"]["source_language_labels"] == ["nob", "eng"]
    assert result["provenance"]["benchmark_lineage"]["known_evaluation_origin"]
    assert not result["provenance"]["benchmark_lineage"]["benchmarks_clear"]
    with pytest.raises(ValueError, match="ambiguous_or_multilingual_label"):
        language(row, {"languages": ["nb"]})


@pytest.mark.parametrize("mutation", ["source", "task", "language", "messages", "attribution", "offset"])
def test_fail_closed_qa_source_checks(mutation):
    row, attr, qa, held = qa_fixture()
    if mutation == "source": row["source"] = "other"
    elif mutation == "task": row["task"] = "translation"
    elif mutation == "language": row["language"] = ["nno"]
    elif mutation == "messages": row["messages"][-1]["content"] += " attribution"
    elif mutation == "attribution": attr["norquad_git_revision"] = "wrong"
    elif mutation == "offset": qa[row["id"]]["answer"]["answer_start"] = 0
    with pytest.raises(ValueError): adapt(row, 0, attr, qa, held, {})


@pytest.mark.parametrize("field,value", [("fleurs_split", "test"), ("fleurs_revision", "wrong"), ("fleurs_norwegian_config", "nn"), ("english_match", "fuzzy")])
def test_fleurs_lineage_is_not_generic_override(field, value):
    row, attr, parallel = fleurs_fixture()
    attr[field] = value
    with pytest.raises(ValueError): adapt(row, 0, attr, {}, {}, parallel)


def test_punkt_not_needed_tsv_uses_structured_quote_none(tmp_path):
    path = tmp_path / "source.tsv"
    path.write_text('1\taudio\tA "quote" remains here.\tx\tx\tx\tx\n')
    assert read_tsv(path)["1"] == 'A "quote" remains here.'
    path.write_text('1\ta\tOne\tx\tx\tx\tx\n1\ta\tOther\tx\tx\tx\tx\n')
    with pytest.raises(ValueError, match="conflicting"): read_tsv(path)


def test_real_norquad_review_covers_all_1886_and_1071_overlap():
    root = Path("data/dfm12/norwegian-benchmark-review-20260925")
    if not root.exists(): pytest.skip("pinned local evidence unavailable")
    qa = qa_records(json.loads((root / "norquad-wiki-train.json").read_text()))
    held = heldout_index({s: json.loads((root / f"norquad-all-{s}.json").read_text()) for s in ("validation", "test")})
    assert len(qa) == 1886
    assert sum(any(" ".join(r["context"].split()) in h["context"] for h in held.values()) for r in qa.values()) == 1071


def test_shared_template_guard_still_rejects():
    with pytest.raises(ValueError, match="embedded_chat_template"):
        validate_messages([{"role": "user", "content": "hello"}, {"role": "assistant", "content": "<start_of_turn>"}])


def test_prepare_refuses_existing_output_before_any_network_access(tmp_path):
    from dfm12.norwegian_benchmark_inclusion import prepare
    with pytest.raises(FileExistsError):
        prepare(tmp_path / "missing-base", tmp_path / "missing-review", tmp_path)


def test_real_gemma_render_limit_still_enforced():
    from dfm12.prepare import Renderer
    from dfm12.io import load
    renderer = Renderer(load("data/sampled_dfm11/metadata.json")["tokenizer_info"], 4096)
    with pytest.raises(ValueError, match="rendered_context_does_not_fit"):
        renderer.count([{"role": "user", "content": "Test " * 10000}, {"role": "assistant", "content": "Svar."}])
