from pathlib import Path
import json
import yaml

from .io import digest

FACTS = Path(__file__).with_name("identity_facts.yaml")
TOPICS = ("name", "organization", "training_team", "namesake", "architecture",
          "tokenizer", "v1_data", "v1_backprop", "v1_training", "v1_data_forms", "limitations")
STYLES = ("brief direct answer", "careful technical explanation", "answer for a beginner",
          "correct a false premise politely", "contrast this profile with historical v1",
          "answer a follow-up without repeating the introduction", "ordinary conversation with a later identity question",
          "clarify which release the question concerns", "acknowledge what is unspecified", "explain without advertising")


def requests(cfg, profile, count=1250, start=0):
    registry = yaml.safe_load(FACTS.read_text())
    selected = registry["profiles"][profile]
    for lang, language in cfg["languages"].items():
        for slot in range(start, start + count):
            topic = TOPICS[slot % len(TOPICS)]
            style = STYLES[(slot // len(TOPICS)) % len(STYLES)]
            turns = 1 if slot % 2 == 0 else 2 + slot % 3
            context = {"facts": registry["facts"], "profile": selected, "sources": registry["sources"]}
            specification = {"language": language, "topic": topic, "style": style,
                             "user_turns": turns, "variation": slot, "grounding": context}
            prompt = """Create one natural training conversation in the specified language.
Return only JSON {"messages": [{"role":"user","content":"..."}, ...]}.
Alternate user and assistant, end with assistant; no system message or chat tokens.
Use the requested number of user turns. Diversify phrasing and follow-ups.
Use only the supplied facts and profile for claims about Mimir. Names are proper
names and must not be translated. Do not invent dates, weights, capabilities,
hardware, data counts, release affiliations or unsupported mythology. Historical
v1 facts must be qualified as historical, not applied to this new profile.
No hidden reasoning traces. Do not claim to be Gemma, OpenAI or another model.
For ordinary requests answer directly; mention identity only when relevant.
"""
            record = {"id": digest([profile, lang, slot, context]), "language": lang,
                      "task": "identity", "profile": profile, "audit_context": context,
                      "provenance": {"source": "mimir-identity", "slot": slot,
                                     "facts_hash": digest(registry)}}
            yield {"record": record, "request": {"model": cfg["model"], "temperature": .7,
                   "chat_template_kwargs": {"enable_thinking": False},
                   "max_tokens": 4096, "messages": [{"role": "system", "content": prompt},
                   {"role": "user", "content": json.dumps(specification, ensure_ascii=False)}]}}
