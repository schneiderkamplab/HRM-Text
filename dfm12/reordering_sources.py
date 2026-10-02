"""Pinned local source registry and exact paragraph spans for reordering work."""
from bisect import bisect_right
from collections import OrderedDict
from pathlib import Path
import re

from .catalog import selected_source
from .io import file_hash, load
from .structure_preserving import EDITIONS, WIKIMEDIA_REVISION, prose, wikimedia_blocks

GOVERNMENT = "data/dienst_publiek_en_communicatie/data.parquet"
DUTCH_FILES = {GOVERNMENT, "data/european_parliament/data.parquet",
               "data/naturalis/data.parquet", "data/pbl/data.parquet", "data/wikiwijs/data.parquet"}


def dutch_blocks(row, relative):
    if relative not in DUTCH_FILES:
        raise ValueError("unreviewed_dutch_source")
    text = row["text"]
    separator = r"\r\n|[\n\r\u2029]" if relative == GOVERNMENT else r"\r?\n[ \t]*\r?\n(?:[ \t]*\r?\n)*|\u2029"
    blocks, offset = [], 0
    for match in list(re.finditer(separator, text)) + [None]:
        end = match.start() if match else len(text)
        raw = text[offset:end]
        stripped = raw.strip()
        if stripped:
            start = offset + len(raw) - len(raw.lstrip())
            blocks.append({"text": stripped, "index": len(blocks),
                           "source_span": [start, start + len(stripped)], "eligible": prose(stripped)})
        offset = match.end() if match else end
    return blocks


def blocks_for(row, lang, relative):
    return dutch_blocks(row, relative) if lang == "nl" else wikimedia_blocks(row, lang)


def registry(native_root, shared_root):
    result = []
    if not (native_root / "complete.json").exists() or (native_root / "diagnostic-only.json").exists():
        raise ValueError("native_registry_not_verified_handoff")
    for lang, edition in EDITIONS.items():
        for entry in load(native_root / "candidates" / lang / "upstream-files.json"):
            relative = entry["path"]
            if not relative.endswith(".parquet"):
                continue
            path = (native_root / "downloads" / relative).resolve()
            if file_hash(path) != entry["lfs"]["oid"]:
                raise ValueError("upstream_checksum_mismatch")
            result.append({"language": lang, "repo": "wikimedia/wikipedia", "revision": WIKIMEDIA_REVISION,
                           "config": "20231101." + edition, "file": relative, "path": str(path),
                           "file_sha256": entry["lfs"]["oid"], "snapshot": "2023-11-01",
                           "boundary_mode": "wikimedia-explicit-blank-lines",
                           "license": "CC-BY-SA-3.0/GFDL per pinned card; retain publisher attribution/share-alike notices",
                           "language_evidence": f"{edition}.wikipedia.org edition; nowiki configured nb"})
    source = selected_source(shared_root, "dynaword-nl")
    if load(shared_root / "cpu-preparation.json")["dynaword-nl"]["download"] != "complete":
        raise ValueError("Dutch download incomplete")
    for relative in source["files"]:
        if relative not in DUTCH_FILES:
            continue
        path = (shared_root / "downloads/dynaword-nl" / relative).resolve()
        result.append({"language": "nl", "repo": source["repo"], "revision": source["revision"],
                       "file": relative, "path": str(path), "file_sha256": file_hash(path),
                       "boundary_mode": "reviewed-single-newline" if relative == GOVERNMENT else "explicit-blank-lines",
                       "license_basis": "owner authorization for DynaWord; preserve constituent notices",
                       "language_evidence": "explicit reviewed Dutch constituent",
                       "source_url_status": "upstream DynaWord row omits URL; no inferred URL"})
    return result


class SourceRows:
    """Small LRU of parquet row groups for exact integration replay."""
    def __init__(self, entries, cache_groups=4):
        self.entries = {(e["repo"], e["revision"], e["file"]): e for e in entries}
        self.files, self.cache = {}, OrderedDict()
        self.cache_groups = cache_groups

    def get(self, provenance):
        import pyarrow.parquet as pq
        key = tuple(provenance[k] for k in ("repo", "revision", "file"))
        if key not in self.entries:
            raise ValueError("unregistered_source")
        if key not in self.files:
            entry = self.entries[key]
            if file_hash(entry["path"]) != entry["file_sha256"]:
                raise ValueError("source_file_changed")
            f = pq.ParquetFile(entry["path"])
            offsets = [0]
            for i in range(f.num_row_groups):
                offsets.append(offsets[-1] + f.metadata.row_group(i).num_rows)
            self.files[key] = f, offsets
        f, offsets = self.files[key]
        ordinal = provenance["ordinal"]
        if not isinstance(ordinal, int) or ordinal < 0 or ordinal >= offsets[-1]:
            raise ValueError("invalid_source_ordinal")
        group = bisect_right(offsets, ordinal) - 1
        cache_key = key, group
        if cache_key not in self.cache:
            self.cache[cache_key] = f.read_row_group(group, use_threads=False).to_pylist()
            if len(self.cache) > self.cache_groups:
                self.cache.popitem(last=False)
        self.cache.move_to_end(cache_key)
        return self.cache[cache_key][ordinal - offsets[group]], self.entries[key]
