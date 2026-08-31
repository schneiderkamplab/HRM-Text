import argparse
import json
from pathlib import Path

import pytest

from scripts.dfm10_tidsskrift_grounded_model import (
    cmd_verify_shard as cmd_verify_sft_shard,
    extract_json,
    audit_messages,
    extract_generated_value,
    generation_record,
    render_instruction,
    validate_audit,
    validate_examples,
)
from scripts.prepare_dfm10_tidsskrift_grounded_sft import chunk_paragraphs
from scripts.dfm10_tidsskrift_chats_model import (
    cmd_verify_shard,
    render_chat,
    validate_audit as validate_chat_audit,
)


def request() -> dict:
    return {
        "request_id": "request",
        "examples_requested": 8,
        "language": "da",
        "source_text": "Et fagligt artikeluddrag med dokumenterede forhold. " * 80,
    }


def examples() -> list[dict]:
    rows = []
    for index in range(5):
        rows.append(
            {
                "task": "grounded_qa",
                "instruction": f"Hvilken relevant faglig sammenhæng nummer {index} kan udledes af uddraget?",
                "response": f"Den faglige sammenhæng nummer {index} følger af de dokumenterede forhold.",
                "support": "De dokumenterede forhold i uddraget underbygger svaret.",
                "summary_is_natural": False,
            }
        )
    for index in range(2):
        rows.append(
            {
                "task": "grounded_explanation",
                "instruction": f"Forklar den faglige mekanisme nummer {index} i uddraget.",
                "response": f"Mekanisme nummer {index} forbinder de dokumenterede forhold.",
                "support": "Sammenhængen fremgår direkte af uddragets beskrivelse.",
                "summary_is_natural": False,
            }
        )
    rows.append(
        {
            "task": "section_summary",
            "instruction": "Sammenfat det sammenhængende faglige afsnit kort og præcist.",
            "response": "Afsnittet beskriver de dokumenterede forhold og deres indbyrdes sammenhæng.",
            "support": "Alle elementer i sammenfatningen optræder i det sammenhængende uddrag.",
            "summary_is_natural": True,
        }
    )
    return rows


def test_chunker_keeps_coherent_paragraph_units() -> None:
    paragraphs = [(f"Afsnit {index}. " + "Relevant dansk fagtekst. " * 30) for index in range(8)]
    chunks = chunk_paragraphs(
        paragraphs,
        min_chars=600,
        target_chars=1000,
        max_chars=1600,
        overlap_paragraphs=1,
    )
    assert len(chunks) >= 3
    assert all(600 <= len(chunk) <= 1600 for chunk in chunks)
    assert "Afsnit 1" in chunks[0]


def test_teacher_contract_accepts_five_qa_two_explanations_and_summary() -> None:
    validated = validate_examples({"examples": examples()}, request())
    assert len(validated) == 8
    assert validated[-1]["task"] == "section_summary"
    assert validated[-1]["item_id"] == "request:7"


def test_teacher_contract_drops_only_unnatural_summary() -> None:
    rows = examples()
    rows[-1]["summary_is_natural"] = False
    validated = validate_examples({"examples": rows}, request())
    assert len(validated) == 7
    assert all(row["task"] != "section_summary" for row in validated)


def test_teacher_contract_retains_partial_batch() -> None:
    record = generation_record(json.dumps({"examples": examples()[:6]}), request(), "teacher")
    assert record["generation_ok"] is True
    assert record["examples_returned"] == 6
    assert record["examples_retained"] == 6
    assert record["partial_recovery"] is True


def test_truncated_generation_recovers_complete_objects() -> None:
    raw = json.dumps({"examples": examples()})
    truncated = raw[: raw.rfind("},") + 1]
    recovered = extract_generated_value(truncated)
    assert 1 <= len(recovered["examples"]) < 8
    assert validate_examples(recovered, request())


def test_json_extraction_accepts_a_repeated_trailing_object() -> None:
    assert extract_json('{"keep": true}\n{"keep": true}') == {"keep": True}


def test_audit_is_row_level_and_fail_closed() -> None:
    generated = {"examples": validate_examples({"examples": examples()}, request())}
    decisions = []
    for index, row in enumerate(generated["examples"]):
        decisions.append(
            {
                "item_id": row["item_id"],
                "keep": True,
                "source_support": 3 if index == 0 else 5,
                "instruction_answer_coherence": 5,
                "language_quality": 5,
                "interesting_training_value": 5,
                "task_appropriateness": 5,
                "primary_failure": "unsupported" if index == 0 else "none",
                "complaint": "",
            }
        )
    audited = validate_audit({"decisions": decisions}, generated, minimum_score=4)
    assert audited[0]["keep"] is False
    assert all(row["keep"] is True for row in audited[1:])


def test_training_prompt_carries_the_licensed_excerpt() -> None:
    row = validate_examples({"examples": examples()}, request())[0]
    prompt = render_instruction(request(), row)
    assert prompt.startswith("Artikeluddrag:\n")
    assert "Opgave:\n" in prompt
    assert row["instruction"] in prompt


def test_chat_contract_accepts_two_to_ten_exchanges() -> None:
    value = {
        "turns": [
            {
                "student": "Hvad handler dette faglige emne grundlæggende om?",
                "assistant": "Det handler grundlæggende om de dokumenterede forhold i uddraget.",
                "support": "Uddragets indledning beskriver disse forhold.",
            },
            {
                "student": "Hvordan hænger de forhold så mere præcist sammen?",
                "assistant": "De hænger sammen gennem den mekanisme, som uddraget beskriver.",
                "support": "Mekanismen og relationen er beskrevet i uddraget.",
            },
        ]
    }
    messages = render_chat(value, request())
    assert [row["role"] for row in messages] == ["system", "user", "assistant", "user", "assistant"]
    assert request()["source_text"] in messages[0]["content"]


def test_chat_audit_requires_every_assistant_turn_to_pass() -> None:
    generated = {"exchange_count": 2}
    value = {
        "keep": True,
        "source_support": 5,
        "conversation_coherence": 5,
        "natural_followups": 5,
        "language_quality": 5,
        "teaching_value": 5,
        "assistant_turns": [
            {"turn_index": 0, "supported": True, "complaint": ""},
            {"turn_index": 1, "supported": False, "complaint": "unsupported"},
        ],
        "primary_failure": "unsupported",
        "complaint": "",
    }
    assert validate_chat_audit(value, generated, 4)["keep"] is False


def test_chat_shard_completion_requires_full_coverage(tmp_path: Path) -> None:
    requests = tmp_path / "requests.jsonl"
    generated = tmp_path / "generated.jsonl"
    audited = tmp_path / "audited.jsonl"
    requests.write_text("".join(json.dumps({"request_id": str(i)}) + "\n" for i in range(100)))
    generated.write_text("".join(json.dumps({"request_id": str(i), "generation_ok": True}) + "\n" for i in range(99)))
    audited.write_text("".join(json.dumps({"request_id": str(i), "audit_ok": True}) + "\n" for i in range(99)))
    with pytest.raises(SystemExit):
        cmd_verify_shard(argparse.Namespace(
            requests=requests,
            generated=generated,
            audited=audited,
            minimum_completion_fraction=1.0,
        ))


def test_audit_canonicalizes_ordered_hash_ids_with_copy_omissions() -> None:
    generated = {"examples": validate_examples({"examples": examples()}, request())}
    decisions = []
    for index, row in enumerate(generated["examples"]):
        decisions.append({
            "item_id": row["item_id"].replace("request", "requst"),
            "keep": True,
            "source_support": 5,
            "instruction_answer_coherence": 5,
            "language_quality": 5,
            "interesting_training_value": 5,
            "task_appropriateness": 5,
            "primary_failure": "none",
            "complaint": "",
        })
    audited = validate_audit({"decisions": decisions}, generated, minimum_score=4)
    assert [row["item_id"] for row in audited] == [row["item_id"] for row in generated["examples"]]
    assert all(row["item_id_repaired"] is True for row in audited)


def test_audit_uses_short_aliases_and_maps_them_to_canonical_ids() -> None:
    generated = {"examples": validate_examples({"examples": examples()}, request())}
    payload = json.loads(audit_messages(request(), generated)[1]["content"])
    assert [row["item_id"] for row in payload["examples"]] == [f"item_{i}" for i in range(8)]
    decisions = [
        {
            "item_id": f"item_{index}",
            "keep": True,
            "source_support": 5,
            "instruction_answer_coherence": 5,
            "language_quality": 5,
            "interesting_training_value": 5,
            "task_appropriateness": 5,
            "primary_failure": "none",
            "complaint": "",
        }
        for index in range(8)
    ]
    audited = validate_audit({"decisions": decisions}, generated, minimum_score=4)
    assert [row["item_id"] for row in audited] == [row["item_id"] for row in generated["examples"]]


def test_chat_allows_legitimate_discussion_of_a_dataset() -> None:
    value = {
        "turns": [
            {
                "student": "Hvilke data byggede forskernes analyse på?",
                "assistant": "Forskerne anvendte et datasæt med mere end to millioner opslag.",
                "support": "Uddraget angiver datasættets størrelse og anvendelse.",
            },
            {
                "student": "Hvordan blev opslagene knyttet til geografiske områder?",
                "assistant": "De blev kortlagt til de relevante valgdistrikter.",
                "support": "Kortlægningen til valgdistrikter er beskrevet direkte.",
            },
        ]
    }
    assert render_chat(value, request())


def test_chat_allows_concise_evidence_locators_and_textual_criticism() -> None:
    value = {
        "turns": [
            {
                "student": "Hvad sammenligner den tekstkritiske analyse?",
                "assistant": "Den skelner mellem den originale kildetekst og udgiverens senere tilføjelser.",
                "support": "Afsnit 1",
            },
            {
                "student": "Hvorfor er den skelnen vigtig for fortolkningen?",
                "assistant": "Den gør det muligt at afgøre, hvilke formuleringer der tilhører originalen.",
                "support": "Note 13",
            },
        ]
    }
    assert render_chat(value, request())


def test_chat_rejects_actual_source_prompt_meta_language() -> None:
    value = {
        "turns": [
            {
                "student": "Hvad står der i denne kildetekst om emnet?",
                "assistant": "Den beskriver de dokumenterede forhold på området.",
                "support": "Forholdene beskrives direkte i uddraget.",
            },
            {
                "student": "Hvordan hænger forholdene sammen?",
                "assistant": "De forbindes gennem den beskrevne mekanisme.",
                "support": "Mekanismen fremgår direkte af uddraget.",
            },
        ]
    }
    with pytest.raises(ValueError, match="meta-language"):
        render_chat(value, request())


def test_chat_shard_threshold_remains_explicitly_configurable(tmp_path: Path) -> None:
    requests = tmp_path / "requests.jsonl"
    generated = tmp_path / "generated.jsonl"
    audited = tmp_path / "audited.jsonl"
    requests.write_text("".join(json.dumps({"request_id": str(i)}) + "\n" for i in range(100)))
    generated.write_text("".join(json.dumps({"request_id": str(i), "generation_ok": True}) + "\n" for i in range(99)))
    audited.write_text("".join(json.dumps({"request_id": str(i), "audit_ok": True}) + "\n" for i in range(99)))
    args = argparse.Namespace(
        requests=requests,
        generated=generated,
        audited=audited,
        minimum_completion_fraction=0.98,
    )
    cmd_verify_shard(args)
    args.minimum_completion_fraction = 1.0
    with pytest.raises(SystemExit):
        cmd_verify_shard(args)


def test_sft_shard_completion_requires_full_coverage(tmp_path: Path) -> None:
    requests = tmp_path / "requests.jsonl"
    generated = tmp_path / "generated.jsonl"
    audited = tmp_path / "audited.jsonl"
    requests.write_text("".join(json.dumps({"request_id": str(i)}) + "\n" for i in range(100)))
    generated.write_text("".join(json.dumps({"request_id": str(i), "generation_ok": True}) + "\n" for i in range(98)))
    audited.write_text("".join(json.dumps({"request_id": str(i), "audit_ok": True}) + "\n" for i in range(98)))
    with pytest.raises(SystemExit):
        cmd_verify_sft_shard(argparse.Namespace(
            requests=requests,
            generated=generated,
            audited=audited,
            minimum_completion_fraction=1.0,
        ))
