"""Conservative PLLuM adapters. Preparation eligibility is not audit acceptance."""
import re
import unicodedata

from .io import digest
from .records import validate_messages

SOURCES = {
    "pllumic": ("pelcra/PLLuMIC", "509bd048c165ff91207ac7fb5db835ac0468a6a7", ("pllumic.json",)),
    "pllumic-syn": ("pelcra/PLLuMIC-syn-ext", "1c3ab9e8437a83a22ed5741dbcb380ac0a7160d5",
                    ("pllumic_synthetic_extension_54k.jsonl",)),
    "pllum-align": ("NASK-PIB/PLLuM-Align", "aa9ae3d4e0d4ffa7b5f52548928de20517122e4b",
                    ("dialogs.jsonl", "ranking.jsonl", "rating.jsonl")),
}


def folded(text):
    return unicodedata.normalize("NFKD", text.casefold().replace("\u0142", "l")).encode("ascii", "ignore").decode()


BRAND = re.compile(r"\b(pllum\w*|chatgpt|openai|gemini|mistral|claude|anthropic|llama|bielik|nask)\b")
IDENTITY = re.compile(r"\b(kim jestes|jak sie nazywasz|kto (cie|ciebie) (stworzyl|zaprojektowal)|"
                      r"twoi tworcy|twoim (tworca|producentem)|who are you|your name|who created you)\b")
EXTRA_MARKERS = ("<|", "<start_of_turn>", "<end_of_turn>", "[INST]", "[/INST]")


def adapt(name, row, relative, ordinal):
    repo, revision, files = SOURCES[name]
    if relative not in files:
        raise ValueError("unreviewed_file")
    if not isinstance(row, dict):
        raise ValueError("invalid_row")
    if row.get("split", "train") != "train":
        raise ValueError("held_out_split")
    if row.get("tools") or row.get("functions"):
        raise ValueError("tool_metadata")
    source_id = str(row.get("conv_id", row.get("id", ordinal)))
    if "identity" in folded(source_id):
        raise ValueError("identity_category")
    if name == "pllum-align":
        if source_id.startswith(("polqa", "toxigen", "antropic")):
            raise ValueError("benchmark_or_inherited_provenance_hold")
        if source_id.startswith("neut-nonpl"):
            raise ValueError("explicit_nonpolish_category")
        messages = row.get("chosen")
        rejected = row.get("rejected")
        validate_messages(messages)
        validate_messages(rejected)
        if messages[:-1] != rejected[:-1]:
            raise ValueError("preference_context_mismatch")
        if messages[-1] == rejected[-1]:
            raise ValueError("identical_preference_answers")
        if relative == "rating.jsonl":
            chosen, other = row.get("chosen_rating"), row.get("rejected_rating")
            if (type(chosen) not in (int, float) or type(other) not in (int, float)
                    or not 1 <= other < chosen <= 5 or chosen < 4):
                raise ValueError("invalid_or_weak_preference_rating")
    else:
        messages = row.get("messages")
        if not isinstance(messages, list) or not all(isinstance(m, dict) for m in messages):
            raise ValueError("invalid_messages")
        if name == "pllumic":
            # Verified pinned organic release: seq numbers identify instruction pairs.
            offset = int(bool(messages) and messages[0].get("role") == "system")
            expected = ([-1] if offset else []) + [i // 2 for i in range(len(messages) - offset)]
            if any(type(m.get("seq")) is not int for m in messages) or [m["seq"] for m in messages] != expected:
                raise ValueError("invalid_sequence")
        # Upstream explicitly documents empty system placeholders; drop only that placeholder.
        if messages and messages[0].get("role") == "system" and messages[0].get("content") == "":
            messages = messages[1:]
        seq = [m.get("seq") for m in messages]
        if name != "pllumic" and any(v is not None for v in seq):
            if not all(type(v) is int for v in seq) or seq != sorted(set(seq)):
                raise ValueError("invalid_sequence")
        validate_messages(messages)
    for message in messages:
        if any(message.get(k) for k in ("tool_calls", "function_call", "tool_call_id", "tools", "functions")):
            raise ValueError("tool_metadata")
        if message.get("language", "pol") not in ("pol", "pl"):
            raise ValueError("nonpolish_message_label")
        category = folded(str(message.get("type", "")) + " " + str(message.get("subtype", "")))
        if "identity" in category or "tozsamos" in category:
            raise ValueError("identity_category")
        content = message["content"]
        if any(marker in content for marker in EXTRA_MARKERS):
            raise ValueError("embedded_chat_template")
        text = folded(content)
        if IDENTITY.search(text) or (message["role"] in ("system", "assistant") and BRAND.search(text)):
            raise ValueError("identity_or_brand_review")
    if row.get("language", "pl") not in ("pl", "pol"):
        raise ValueError("nonpolish_row_label")
    provenance = {"repo": repo, "revision": revision, "file": relative, "ordinal": ordinal,
                  "source_id": source_id, "split": "unsplit_release", "license": "cc-by-sa-4.0",
                  "source_metadata": {k: v for k, v in row.items() if k not in ("messages", "chosen", "rejected")},
                  "message_metadata": [{k: v for k, v in m.items() if k not in ("role", "content")}
                                       for m in messages]}
    result = {"id": digest([repo, revision, relative, ordinal]), "language": "pl", "task": "instruction",
              "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
              "provenance": provenance, "audit_status": "pending"}
    if name == "pllum-align":
        # Preference supervision certifies only the final answer, not the assistant history.
        result["target_message_index"] = len(messages) - 1
    return result


def rendered_count(renderer, record):
    from scripts.tokenize_chat_template import examples_from_messages, tokenize_example
    total = 0
    for example in examples_from_messages(record["messages"], [], record.get("target_message_index")):
        encoded = tokenize_example(renderer.tokenizer, renderer.template, example, False)
        if encoded is None or sum(map(len, encoded)) > renderer.max_length:
            raise ValueError("full_context_render_rejected")
        total += sum(map(len, encoded))
    if not total:
        raise ValueError("no_training_targets")
    return total
