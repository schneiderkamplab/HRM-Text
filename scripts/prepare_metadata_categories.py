"""CPU-only, bounded-memory routing sidecar preparation.

Manifest ranges use exact tokens.npy offsets, not sampled row order. Category
0 is neutral/uncertain DOMAIN for a known source, 1 math/code/tool-agentic,
2 language/chat/summarization/translation. Missing provenance is NOT category 0.
Audit mode accepts partial candidate provenance; publication requires complete,
reviewed provenance bound to metadata and every sampled index file SHA256.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import numpy as np


FIELDS = ("inst_start", "inst_len", "resp_start", "resp_len")
CATEGORIES = {
    "0": "neutral_or_uncertain_domain",
    "1": "math_code_tool_agentic",
    "2": "language_chat_summarization_translation",
}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def signature(path):
    s = Path(path).stat()
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def write_json(path, value):
    with Path(path).open("x") as f:
        json.dump(value, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def validate_ranges(ranges, stored):
    ranges = sorted(ranges, key=lambda r: r["start"])
    for r in ranges:
        if any(type(r[k]) is not int for k in ("start", "end", "category")):
            raise ValueError("Range boundaries and category must be integers")
        if not (0 <= r["start"] < r["end"] <= stored and r["category"] in (0, 1, 2)):
            raise ValueError("Invalid range or category")
        if not r.get("source") or not r.get("rationale"):
            raise ValueError("Every range needs a source and explicit classification rationale")
    if any(a["end"] > b["start"] for a, b in zip(ranges, ranges[1:])):
        raise ValueError("Overlapping source ranges")
    return ranges


def assign(chunk, ranges, stored):
    """Return range index per row; -1 means missing/conflicting provenance."""
    for field in ("inst", "resp"):
        s, n = chunk[field + "_start"], chunk[field + "_len"]
        if np.any(s > stored) or np.any(n > stored - np.minimum(s, stored)):
            raise ValueError("Out-of-bounds token span")
    if np.any(chunk["resp_len"] == 0):
        raise ValueError("Empty response")
    if not ranges:
        return np.full(len(chunk["resp_len"]), -1, dtype=np.int64)
    starts = np.array([r["start"] for r in ranges], dtype=np.uint64)
    ends = np.array([r["end"] for r in ranges], dtype=np.uint64)
    owners = []
    for field in ("inst", "resp"):
        s, n = chunk[field + "_start"], chunk[field + "_len"]
        ix = np.searchsorted(starts, s, side="right") - 1
        safe = np.maximum(ix, 0)
        valid = (ix >= 0) & (s < ends[safe]) & (n <= ends[safe] - np.minimum(s, ends[safe]))
        owners.append(np.where(valid, ix, -1))
    inst, resp = owners
    return np.where((chunk["inst_len"] == 0) | (inst == resp), resp, -1)


def prepare(dataset, manifest_path, output, epoch=0, chunk_rows=250_000, publish=False):
    dataset, output, manifest_path = map(Path, (dataset, output, manifest_path))
    if chunk_rows < 1 or epoch < 0:
        raise ValueError("Invalid chunk size or epoch")
    if output.resolve().is_relative_to(dataset.resolve()):
        raise ValueError("Preparation output must be outside the sampled dataset")
    manifest = json.loads(manifest_path.read_text())
    folder = dataset / f"epoch_{epoch}"
    paths = {k: folder / (k + ".npy") for k in FIELDS}
    tracked = [*paths.values(), dataset / "tokens.npy", dataset / "metadata.json", manifest_path]
    evidence = manifest.get("evidence", [])
    for item in evidence:
        path = Path(item["path"])
        if sha256(path) != item["sha256"]:
            raise ValueError(f"Evidence hash mismatch: {path}")
        tracked.append(path)
    before = {str(p): signature(p) for p in tracked}
    tokens = np.load(dataset / "tokens.npy", mmap_mode="r", allow_pickle=False)
    if tokens.ndim != 1 or tokens.dtype.kind not in "iu":
        raise ValueError("Expected one-dimensional integer token store")
    stored = len(tokens)
    ranges = validate_ranges(manifest["ranges"], stored)
    arrays = {k: np.load(p, mmap_mode="r", allow_pickle=False) for k, p in paths.items()}
    nrows = len(arrays["resp_len"])
    if any(a.shape != (nrows,) or a.dtype.kind not in "iu" for a in arrays.values()):
        raise ValueError("Index arrays must be aligned one-dimensional integers")
    hashes = {}
    for k, a in arrays.items():
        if paths[k].stat().st_size != a.offset + a.nbytes:
            raise ValueError("Unexpected trailing or truncated index payload")
        h = hashlib.sha256()
        with paths[k].open("rb") as f:
            h.update(f.read(a.offset))
        hashes[k] = h
    blockers = []
    if manifest.get("provenance_status") != "verified" or not evidence:
        blockers.append("Source provenance is candidate-only, not verified")
    if manifest.get("metadata_sha256") != sha256(dataset / "metadata.json"):
        blockers.append("Metadata hash is not bound to this manifest")
    if manifest.get("epoch") != epoch or manifest.get("stored_tokens") != stored:
        blockers.append("Epoch/token-store shape is not bound to this manifest")
    expected = manifest.get("index_sha256", {})
    if set(expected) != set(FIELDS):
        blockers.append("Missing expected sampled-index SHA256 binding")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "category-manifest.json", manifest)
    temp = None
    dest = None
    counts = np.zeros(len(ranges), dtype=np.int64)
    exposure = np.zeros(len(ranges), dtype=np.int64)
    category_values = np.array([r["category"] for r in ranges], dtype=np.uint8)
    unknown_rows = unknown_tokens = total_tokens = 0
    try:
        if not blockers:
            fd, temp = tempfile.mkstemp(dir=output, suffix=".npy")
            os.close(fd)
            dest = np.lib.format.open_memmap(temp, mode="w+", dtype=np.uint8, shape=(nrows,))
        for off in range(0, nrows, chunk_rows):
            raw = {k: a[off:off + chunk_rows] for k, a in arrays.items()}
            for k, a in raw.items():
                hashes[k].update(a.tobytes())
                if a.dtype.kind == "i" and np.any(a < 0):
                    raise ValueError("Negative sampled indices")
            chunk = {k: a.astype(np.uint64, copy=False) for k, a in raw.items()}
            if np.any(chunk["inst_len"] > 4097) or np.any(chunk["resp_len"] > 4097):
                raise ValueError("Span exceeds pilot context")
            lengths = chunk["inst_len"] + chunk["resp_len"]
            if np.any(lengths > 4097):
                raise ValueError("Row exceeds pilot context")
            owner = assign(chunk, ranges, stored)
            unknown = owner < 0
            unknown_rows += int(unknown.sum())
            unknown_tokens += int(lengths[unknown].sum())
            total_tokens += int(lengths.sum())
            known = owner[~unknown]
            counts += np.bincount(known, minlength=len(ranges))
            # Per-chunk sums are < 4097 * chunk_rows and exactly representable
            # in float64; accumulate the resulting integers, not running floats.
            if chunk_rows * 4097 >= 2**53:
                raise ValueError("Chunk too large for exact exposure counting")
            exposure += np.bincount(known, weights=lengths[~unknown],
                                    minlength=len(ranges)).astype(np.int64)
            if dest is not None:
                dest[off:off + len(owner)][~unknown] = category_values[known]
        digest = {k: h.hexdigest() for k, h in hashes.items()}
        if expected and expected != digest:
            blockers.append("Sampled-index SHA256 mismatch")
        if unknown_rows:
            blockers.append(f"{unknown_rows} rows lack exact same-source span ownership")
        if any(signature(p) != before[str(p)] for p in tracked):
            raise ValueError("Input changed during preparation")
        sources = [dict(r, rows=int(counts[i]), token_exposure=int(exposure[i]))
                   for i, r in enumerate(ranges)]
        categories = {
            k: dict(name=v, rows=sum(s["rows"] for s in sources if s["category"] == int(k)),
                    token_exposure=sum(s["token_exposure"] for s in sources if s["category"] == int(k)))
            for k, v in CATEGORIES.items()
        }
        report = dict(status="blocked" if blockers else "verified", blockers=blockers,
                      dataset=str(dataset.resolve()), epoch=epoch, rows=nrows,
                      token_exposure=total_tokens, shifted_token_exposure=total_tokens-nrows,
                      uncovered_rows=unknown_rows, uncovered_token_exposure=unknown_tokens,
                      categories=categories, sources=sources, index_sha256=digest,
                      metadata_sha256=sha256(dataset / "metadata.json"),
                      manifest_sha256=sha256(manifest_path), input_signatures=before,
                      stored_tokens=stored, token_payload_hashed=False,
                      hash_scope="Full NPY index files and evidence; token payload not read",
                      published=False)
        if not blockers:
            dest.flush()
            del dest
            with open(temp, "rb") as f:
                os.fsync(f.fileno())
            staged = output / "category_id.npy"
            os.link(temp, staged)
            report["category_sha256"] = sha256(staged)
            if publish:
                if any(signature(p) != before[str(p)] for p in tracked):
                    raise ValueError("Input changed before publication")
                # link is atomic and refuses any existing resume-sensitive sidecar.
                os.link(staged, folder / "category_id.npy")
                fd = os.open(folder, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
                report["published"] = True
        write_json(output / "receipt.json", report)
        return report
    finally:
        if temp is not None:
            Path(temp).unlink(missing_ok=True)


def seed_transferred_math(dataset, manifest_path):
    """Preserve available historical evidence without claiming full provenance."""
    dataset = Path(dataset)
    work = dataset.parent / "dfm15/math-answer-conditioning-v2"
    evidence = [work / "source-ranges.json", work / "before.json",
                work / "preparation.json", dataset / "validated.json"]
    ranges = [
        dict(start=r["start"], end=r["end"], source=r["name"], category=1,
             rationale="Explicit math-source range from historical conditioning receipt")
        for r in json.loads(evidence[0].read_text())
    ]
    before = json.loads(evidence[1].read_text())
    after = json.loads(evidence[-1].read_text())
    ranges.append(dict(start=before["stored_tokens"], end=after["stored_tokens"],
                       source="math-answer-conditioning-v2:appended-variants", category=1,
                       rationale="Conditioning script appends only math variants; candidate until chain verified"))
    manifest = dict(
        schema="metadata-routing-ranges-v1", provenance_status="candidate",
        categories=CATEGORIES, epoch=0, stored_tokens=after["stored_tokens"],
        metadata_sha256=sha256(dataset / "metadata.json"), index_sha256={},
        evidence=[dict(path=str(p.resolve()), sha256=sha256(p)) for p in evidence],
        ranges=ranges,
        unresolved=[
            "Complete original source-token concatenation map bound to transferred token store",
            "DFM12/13/14 inheritance append ranges and reconciliation chain",
            "All native-reasoning replacements and DFM15 additions",
            "Explicit reviewed language/chat/summarization/translation source mapping",
            "Bind complete map to current index hashes after transformation verification",
        ],
    )
    write_json(manifest_path, manifest)


def source_category(name):
    """Domain policy on dataset identifiers only; never inspect example text."""
    name = name.lower()
    specialist = (
        r"(^|[-_])(math|mathagentic|gsm|gsm8k|gsm-symbolic|gsm_symbolic|"
        r"code|coding|tool|agentic|tinygsm|dmmath|ampsmathematica|"
        r"omnimath|numinamath|openmathinstruct2|kaenguruen)([-_.]|$)|"
        r"nemotron_(swe|terminal)|zai_deepdive|sudoku_extreme"
    )
    language = (
        r"(^|[-_])(translation|summarization|summarize|summary|rewrite|"
        r"denoising|paragraph-reordering|prefix-continuation|span-filling|"
        r"acceptability|correction|modernization|opus|europarl|parallel|"
        r"linguistic-quality|multiturn|chats|conversations)([-_.]|$)|"
        r"^(transformations-|posttrain_(coedit|asset)|dsldk_danish_|cor_sem__|"
        r"govreport_summarization|wiki_cat_sum|scientific_summaries|"
        r"machine_translation|synquid_mt_|danish_wildchat|"
        r"synquid_wildchat|elrc_medical|emea_medical|ecdc_public_health)"
    )
    if re.search(specialist, name):
        return 1, "source-domain-v1: explicit math/code/tool-agentic subdataset identifier"
    if re.search(language, name):
        return 2, "source-domain-v1: explicit language/chat/summary/translation task identifier"
    return 0, "source-domain-v1: mixed/general-purpose or uncertain subdataset; explicitly neutral"


def token_length(path):
    """Read only a NPY header; no token payload or tokenizer access."""
    a = np.load(path, mmap_mode="r", allow_pickle=False)
    if a.ndim != 1 or a.dtype.kind not in "iu":
        raise ValueError(f"Invalid token store: {path}")
    return len(a)


def validate_conditioning(mapping_path, ranges, start, end):
    """Prove old source ownership and contiguous appended variant offsets."""
    with np.load(mapping_path, allow_pickle=False) as mapping:
        old, new = mapping["old"], mapping["new"]
    if old.shape != new.shape or old.ndim != 2 or old.shape[1] != 4 or not len(old):
        raise ValueError("Invalid conditioning mapping shape")
    if old.dtype.kind not in "iu" or new.dtype.kind not in "iu" or np.any(old < 0) or np.any(new < 0):
        raise ValueError("Invalid conditioning mapping dtype/offsets")
    if np.any(new[:, 1] > 4097) or np.any(new[:, 3] > 4097):
        raise ValueError("Invalid conditioning lengths")
    if (new[0, 0] != start or new[-1, 2] + new[-1, 3] != end or
            np.any(new[:, 0] + new[:, 1] != new[:, 2]) or
            np.any(new[:-1, 2] + new[:-1, 3] != new[1:, 0]) or
            np.any(new[:, 3] == 0) or np.any(new[:, 1] + new[:, 3] > 4097)):
        raise ValueError("Conditioning append is not exact and contiguous")
    for off in range(0, len(old), 250_000):
        chunk = {k: old[off:off+250_000, i].astype(np.uint64, copy=False)
                 for i, k in enumerate(FIELDS)}
        owners = assign(chunk, ranges, start)
        categories = np.array([r["category"] for r in ranges])
        if np.any(owners < 0) or np.any(categories[owners] != 1):
            raise ValueError("Conditioning old rows do not have math source ownership")
    return len(old)


def recover_dfm15(dataset, manifest_path, root, index_receipt):
    """Recover exact token offsets using the documented production assembly."""
    dataset, root = Path(dataset).resolve(), Path(root).resolve()
    evidence, headers, stages, ranges = {}, [], [], []
    offset = 0

    def read(relative):
        path = Path(relative)
        if not path.is_absolute():
            path = root / path
        evidence[str(path)] = sha256(path)
        return json.loads(path.read_text())

    def add(name, length, stage, backing=None):
        nonlocal offset
        category, rationale = source_category(name)
        if length < 0:
            raise ValueError("Negative source length")
        if length:
            ranges.append(dict(start=offset, end=offset+length, source=name,
                               category=category, rationale=rationale, stage=stage))
        if backing is not None:
            headers.append(dict(path=str(backing), tokens=length, signature=signature(backing)))
        offset += length

    def boundary(name, expected):
        if offset != expected:
            raise ValueError(f"{name} offset mismatch: reconstructed {offset}, expected {expected}")
        stages.append(dict(stage=name, end=offset))
        print(f"{name}: exact boundary {offset}, {len(ranges)} ranges", flush=True)

    reconciliation = root / "data/dfm14/inheritance-reconciliation"
    copies = {v: read(reconciliation / f"sampled_dfm{v}/token-copy.json") for v in (12, 13, 14)}
    # This is also the explicit inventory algorithm in repair_reasoning.py.
    for directory in sorted((root / "data/tokenized_dfm11").iterdir()):
        if directory.is_symlink() and not directory.exists():
            raise ValueError(f"Missing source backing: {directory}")
        if directory.is_dir():
            path = directory / "tokens.npy"
            add(directory.name, token_length(path), "dfm11", path)
    boundary("dfm11", copies[12]["base_tokens"])
    inventory = read(reconciliation / "component-inventory.json")
    for version in (12, 13):
        parts = sorted((p for p in inventory if p["group"] == f"dfm{version}"),
                       key=lambda p: p["part"])
        if not parts or len({p["part"] for p in parts}) != len(parts):
            raise ValueError("Missing or duplicate component inventory")
        for part in parts:
            add(part["part"], part["tokens"], f"dfm{version}")
        boundary(f"dfm{version}", copies[version]["base_tokens"] + copies[version]["addition_tokens"])
        if version == 12:
            boundary("dfm13-base", copies[13]["base_tokens"])
    boundary("dfm14-base", copies[14]["base_tokens"])
    registry14 = read("config/dfm14_sources.json")
    parts14 = sorted((f'{entry["name"]}__part-{i:06d}', root / path)
                     for entry in registry14["additions"] for i, path in enumerate(entry["parts"]))
    for name, directory in parts14:
        path = directory / "tokens.npy"
        add(name, token_length(path), "dfm14", path)
    boundary("dfm14", copies[14]["base_tokens"] + copies[14]["addition_tokens"])
    repairs_root = root / "data/dfm15/native-reasoning-v2"
    repairs = read(repairs_root / "repairs.json")
    native_copy = read(repairs_root / "sampled_dfm15/token-copy.json")
    boundary("native-base", native_copy["base_tokens"])
    original = {r["source"]: r for r in ranges}
    for part in repairs["parts"]:
        r = original.get(part["name"])
        if r is None or (r["start"], r["end"]-r["start"]) != (part["offset"], part["tokens"]):
            raise ValueError(f'Repair original-offset mismatch: {part["name"]}')
        add(part["name"] + ":native", part["new_tokens"], "native-repair")
    boundary("native-repaired", native_copy["tokens"])
    registry15_path = dataset.parents[1] / "config/dfm15_sources.json"
    registry15 = read(registry15_path)
    final = read(dataset / "validated.json")
    if sha256(registry15_path) != final["registry_sha256"]:
        raise ValueError("Transferred DFM15 registry hash mismatch")
    for entry in registry15["additions"]:
        total = 0
        for i, part in enumerate(entry["parts"]):
            # Registry uses producer repo absolute paths, relocated locally.
            relative = Path(part["path"]).relative_to("/work/dfm/HRM-Text")
            path = root / relative / "tokens.npy"
            length = token_length(path)
            add(f'{entry["name"]}__part-{i:06d}', length, "dfm15-addition", path)
            total += length
        if total != entry["tokens"]:
            raise ValueError(f'DFM15 source token total mismatch: {entry["name"]}')
    conditioning = dataset.parent / "dfm15/math-answer-conditioning-v2"
    precondition = read(conditioning / "before.json")
    first_conditioning = dataset.parent / "dfm15/math-answer-conditioning"
    first_before = read(first_conditioning / "before.json")
    boundary("before-conditioning-v1", first_before["stored_tokens"])
    mapping_path = first_conditioning / "mapping.npz"
    evidence[str(mapping_path)] = sha256(mapping_path)
    n = validate_conditioning(mapping_path, ranges, offset, precondition["stored_tokens"])
    if n != read(first_conditioning / "preparation.json")["changed_unique"]:
        raise ValueError("Conditioning-v1 count mismatch")
    add("math-answer-conditioning-v1", precondition["stored_tokens"]-offset, "math-conditioning-v1")
    boundary("preconditioning", precondition["stored_tokens"])
    for anchor in read(conditioning / "source-ranges.json"):
        matches = [r for r in ranges if r["source"] == anchor["name"]]
        if not matches and anchor["name"] == "gsm-symbolic-en-train":
            matches = [r for r in ranges if r["source"].startswith(anchor["name"]+"__part-")]
        if not matches or (min(r["start"] for r in matches), max(r["end"] for r in matches)) != (
                anchor["start"], anchor["end"]):
            raise ValueError(f'Math receipt anchor mismatch: {anchor["name"]}')
    mapping_path = conditioning / "mapping.npz"
    evidence[str(mapping_path)] = sha256(mapping_path)
    n = validate_conditioning(mapping_path, ranges, offset, final["stored_tokens"])
    if n != read(conditioning / "preparation.json")["changed_unique"]:
        raise ValueError("Conditioning-v2 count mismatch")
    add("math-answer-conditioning-v2", final["stored_tokens"]-offset, "math-conditioning")
    boundary("final", token_length(dataset / "tokens.npy"))
    census = read(index_receipt)
    if census["dataset"] != str(dataset) or census["epoch"] != 0:
        raise ValueError("Index census belongs to another dataset/epoch")
    metadata = sha256(dataset / "metadata.json")
    if census["metadata_sha256"] != metadata:
        raise ValueError("Metadata changed since index census")
    for relative in ("data_io/sample_tokenized.py", "dfm14/reconcile_inheritance.py",
                     "dfm14/build.py", "dfm12/build_training.py", "dfm14/repair_reasoning.py",
                     "scripts/build_dfm15_full_sample.py", "scripts/condition_dfm15_math_answers.py"):
        path = root / relative
        evidence[str(path)] = sha256(path)
    for h in headers:
        if signature(h["path"]) != h["signature"]:
            raise ValueError("Source header changed during reconstruction")
    manifest = dict(schema="metadata-routing-ranges-v1", provenance_status="verified",
                    provenance_basis="documented_sorted_concatenation_and_append_receipts",
                    classification_policy="source-domain-v1; mixed/uncertain sources explicitly neutral",
                    categories=CATEGORIES, epoch=0, stored_tokens=offset,
                    metadata_sha256=metadata, index_sha256=census["index_sha256"],
                    evidence=[dict(path=p, sha256=h) for p, h in evidence.items()],
                    header_inventory=headers, assembly_boundaries=stages, ranges=ranges)
    validate_ranges(ranges, offset)
    write_json(manifest_path, manifest)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("dataset", type=Path)
    p.add_argument("manifest", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--epoch", type=int, default=0)
    p.add_argument("--chunk-rows", type=int, default=250_000)
    p.add_argument("--publish", action="store_true")
    p.add_argument("--seed-transferred-math", action="store_true",
                   help="Create a partial candidate manifest from transferred receipts; never publish it")
    p.add_argument("--recover-dfm15", action="store_true")
    p.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--index-receipt", type=Path)
    a = p.parse_args()
    if a.recover_dfm15:
        if a.seed_transferred_math or a.index_receipt is None or a.epoch != 0:
            p.error("Recovery requires --index-receipt, epoch 0, and no candidate seeding")
        recover_dfm15(a.dataset, a.manifest, a.repo_root, a.index_receipt)
    if a.seed_transferred_math:
        if a.publish:
            p.error("Candidate seeding cannot publish")
        seed_transferred_math(a.dataset, a.manifest)
    result = prepare(a.dataset, a.manifest, a.output, a.epoch, a.chunk_rows, a.publish)
    print(json.dumps({k: result[k] for k in ("status", "rows", "uncovered_rows", "blockers")}))
    raise SystemExit(2 if result["blockers"] else 0)


if __name__ == "__main__":
    main()
