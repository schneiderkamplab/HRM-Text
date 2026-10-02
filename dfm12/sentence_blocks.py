"""Explicit synthetic multi-sentence blocks, never labeled native paragraphs."""
import copy
from functools import lru_cache
from pathlib import Path
import random
import re

from .io import digest, file_hash
from .structure_preserving import intact_prose

VERSION = "synthetic-sentence-blocks-v3"
MODELS = {"nb": "norwegian", "nn": "norwegian", "sv": "swedish", "nl": "dutch"}
ABBREVIATIONS = {
    "nb": {"dr", "prof", "f.eks", "bl.a", "dvs", "osv", "nr", "ca"},
    "nn": {"dr", "prof", "t.d", "m.a", "dvs", "osv", "nr", "ca", "o.l"},
    "sv": {"dr", "prof", "t.ex", "bl.a", "d.v.s", "osv", "nr", "ca"},
    "nl": {"dr", "prof", "bijv", "bv", "d.w.z", "enz", "nr", "ca"},
}
# These instructions say text blocks, not original paragraphs.
PROMPTS = {
    "nb": "Sett tekstblokkene i opprinnelig rekkefølge. Hver blokk inneholder flere sammenhengende setninger fra samme tekst. Skriv hele teksten uten nummerering, med en tom linje mellom blokkene.",
    "nn": "Set tekstblokkene i opphavleg rekkjefølgje. Kvar blokk inneheld fleire samanhengande setningar frå den same teksten. Skriv heile teksten utan nummerering, med ei tom linje mellom blokkene.",
    "sv": "Ordna textblocken i ursprunglig ordning. Varje block innehåller flera sammanhängande meningar från samma text. Skriv hela texten utan numrering, med en tom rad mellan blocken.",
    "nl": "Zet de tekstblokken in de oorspronkelijke volgorde. Elk blok bevat meerdere opeenvolgende zinnen uit dezelfde tekst. Geef de volledige tekst zonder nummering, met een lege regel tussen de blokken.",
}
QUOTE_MAP = str.maketrans({"\u00ab": '"', "\u00bb": '"', "\u201c": '"',
                          "\u201d": '"', "\u201e": '"'})


@lru_cache(maxsize=4)
def segmenter(lang):
    from nltk.tokenize.punkt import PunktSentenceTokenizer, PunktTokenizer
    params = copy.deepcopy(PunktTokenizer(MODELS[lang])._params)
    params.abbrev_types.update(ABBREVIATIONS[lang])
    return PunktSentenceTokenizer(params)


def segmenter_info(lang):
    import nltk
    directory = Path(str(nltk.data.find("tokenizers/punkt_tab/" + MODELS[lang])))
    return {"library": "nltk", "version": nltk.__version__, "algorithm": "Punkt",
            "model": MODELS[lang], "model_files": {p.name: file_hash(p) for p in sorted(directory.iterdir()) if p.is_file()},
            "abbreviation_overrides": sorted(ABBREVIATIONS[lang]),
            "quote_handling": "length-preserving quote normalization for segmentation only; original text retained",
            "variant_caveat": "Norwegian pretrained model is shared for NB/NN, not a separately trained NN model" if lang in {"nb", "nn"} else None}


def sentence_spans(text, lang):
    # The shadow has exactly the same code-point offsets as the original.
    return list(segmenter(lang).span_tokenize(text.translate(QUOTE_MAP)))


def complete_sentence(text, lang):
    shadow = text.translate(QUOTE_MAP)
    core = shadow.strip('"\'()[] ')
    if (len(text) < 35 or len(text) > 1200 or len(text.split()) < 6 or not intact_prose(text)
            or not core or not core[0].isupper() or not core.endswith((".", "!", "?"))
            or re.search(r"[\n\r\u2028\u2029]|\[|\]|\{|\}|<|>|\||\ufffd|https?://|\(\s*\)|\.\.\.|\u2026", text)
            or shadow.count('"') % 2 or shadow.count("(") != shadow.count(")")
            or sum(c.isalpha() for c in text) / len(text) < .6):
        return False
    final = core.split()[-1].lower().rstrip(".")
    return final not in ABBREVIATIONS[lang] and not (len(final) == 1 and final.isalpha())


def fallback_candidate(text, lang, provenance, renderer, runs=None, seed=20260924):
    """Select six adjacent complete sentences; preserve exact text inside pairs.

    Runs are exact character spans inside one source document. Native headings,
    line breaks and invalid sentences are barriers, not text to remove or bridge.
    """
    if runs is None:
        runs = [(m.start(), m.end()) for m in re.finditer(r"[^\n\r\u2028\u2029]+", text)]
    windows = []
    for run_start, run_end in runs:
        spans = [(a + run_start, b + run_start) for a, b in sentence_spans(text[run_start:run_end], lang)]
        valid = [complete_sentence(text[a:b], lang) for a, b in spans]
        for start in range(len(spans) - 5):
            selected = spans[start:start + 6]
            if not all(valid[start:start + 6]):
                continue
            if any(text[selected[i][1]:selected[i + 1][0]].strip() for i in range(5)):
                continue
            blocks = [text[selected[i][0]:selected[i + 1][1]] for i in (0, 2, 4)]
            if len(set(blocks)) < 3 or sum(map(len, blocks)) + 4 > 6000:
                continue
            # Punkt's context can change at a block end (quotes/abbreviations).
            # Require exactly the same two spans both inside and outside context.
            stable = True
            for i, block in zip((0, 2, 4), blocks):
                expected = [(a - selected[i][0], b - selected[i][0]) for a, b in selected[i:i + 2]]
                if sentence_spans(block, lang) != expected:
                    stable = False
                    break
            if not stable:
                continue
            windows.append((selected, blocks))
    if not windows:
        raise ValueError("no_six_contiguous_complete_sentences")
    rng = random.Random(digest([seed, provenance["document_hash"], VERSION]))
    rng.shuffle(windows)
    for spans, blocks in windows:
        target = "\n\n".join(blocks)
        key = digest([target, lang, "text-block-reordering", VERSION, seed])
        order = [0, 1, 2]
        random.Random(key).shuffle(order)
        if order == [0, 1, 2]:
            order = [1, 2, 0]
        instruction = PROMPTS[lang] + "\n\n" + "\n\n".join(f"[{i + 1}] {blocks[j]}" for i, j in enumerate(order))
        messages = [{"role": "user", "content": instruction}, {"role": "assistant", "content": target}]
        try:
            count = renderer.count(messages)
        except ValueError as exc:
            if str(exc) != "rendered_context_does_not_fit":
                raise
            continue
        if count > 4096:
            continue
        origin = dict(provenance, boundary_mode="synthetic-contiguous-sentence-pairs",
                      synthetic_boundaries=True, block_selection={
                          "version": VERSION, "sentence_spans": spans,
                          "block_spans": [[spans[i][0], spans[i + 1][1]] for i in (0, 2, 4)],
                          "sentences_per_block": [2, 2, 2], "block_count": 3,
                          "original_order_preserved_in_target": True})
        return {"id": key, "language": lang, "task": "text-block-reordering", "messages": messages,
                "rendered_tokens": count, "provenance": origin,
                "audit_context": {"original": target, "seed": seed,
                                  "boundary_warning": "Synthetic text blocks, not original paragraphs",
                                  "source_excerpt": text[spans[0][0]:spans[-1][1]]}}
    raise ValueError("rendered_context_does_not_fit")
