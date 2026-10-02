"""Future sampling budgets only. This module never samples or alters indices."""
from .io import file_hash


def opus_budget(report, cfg):
    active = False
    tokens = 0
    sources = []
    for line in report.read_text().splitlines():
        if line.startswith("### "):
            active = line.strip() == "### Task Coverage Stats"
        if not active or not line.startswith("| **"):
            continue
        fields = line.split("|")
        name = fields[1].strip().strip("*")
        if not name.startswith("opus_da_en_repaired__"):
            continue
        value = int(fields[5].strip().split()[0].replace(",", ""))
        sources.append(name)
        tokens += value
    if not sources or tokens <= 0:
        raise ValueError("Report does not contain sampled repaired OPUS tokens; refusing to use stored tokens or raw OPUS")
    return {"basis": "sampled tokens, both directions", "baseline_tokens": tokens,
            "report": str(report.resolve()), "report_sha256": file_hash(report), "tasks": sources,
            "english_pair_cap": int(tokens * cfg["english_translation_fraction"]),
            "non_english_pair_cap": int(tokens * cfg["other_translation_fraction"]),
            "sampled": False}
