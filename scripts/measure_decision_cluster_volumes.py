#!/usr/bin/env python3
"""Measure the DFM15 snapshot, reusing its verified per-range exposure census.

CPU/metadata only: never opens tokens.npy or reads index payloads. Source row
counts are physical index records, not distinct parent problems or decisions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

BASE = "data/category_preparation/dfm15-epoch0-source-domains-published-20261020"
NARRATIVE = "wiki/pages/decision-datasets"
# Ordered by workflow relevance, not measured efficacy. Easy means target
# recovery/mechanical construction candidates, never whole-source eligibility.
CLUSTERS = {
    "direct_labels": (1, "easy_candidate", "Intent/classification/NLI/MCQ; recover original labels and split gates"),
    "tool_actions": (2, "broad_candidate", "Tool/action state; schema checks conditional, semantic negatives unverified"),
    "instruction_constraints": (3, "broad_candidate", "IF constraints; easy subset requires retained executable checks"),
    "math": (4, "broad_candidate", "Math; equivalence checker and trusted answers required"),
    "code": (5, "broad_candidate", "Code; retained tests/execution required"),
    "reasoning_mixed": (6, "broad_candidate", "Unresolved reasoning domains; not assumed math or verified"),
    "qa_evidence": (7, "broad_candidate", "QA/evidence; source support and validated negatives required"),
    "preference": (8, "broad_candidate", "Preference-origin; chosen-only exports may have lost pair labels"),
    "acceptability": (9, "easy_candidate", "Language acceptability; retain original binary labels"),
    "gec": (10, "easy_candidate", "Correction pairs; identical/style edits and ambiguous repairs excluded later"),
    "paragraph_order": (11, "easy_candidate", "Source-order recovery; not unique discourse coherence"),
    "span_denoise": (12, "easy_candidate", "Corruption/span recovery; valid alternatives and traces required"),
    "summary": (13, "broad_candidate", "Summary support; reference alone does not validate negatives"),
    "translation": (14, "broad_candidate", "Parallel translation; equivalent alternatives remain valid"),
    "mixed_chat": (15, "residual", "Mixed chat/instruction/transforms; constituent routing not established"),
    "raw_unknown": (16, "residual", "Raw/prefix continuation or unidentified task; no bounded target established"),
}


def classify(source):
    """Narrative-informed precedence, with name-inferred matches exposed as such."""
    s = source.lower()
    rules = [
        ("paragraph_order", r"paragraph.*reorder|reorder.*paragraph", "conversion-recipes.md"),
        ("gec", r"(?:^|[_-])gec(?:[_-]|$)|dala.*correction|linguistic-quality", "middle-dala.md"),
        ("span_denoise", r"denois|span[_-]fill|error[_-]correct", "conversion-recipes.md"),
        ("acceptability", r"acceptability|(?:^|[_-])(?:dala|cola)(?:[_-]|$)", "middle-dala.md"),
        ("direct_labels", r"when2call|sentiment|classification|entailment|(?:^|[_-])(?:nli|snli|mnli|rte|qnli|sst2?|wic|ner|dane|intent|mcq|arc)(?:[_-]|$)|bool[_-]?q|hellaswag|winogrande|winograd|openbookqa|commonsenseqa|scienceqa|piqa|copa|scicite|skillspan|kompetencer|kaenguruen", "early-datasets.md"),
        ("preference", r"preferred|preference|helpsteer|simpo|(?:^|[_-])dpo(?:[_-]|$)", "conversion-recipes.md"),
        # No-Tools is general chat. Translated Dolci without explicit tool task
        # also stays mixed; a source name does not prove retained native calls.
        ("mixed_chat", r"no[_-]tools|dolci[_-]translated|koolbardi|fineinstructions|dyna-instruct__part", "early-datasets.md"),
        ("instruction_constraints", r"ifbench|if_sft|instruction.following|nemotron_instruction_reasoning_off", "early-datasets.md"),
        ("tool_actions", r"tool|agentic|terminal|function.call|(?:^|[_-])swe(?:[_-]|$)|repochat|search", "conversion-recipes.md"),
        ("code", r"code|coding|programming|leetcode|apps(?:__|_)", "conversion-recipes.md"),
        ("math", r"math|gsm|algebra|arithmetic|sudoku|amps|numina|kaeng", "latest-dfm15.md"),
        ("reasoning_mixed", r"reason|openthought|scibench|theorem", "latest-dfm15.md"),
        ("summary", r"summar|eur.lex.sum|wiki.cat.sum", "conversion-recipes.md"),
        ("translation", r"translation|machine.translation|mt.da.deepseek|(?:^|[_-])opus(?:[_-]|$)|elrc|emea|ecdc", "early-datasets.md"),
        ("qa_evidence", r"(?:^|[_-])qa(?:[_-]|$)|squad|coqa|quac|trivia.qa|natural.questions|wiki.dialog|wiki.instruct|laerebogen|lexdk|(?:^|[_-])dbc(?:[_-]|$)", "early-datasets.md"),
        ("raw_unknown", r"prefix.continu|raw|(?:danish_dynaword|danish-dynaword)__", "conversion-recipes.md"),
        ("mixed_chat", r"chat|instruct|flan|tulu|dolci|hermes|synth|transformations|sciriff|nemotron_multilingual|euroblocks|magpie|alpaca|text-", "early-datasets.md"),
    ]
    for cluster, pattern, page in rules:
        if re.search(pattern, s):
            return cluster, pattern, f"{NARRATIVE}/{page}"
    return "raw_unknown", "unmatched; no task inferred", f"{NARRATIVE}/coverage.md"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def index_rows(path):
    """Read a bounded NPY header, without mmap or reading any array payload."""
    with Path(path).open("rb") as f:
        version = np.lib.format.read_magic(f)
        if version == (1, 0):
            shape, _, dtype = np.lib.format.read_array_header_1_0(f)
        elif version == (2, 0):
            shape, _, dtype = np.lib.format.read_array_header_2_0(f)
        else:
            raise ValueError(f"Unsupported NPY version: {version}")
    if len(shape) != 1 or dtype.kind not in "iu":
        raise ValueError(f"Invalid index header: {path}")
    return shape[0]


def validate(manifest, receipt, manifest_hash):
    if receipt["status"] != "verified" or receipt["uncovered_rows"] != 0:
        raise ValueError("Receipt is not a complete verified census")
    if receipt["manifest_sha256"] != manifest_hash:
        raise ValueError("Receipt/manifest hash mismatch")
    if manifest["epoch"] != 0 or receipt["epoch"] != 0:
        raise ValueError("Expected epoch zero")
    if manifest["index_sha256"] != receipt["index_sha256"]:
        raise ValueError("Index hash mismatch")
    if len(manifest["ranges"]) != len(receipt["sources"]):
        raise ValueError("Range count mismatch")
    end = rows = tokens = 0
    for r, c in zip(manifest["ranges"], receipt["sources"]):
        if any(r[k] != c[k] for k in r) or r["start"] != end or r["end"] <= end:
            raise ValueError("Range identity/contiguity mismatch")
        end = r["end"]
        rows += c["rows"]
        tokens += c["token_exposure"]
    if (end, rows, tokens) != (manifest["stored_tokens"], receipt["rows"], receipt["token_exposure"]):
        raise ValueError("Totals do not reconcile")


def measure(root, read_headers=False):
    evidence = {}

    def read(relative):
        path = root / relative
        evidence[str(relative)] = digest(path)
        return json.loads(path.read_text())

    manifest = read(f"{BASE}/category-manifest.json")
    receipt = read(f"{BASE}/receipt.json")
    validate(manifest, receipt, evidence[f"{BASE}/category-manifest.json"])
    components_path = "data/dfm14/inheritance-reconciliation/component-inventory.json"
    components = {(p["group"], p["part"]): p for p in read(components_path)}
    repairs_path = "data/dfm15/native-reasoning-v2/repairs.json"
    repairs = {p["name"] + ":native": p for p in read(repairs_path)["parts"]}
    headers = iter(h for h in manifest["header_inventory"] if h["tokens"])
    records = []
    for i, (r, c) in enumerate(zip(manifest["ranges"], receipt["sources"])):
        stage, name = r["stage"], r["source"]
        n = None
        provenance = "unavailable"
        if stage in ("dfm11", "dfm14", "dfm15-addition"):
            h = next(headers)
            if h["tokens"] != r["end"] - r["start"]:
                raise ValueError("Header inventory order mismatch")
            path = Path(h["path"]).with_name("inst_start.npy")
            # Relocate producer paths when reproducing in another checkout.
            path = root / path.relative_to("/work/dfm/HRM-Text")
            if read_headers:
                try:
                    n = index_rows(path)
                    provenance = str(path.relative_to(root)) + "#npy-header-shape"
                except (OSError, ValueError) as error:
                    provenance = f"unavailable: {path}: {error}"
            else:
                provenance = "not_read_fast_metadata_mode: " + str(path.relative_to(root))
        elif stage in ("dfm12", "dfm13"):
            p = components[stage, name]
            if p["tokens"] != r["end"] - r["start"]:
                raise ValueError("Component token mismatch")
            n, provenance = p["rows"], components_path + "#" + stage + "/" + name
        elif stage == "native-repair":
            p = repairs[name]
            if p["new_tokens"] != r["end"] - r["start"]:
                raise ValueError("Repair token mismatch")
            n, provenance = p["rows"], repairs_path + "#" + name
        elif stage.startswith("math-conditioning"):
            suffix = "" if stage.endswith("v1") else "-v2"
            path = f"incoming/mimir-xl-20261015/data/dfm15/math-answer-conditioning{suffix}/preparation.json"
            n, provenance = read(path)["changed_unique"], path + "#changed_unique"
        cluster, rule, narrative = classify(name)
        records.append(dict(range_id=i, source=name, stage=stage, cluster=cluster,
            pool=CLUSTERS[cluster][1], reservoir_rows=n,
            reservoir_tokens=r["end"]-r["start"], epoch0_rows=c["rows"],
            epoch0_tokens=c["token_exposure"], start=r["start"], end=r["end"],
            row_provenance=provenance, classification_rule=rule, narrative=narrative,
            assignment_confidence="narrative_informed_identifier_triage_not_row_audit"))
        if i % 5000 == 0:
            print(f"Measured {i}/{len(manifest['ranges'])} ranges", flush=True)
    if next(headers, None) is not None:
        raise ValueError("Unused nonempty headers")
    for path in sorted((root / NARRATIVE).glob("*.md")):
        evidence[str(path.relative_to(root))] = digest(path)
    metrics = ("reservoir_rows", "reservoir_tokens", "epoch0_rows", "epoch0_tokens")

    def total(items):
        items = list(items)
        missing = sum(x["reservoir_rows"] is None for x in items)
        return {**{k: (None if k == "reservoir_rows" and missing else sum(x[k] or 0 for x in items)) for k in metrics},
                "known_reservoir_rows": sum(x["reservoir_rows"] or 0 for x in items),
                "ranges": len(items), "missing_row_count_ranges": sum(x["reservoir_rows"] is None for x in items)}

    clusters = [dict(cluster=k, rank=v[0], pool=v[1], caution=v[2],
                     **total(r for r in records if r["cluster"] == k)) for k, v in CLUSTERS.items()]
    pools = {p: total(r for r in records if r["pool"] == p)
             for p in ("easy_candidate", "broad_candidate", "residual")}
    exact = defaultdict(list)
    for r in records:
        exact[r["source"]].append(r)
    sources = [dict(source=s, cluster=rs[0]["cluster"], **total(rs),
                    range_ids=[r["range_id"] for r in rs]) for s, rs in sorted(exact.items())]
    return dict(schema="decision-cluster-volumes-v1", evidence_root=str(root),
        scope="DFM15 physical reservoir and published epoch0 census; NOT DFM1-15 historical union",
        ranking_basis="User-supplied typed-decisions and decision-index workflow priorities; no benchmark efficacy measurement or claim",
        historical_53B={
            "provenance": "Independent agent measurement documented in wiki/pages/decision-datasets/volume-method.md",
            "available_rows": 43324454, "available_tokens": 52812537488,
            "scope": "Six historical transformation families; latest positive available counts in DFM4 analytics",
            "caution": "Separate historical serialized variants, NOT unique parents or novel volume; never added to DFM15 because overlap is unresolved",
        },
        source_row_mode="source_headers_and_metadata" if read_headers else "metadata_only_missing_headers_explicit",
        definitions={
            "reservoir_rows": "Stored source index records (component metadata or NPY header); includes inactive/repaired/quarantined/format variants, NOT unique parent rows",
            "known_reservoir_rows": "Partial sum of available row counts; reservoir_rows is null whenever any contributing range lacks a count",
            "reservoir_tokens": "Disjoint manifest end-start token slots, counted once; includes superseded and zero-exposure ranges, NOT currently eligible conversion tokens",
            "epoch0_rows": "Sampled row occurrences from verified receipt, including repeats; NOT unique rows",
            "epoch0_tokens": "Sum inst_len+resp_len per sampled occurrence, before causal shift; repeats included",
            "easy_candidate": "Source-volume triage for existing labels or mechanical targets; actual eligible/convertible yield UNKNOWN",
            "broad_candidate": "Additional non-easy candidate source volume; tool/IF/checkable math/code subsets can move to easy only after validation",
            "residual": "Mixed/chat and raw/unknown kept outside candidate subtotals",
        }, limitations=[
            "No distinct-row estimate is inferred by dividing exposure by repeats; sampling caps and variants invalidate that shortcut.",
            "No cross-source, parent-document, repair, translation or template deduplication was performed.",
            "Native repair rows are index slots, including quarantined slots; original and repaired storage are not independent problems.",
            "Source names guide task triage with narrative exceptions; original labels, tests, pairs and checkers may not survive SFT conversion.",
            "BoolQ/MCQ/NLI explanation or generative variants are not guaranteed finite-label rows; ALL cluster suitability is inference, counts are source volumes not decision yields.",
            "Historical test/validation-named and excluded ranges remain in physical totals; no admission or conversion authorization is implied.",
            "Exposure reuses the dated published receipt; current epoch payloads are not rehashed or rescanned.",
            "Early historical sources absent from this reservoir are not measured; never sum DFM version inventories.",
        ], evidence_sha256=evidence, totals=total(records), pools=pools,
        broad_candidate_pool_including_easy=total(r for r in records if r["pool"] != "residual"),
        zero_exposure_reservoir=total(r for r in records if not r["epoch0_rows"]),
        shifted_epoch0_tokens=receipt["shifted_token_exposure"], clusters=clusters,
        sources=sources, ranges=records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", default="docs/reports/decision_dataset_volumes_20261021")
    parser.add_argument("--read-source-headers", action="store_true",
                        help="Opt into potentially slow per-source NPY header reads to fill missing reservoir rows")
    args = parser.parse_args()
    report = measure(args.root.resolve(), args.read_source_headers)
    output = args.root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    # One flat TSV: cluster summaries followed by exact-source summaries.
    fields = ["level", "cluster", "source", "rank", "pool", "reservoir_rows",
              "reservoir_tokens", "epoch0_rows", "epoch0_tokens", "ranges", "missing_row_count_ranges", "known_reservoir_rows"]
    with output.with_suffix(".tsv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for level, rows in (("cluster", report["clusters"]), ("source", report["sources"])):
            for row in rows:
                writer.writerow(dict(level=level, **row))
    print(json.dumps({"totals": report["totals"], "pools": report["pools"]}, indent=2))


if __name__ == "__main__":
    main()
