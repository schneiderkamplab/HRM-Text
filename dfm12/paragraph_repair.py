"""Opt-in paragraph-only repair; legacy transforms and audit IDs stay unchanged."""
import random
import re


VERSION = "paragraph-repair-v1"
SINGLE_LINE_SOURCE = ("dynaword-nl", "data/dienst_publiek_en_communicatie/data.parquet")


def paragraph_window(text, seed, single_lines=False, max_chars=6000):
    """Choose three contiguous complete prose blocks, never synthesize boundaries.

    Single newlines are opt-in for reviewed web prose, not PDF line wrapping.
    Invalid blocks remain barriers: removing headings must not join sections.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    separator = r"\n+|\u2029" if single_lines else r"\n[ \t]*\n(?:[ \t]*\n)*|\u2029"
    parts = [p.strip() for p in re.split(separator, text) if p.strip()]
    valid = [len(p) >= 80 and len(p.split()) >= 10
             and p.rstrip('\"\u201d\u2019\')').endswith((".", "!", "?"))
             and not re.match(r"^(?:[-*#\u2022]|\d+[.)]\s)", p)
             and (not single_lines or "\u2028" not in p)
             for p in parts]
    starts = [i for i in range(len(parts) - 2)
              if all(valid[i:i + 3]) and len(set(parts[i:i + 3])) == 3
              and sum(map(len, parts[i:i + 3])) + 4 <= max_chars]
    if not starts:
        raise ValueError("no_contiguous_paragraph_window")
    start = random.Random(seed).choice(starts)
    return "\n\n".join(parts[start:start + 3]), {
        "version": VERSION, "boundary_mode": "reviewed-single-newline" if single_lines else "blankline-or-u2029",
        "paragraph_start": start, "paragraph_count": 3, "max_chars": max_chars,
    }
