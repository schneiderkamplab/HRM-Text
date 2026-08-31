from scripts.run_dfm10_dynaword_sft import (
    extract_json,
    generation_messages,
    training_instruction,
)


def test_generation_and_training_prompts_store_source_once() -> None:
    row = {
        "family": "spoken_normalization",
        "instruction": "Omskriv teksten.",
        "source_text": "Det her er en rå udskrift.",
    }
    messages = generation_messages(row)
    assert messages[-1]["content"] == row["source_text"]
    assert training_instruction(row) == "Omskriv teksten.\n\nKildetekst:\nDet her er en rå udskrift."


def test_extract_json_accepts_fenced_object() -> None:
    assert extract_json('```json\n{"response":"god", "preservation_notes":"ok"}\n```')["response"] == "god"
