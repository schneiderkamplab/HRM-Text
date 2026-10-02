"""Strict chat adapters and metadata isolation."""
import re
from .io import digest

ALIASES = {"eng": "en", "dan": "da", "nld": "nl", "dut": "nl", "nob": "nb",
           "nno": "nn", "swe": "sv", "isl": "is", "ice": "is", "fao": "fo", "pol": "pl",
           "deu": "de", "ger": "de", "fra": "fr", "fre": "fr", "spa": "es",
           "ita": "it", "ces": "cs", "cze": "cs", "fin": "fi", "est": "et",
           "cat": "ca", "ell": "el", "gre": "el", "ron": "ro", "rum": "ro", "ukr": "uk"}
MARKERS = ("<|im_start|>", "<|im_end|>", "<start_of_turn>", "<end_of_turn>",
           "[INST]", "<|eot_id|>")


def language(row, source):
    value = (row.get(source["language_field"]) if source.get("language_field")
             else row.get("language", row.get("lang", source.get("language"))))
    if isinstance(value, list):
        if len(value) != 1:
            raise ValueError("ambiguous_or_multilingual_label")
        value = value[0]
    value = source.get("language_aliases", {}).get(value, ALIASES.get(value, value))
    if value not in source.get("languages", [source.get("language")]):
        raise ValueError("unapproved_or_ambiguous_language")
    return value


def validate_messages(messages):
    if not isinstance(messages, list) or len(messages) < 2:
        raise ValueError("missing_conversation")
    expected = "user"
    for i, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError("invalid_message")
        role, content = message.get("role"), message.get("content")
        if message.get("tool_calls") or role == "tool":
            raise ValueError("requires_native_tool_converter")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty_or_nontext_content")
        if any(marker in content for marker in MARKERS):
            raise ValueError("embedded_chat_template")
        if i == 0 and role == "system":
            continue
        if role != expected:
            raise ValueError("invalid_role_order")
        expected = "assistant" if role == "user" else "user"
    if messages[-1]["role"] != "assistant":
        raise ValueError("missing_assistant_target")


def chat_fingerprint(messages):
    return digest([{k: re.sub(r"\s+", " ", m[k]).strip() for k in ("role", "content")}
                   for m in messages])


def convert(row, source, relative_file, ordinal):
    if row.get("tools") or row.get("functions"):
        raise ValueError("requires_native_tool_converter")
    adapter = source.get("adapter")
    if adapter == "input_target":
        row = dict(row, messages=[
            {"role": "user", "content": row.get(source["input_field"])},
            {"role": "assistant", "content": row.get(source["target_field"])}])
    elif adapter == "conversation":
        conversation = row.get(source["conversation_field"])
        if not isinstance(conversation, list):
            raise ValueError("missing_conversation")
        # Preserve tool-call metadata until the strict validator rejects it.
        row = dict(row, messages=[dict(m, role=m.get(source.get("role_field", "role")),
                                      content=m.get(source.get("content_field", "content")))
                                  for m in conversation])
    elif adapter is not None:
        raise ValueError("unknown_source_adapter")
    messages = row.get("chosen") if source["kind"] == "preference-chosen" else row.get("messages")
    if messages is None and isinstance(row.get("conversations"), list):
        roles = {"human": "user", "gpt": "assistant", "system": "system"}
        messages = [dict(m, role=roles.get(m.get("from"), m.get("from")), content=m.get("value"))
                    if "from" in m else dict(m) for m in row["conversations"]]
    kwargs = row.get("chat_template_kwargs") or {}
    if kwargs:
        if not isinstance(kwargs, dict) or any(v for k, v in kwargs.items()
                if k not in {"custom_instructions", "enable_thinking"}):
            raise ValueError("unsupported_template_metadata")
        if kwargs.get("enable_thinking"):
            raise ValueError("requires_native_reasoning_converter")
        custom = kwargs.get("custom_instructions")
        if custom:
            if not isinstance(custom, str) or not isinstance(messages, list):
                raise ValueError("invalid_custom_instructions")
            messages = [dict(m) for m in messages]
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] = custom + "\n\n" + messages[0]["content"]
            else:
                messages.insert(0, {"role": "system", "content": custom})
    validate_messages(messages)
    messages = [{"role": m["role"], "content": m["content"]} for m in messages]
    lang = language(row, source)
    task = "instruction"
    if source["kind"] == "dala":
        task = "acceptability" if "/acceptability/" in "/" + relative_file else "correction"
        if task == "acceptability" and messages[-1]["content"].strip() not in {"yes", "no"}:
            raise ValueError("invalid_acceptability_label")
        name = {"en": "English", "nl": "Nederlandse"}[lang]
        if name.lower() not in messages[0]["content"].lower():
            raise ValueError("missing_explicit_language")
    provenance = {"repo": source["repo"], "revision": source["revision"],
                  "file": relative_file, "ordinal": ordinal,
                  "source_id": str(row.get("id", row.get("prompt_id", ordinal))),
                  "pair_id": row.get("pair_id"), "constituent": row.get("source"), "split": "train"}
    return {"id": digest(provenance), "messages": messages, "language": lang,
            "task": task, "provenance": provenance}
