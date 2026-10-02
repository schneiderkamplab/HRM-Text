"""Source-specific Wikipedia paragraph adapters. No sentence-boundary recovery."""
import random
import re
from urllib.parse import urlsplit

from .io import digest
from .transform import transform

VERSION = "structure-preserving-v2"
WIKIMEDIA_REVISION = "b04c8d1ceb2f5cd4588862100d08de323dccfbaa"
EDITIONS = {"nb": "no", "nn": "nn", "sv": "sv"}


def intact_prose(text):
    """Reject observed cleaner holes; false negatives are preferable to repairs."""
    return not re.search(r"\S[^\S\n]{2,}\S|\b(?:er|\u00e4r|is)\s+[.,]|\b(?:er|\u00e4r|is)\s*\u00b0[CF]", text)


def wikipedia_quality(text, lang):
    if lang == "sv" and re.search(
            r"Terr\u00e4ngen runt|\u00c5rsmedeltemperaturen i trakten|Genomsnittlig \u00e5rsnederb\u00f6rd|Lsjbot|[Rr]obotskapad", text):
        raise ValueError("formulaic_bot_geography_or_bot_marker")


def check_url(url, lang):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc != EDITIONS[lang] + ".wikipedia.org"
            or not parsed.path.startswith("/wiki/") or parsed.fragment):
        raise ValueError("wrong_edition_url")


def prose(text):
    """Conservative eligibility, not a substitute for independent language audit."""
    return (len(text) >= 120 and len(text.split()) >= 20 and intact_prose(text)
            and text.rstrip('\"\u201d\u2019\')').endswith((".", "!", "?"))
            and not re.search(r"[\n\r\u2028\u2029]|\[\[|\]\]|\{\{|\}\}|<|>|\||\ufffd|\(\s*\)", text)
            and not re.match(r"^(?:[-*#;:\u2022]|\d+[.)]\s)", text)
            and sum(c.isalpha() for c in text) / len(text) > 0.6)


def wikimedia_blocks(row, lang):
    """Keep exact nonempty blank-line blocks and their source character spans.

    Single line breaks remain inside blocks and make them ineligible: cleaned
    section headings can share such a block with prose. Do not delete barriers.
    """
    check_url(row["url"], lang)
    if not str(row["id"]).isdigit() or not row.get("title"):
        raise ValueError("missing_article_identity")
    if row["title"] in {"Hovudside", "Hovedside", "Portal:Huvudsida"}:
        raise ValueError("main_page")
    text = row["text"]
    wikipedia_quality(text, lang)
    blocks = []
    for match in re.finditer(r"(?s)(?:[^\n]|\n(?![ \t]*\n))+", text):
        raw = match.group()
        stripped = raw.strip()
        if stripped:
            start = match.start() + len(raw) - len(raw.lstrip())
            blocks.append({"text": stripped, "source_span": [start, start + len(stripped)],
                           "index": len(blocks), "eligible": prose(stripped)})
    return blocks


def sparv_spacing(value):
    """Decode only Sparv's explicit whitespace escapes, never arbitrary escapes."""
    mapping = {"s": " ", "n": "\n", "t": "\t", "r": "\r"}
    if re.sub(r"\\[sntr]", "", value).strip():
        raise ValueError("unsupported_sparv_spacing")
    return re.sub(r"\\([sntr])", lambda m: mapping[m[1]], value)


def sparv_blocks(node):
    """Use actual XML paragraphs and Sparv's optional whitespace annotations."""
    check_url(node.attrib.get("url", ""), "sv")
    if not node.attrib.get("_id") or not node.attrib.get("permalink"):
        raise ValueError("missing_article_identity")
    paragraphs = list(node.iter("paragraph"))
    if not paragraphs:
        raise ValueError("no_xml_paragraphs")
    if list(node) != paragraphs:
        raise ValueError("unsupported_xml_paragraph_layout")
    wikipedia_quality(" ".join(node.itertext()), "sv")
    blocks = []
    for index, paragraph in enumerate(paragraphs):
        invalid = any(e.tag in {"header", "list", "table", "item"} for e in paragraph.iter())
        pieces = []
        tokens = list(paragraph.iter("token"))
        if not any("_tail" in t.attrib for t in tokens):
            invalid = True
        for i, token in enumerate(tokens):
            value = "".join(token.itertext()).strip()
            # Sparv omits empty attributes. Missing tail denotes adjacency,
            # but reject suspicious word-word adjacency instead of guessing.
            next_value = "".join(tokens[i + 1].itertext()).strip() if i + 1 < len(tokens) else ""
            if ("_tail" not in token.attrib and value and next_value
                    and value[-1].isalnum() and next_value[0].isalnum()):
                invalid = True
                break
            # Inline XML (e.g. subscript) is part of the token, not a new unit.
            pieces.append(value)
            try:
                pieces.append(sparv_spacing(token.attrib.get("_tail", "")))
            except ValueError:
                invalid = True
                break
        text = "".join(pieces).strip()
        blocks.append({"text": text, "index": index,
                       "eligible": not invalid and prose(text),
                       "xml_path": f"text/paragraph[{index + 1}]"})
    return blocks


def make_candidate(blocks, lang, provenance, renderer, seed=20260924):
    starts = [i for i in range(len(blocks) - 2)
              if all(p["eligible"] for p in blocks[i:i + 3])
              and len({p["text"] for p in blocks[i:i + 3]}) == 3
              and sum(len(p["text"]) for p in blocks[i:i + 3]) + 4 <= 6000]
    if not starts:
        raise ValueError("no_contiguous_paragraph_window")
    rng = random.Random(digest([seed, provenance["document_hash"]]))
    rng.shuffle(starts)
    # Rendering may reject one start but a shorter genuine window can still fit.
    for start in starts:
        selected = blocks[start:start + 3]
        text = "\n\n".join(p["text"] for p in selected)
        origin = dict(provenance, paragraph_selection={
            "version": VERSION, "paragraph_count": 3,
            "blocks": [{k: v for k, v in p.items() if k not in {"text", "eligible"}}
                       for p in selected], "max_chars": 6000})
        candidate = transform(text, lang, "paragraph-reordering", origin, seed)
        try:
            count = renderer.count(candidate["messages"])
        except ValueError as exc:
            if str(exc) != "rendered_context_does_not_fit":
                raise
            continue
        if count > 4096:
            continue
        candidate["rendered_tokens"] = count
        return candidate
    raise ValueError("rendered_context_does_not_fit")
