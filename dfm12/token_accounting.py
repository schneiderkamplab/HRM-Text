"""Read-only, streaming DFM12 token inventory; never constructs sampled indices."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import glob
import json
from pathlib import Path
import subprocess

import numpy as np

from .io import atomic, file_hash, load, write_json

try:
    import orjson
    decode = orjson.loads
except ImportError:
    decode = json.loads


def evidence(path):
    return {"path": str(path.resolve()), "sha256": file_hash(path)}


def inherited_budget(report, sampled_root):
    """Coverage is accumulated over epochs, unlike metadata.total_length."""
    tables = {"Category": {}, "Task": {}}
    section, header = None, None
    for line in report.read_text().splitlines():
        if line.startswith("### "):
            section = next((s for s in tables if line == f"### {s} Coverage Stats"), None)
            header = None
        if section and line.startswith("| Name |"):
            header = [v.strip() for v in line.strip("|").split("|")]
        if not section or not line.startswith("| **"):
            continue
        fields = [v.strip() for v in line.strip("|").split("|")]
        if header is None or len(fields) != len(header):
            raise ValueError("Malformed coverage table")
        name = fields[0].strip("*")
        if name in tables[section]:
            raise ValueError("Duplicate report task/category")
        values = {k: int(v.split()[0].replace(",", "")) for k, v in zip(header[1:], fields[1:])}
        if values["Cov Toks (%)"] != values["Cov IToks (%)"] + values["Cov RToks (%)"]:
            raise ValueError("Coverage token columns disagree")
        tables[section][name] = values
    global_stats = tables["Category"]["GLOBAL"]
    tasks = tables["Task"]
    for column in global_stats:
        if sum(t[column] for t in tasks.values()) != global_stats[column]:
            raise ValueError("Task table does not reconcile with GLOBAL")
    epochs = sorted(sampled_root.glob("epoch_*"))
    if not epochs or {p.name for p in epochs} != {f"epoch_{i}" for i in range(len(epochs))}:
        raise ValueError("Missing/noncontiguous inherited epochs")
    epoch_rows = {}
    for epoch in epochs:
        array = np.load(epoch / "inst_len.npy", mmap_mode="r", allow_pickle=False)
        epoch_rows[epoch.name] = len(array)
        del array
    if sum(epoch_rows.values()) != global_stats["Cov Rows (%)"]:
        raise ValueError("Report sampled rows do not match installed epoch headers")
    metadata = load(sampled_root / "metadata.json")
    global_mean = Fraction(global_stats["Cov Toks (%)"], len(epochs))
    if round(global_mean) != metadata["total_length"]:
        raise ValueError("Report sampled tokens do not match installed metadata")
    selected = {k: v for k, v in tasks.items() if k.startswith("opus_da_en_repaired__")}
    cumulative = sum(v["Cov Toks (%)"] for v in selected.values())
    if not selected or cumulative <= 0:
        raise ValueError("No sampled repaired EN-DA baseline")
    t = Fraction(cumulative, len(epochs))
    return {"basis": "mean sampled tokens per inherited epoch, both directions, prompt plus response",
            "report": evidence(report), "sampled_metadata": evidence(sampled_root / "metadata.json"),
            "epochs": len(epochs), "epoch_rows": epoch_rows,
            "global_cumulative_tokens": global_stats["Cov Toks (%)"],
            "global_mean_tokens": float(global_mean), "installed_mean_tokens_rounded": metadata["total_length"],
            "tasks": selected, "cumulative_tokens": cumulative,
            "T": {"numerator": t.numerator, "denominator": t.denominator, "tokens": float(t)},
            "english_pair_cap": cumulative // (len(epochs) * 4),
            "non_english_pair_cap": cumulative // (len(epochs) * 16),
            "rounding": "floor of exact epoch mean divided by 4 or 16; not floor(T) first",
            "sampled": False}


def state(path):
    s = path.stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)


def scan_candidates(paths, receipt, renderer=None, render_limit=0):
    """One row in memory. Translation rendered_tokens already includes both ways."""
    groups = defaultdict(lambda: {"records": 0, "conversations": 0, "tokens": 0,
                                  "min_record_tokens": None, "max_record_tokens": 0,
                                  "missing_token_records": 0, "rendered_probe_records": 0,
                                  "rendered_probe_tokens": 0})
    files = []
    for path in paths:
        before = state(path)
        h = hashlib.sha256()
        fallback_lines = 0
        with path.open("rb") as handle:
            for line in handle:
                h.update(line)
                if not line.strip():
                    continue
                try:
                    row = decode(line)
                except ValueError:
                    # Upstream metadata can contain Python JSON's NaN extension.
                    # Token fields below remain strictly positive integers.
                    row = json.loads(line)
                    fallback_lines += 1
                paired = "reverse_messages" in row
                lang = row.get("language", "unknown")
                if paired:
                    lang = "+".join(sorted((lang, row.get("reverse_language", "unknown"))))
                key = f"{lang}/{row.get('task', 'unknown')}"
                g = groups[key]
                g["records"] += 1
                g["conversations"] += 2 if paired else 1
                tokens = row.get("rendered_tokens")
                if tokens is None:
                    g["missing_token_records"] += 1
                    if renderer and g["rendered_probe_records"] < render_limit:
                        tokens = renderer.count(row["messages"])
                        if paired:
                            tokens += renderer.count(row["reverse_messages"])
                        g["rendered_probe_records"] += 1
                        g["rendered_probe_tokens"] += tokens
                    continue
                if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens <= 0:
                    raise ValueError(f"Invalid rendered_tokens: {path}")
                g["tokens"] += tokens
                g["min_record_tokens"] = min(g["min_record_tokens"] or tokens, tokens)
                g["max_record_tokens"] = max(g["max_record_tokens"], tokens)
        if state(path) != before:
            raise ValueError(f"Candidate changed during accounting: {path}")
        sha = h.hexdigest()
        expected = None
        if len(paths) == 1:
            expected = next((receipt[k] for k in ("sha256", "candidates_sha256", "candidate_sha256")
                             if isinstance(receipt.get(k), str)), None)
        for item in receipt.get("files", []):
            if isinstance(item, dict) and str(path).endswith(item.get("path", "\0")):
                expected = item.get("sha256")
        if expected and expected != sha:
            raise ValueError(f"Candidate receipt checksum mismatch: {path}")
        files.append({"path": str(path.resolve()), "sha256": sha, "bytes": before[2],
                      "receipt_checksum_verified": bool(expected), "stdlib_json_fallback_lines": fallback_lines})
    for g in groups.values():
        missing, n = g["missing_token_records"], g["rendered_probe_records"]
        g["method"] = "exact_recorded_rendered_tokens" if not missing else "unavailable"
        if missing and n:
            g["estimated_tokens"] = g["tokens"] + g["rendered_probe_tokens"] * missing / n
            g["method"] = "bounded_prefix_render_estimate" if n < missing else "exact_rendered"
            g["estimate_caveat"] = "Prefix probe of missing-token rows, not random; no confidence interval or corpus extrapolation."
            if n == missing:
                g["tokens"] += g["rendered_probe_tokens"]
        g["mean_record_tokens"] = g["tokens"] / g["records"] if not missing and g["records"] else None
    return {"groups": dict(groups), "files": files,
            "records": sum(g["records"] for g in groups.values()),
            "conversations": sum(g["conversations"] for g in groups.values()),
            "exact_tokens": sum(g["tokens"] for g in groups.values()) if all(
                g["method"].startswith("exact") for g in groups.values()) else None}


def tokenized_totals(directory, chunk_size=65536):
    """Sum index lengths in small mmap slices, never load tokens.npy payloads."""
    completion = directory / "completion.json"
    before = state(completion)
    receipt = load(completion)
    shards = sorted(directory.glob("*/metadata.json"))
    if receipt.get("files") is not None and receipt["files"] != len(shards):
        raise ValueError("Tokenized completion shard count mismatch")
    totals = {"examples": 0, "instruction_tokens": 0, "response_tokens": 0, "stored_tokens": 0}
    for metadata in shards:
        arrays = {name: np.load(metadata.parent / f"{name}.npy", mmap_mode="r", allow_pickle=False)
                  for name in ("inst_len", "resp_len", "tokens")}
        n = len(arrays["inst_len"])
        if len(arrays["resp_len"]) != n:
            raise ValueError("Tokenized index lengths disagree")
        totals["examples"] += n
        totals["stored_tokens"] += len(arrays["tokens"])
        for offset in range(0, n, chunk_size):
            for name, key in (("inst_len", "instruction_tokens"), ("resp_len", "response_tokens")):
                totals[key] += int(arrays[name][offset:offset + chunk_size].sum(dtype=np.uint64))
        del arrays
    if receipt.get("rows") is not None and receipt["rows"] != totals["examples"]:
        raise ValueError("Tokenized completion example count mismatch")
    if state(completion) != before:
        raise ValueError("Tokenization completion changed during accounting")
    totals["rendered_tokens"] = totals["instruction_tokens"] + totals["response_tokens"]
    return dict(totals, completion=evidence(completion), method="exact_tokenized_index_lengths",
                note="Stored tokens are not additive to rendered tokens; multi-turn contexts can reuse storage.")


def component_specs(root, manifest):
    for p in sorted((root / "candidates").glob("*/receipt.json")):
        if p.parent.name.endswith("-pilot"):
            continue
        tokenized = root / "tokenized_unaudited" / p.parent.name
        yield {"name": p.parent.name, "receipt": str(p), "files": [str(p.parent / "candidates.jsonl")],
               "inventory_class": "main_unaudited", "tokenized": str(tokenized)}
    yield from manifest["components"]


def account_component(spec, renderer, render_limit):
    result = {k: v for k, v in spec.items() if k not in {"files", "receipt", "tokenized"}}
    receipt_path = Path(spec["receipt"])
    if not receipt_path.exists():
        return dict(result, status="not_available", exact_tokens=None)
    before = state(receipt_path)
    receipt = load(receipt_path)
    result["receipt"] = evidence(receipt_path)
    if "pair" in receipt:
        result["pair"] = receipt["pair"]
    if spec.get("receipt_only"):
        return dict(result, status="receipt_only_no_candidate_inventory", evidence_status=receipt.get("status"),
                    source_statuses={k: v.get("status") for k, v in receipt.get("sources", {}).items()
                                     if isinstance(v, dict)}, exact_tokens=None, note=spec.get("note"))
    paths = [Path(p) for pattern in spec["files"] for p in sorted(glob.glob(pattern))]
    if not paths:
        return dict(result, status="no_candidate_files", exact_tokens=None)
    result.update(scan_candidates(paths, receipt, renderer, render_limit))
    if state(receipt_path) != before:
        raise ValueError("Receipt changed during accounting")
    tokenized = Path(spec.get("tokenized", "__no_tokenized_path__"))
    if (tokenized / "completion.json").exists():
        result["tokenized"] = tokenized_totals(tokenized)
        if result["exact_tokens"] is not None:
            result["tokenized"]["matches_candidate_tokens"] = result["tokenized"]["rendered_tokens"] == result["exact_tokens"]
    result["status"] = "unaudited_inventory_not_accepted"
    return result


def markdown(report):
    b = report["inherited_baseline"]
    lines = ["# DFM12 Token Accounting", "", "No final sampling. Candidate inventories are unaudited and may overlap.", "",
             f"Inherited T = {b['T']['tokens']:,.1f} tokens per epoch, EN-DA both directions.",
             f"Exact ratio: {b['cumulative_tokens']:,} / {b['epochs']} epochs.",
             f"English pair cap floor(T/4): **{b['english_pair_cap']:,}**.",
             f"Non-English pair cap floor(T/16): **{b['non_english_pair_cap']:,}**.", "",
             "Cov Toks in the source report is cumulative across epochs; stored/unique tokens are not T.", "",
             "## Available Components", "", "Alternatives are separate inventories, not automatically additive.", "",
             "| Component | Class | Records | Rendered tokens | Tokenized check |",
             "| --- | --- | ---: | ---: | --- |"]
    for c in report["components"]:
        tokens = c.get("exact_tokens")
        check = c.get("tokenized", {}).get("matches_candidate_tokens")
        lines.append(f"| {c['name']} | {c['inventory_class']} | {c.get('records', '-')} | "
                     f"{format(tokens, ',') if tokens is not None else c['status']} | {check if check is not None else '-'} |")
    lines += ["", "## Language and Task Distributions", "",
              "All values below are exact recorded rendered tokens unless the method says estimate/unavailable.", "",
              "| Component | Language/task | Records | Tokens | Within-component token share | Method |",
              "| --- | --- | ---: | ---: | ---: | --- |"]
    for c in report["components"]:
        for key, g in sorted(c.get("groups", {}).items()):
            share = f"{100*g['tokens']/c['exact_tokens']:.2f}%" if c.get("exact_tokens") else "-"
            amount = g.get("estimated_tokens", g["tokens"])
            lines.append(f"| {c['name']} | {key} | {g['records']:,} | {amount:,.0f} | {share} | {g['method']} |")
    lines += ["", "## Translation Pair Caps", "",
              "One row contains both directions; its rendered_tokens is counted once.", "",
              "| Pair | Available tokens | Cap | Available / cap |", "| --- | ---: | ---: | ---: |"]
    for p in report["translation_caps"]:
        lines.append(f"| {p['pair']} | {p['available_tokens']:,} | {p['cap']:,} | {p['available_fraction']:.4%} |")
    lines += ["", "## Limits", "",
              "No cross-component deduplication or final allocation is performed. No accepted-token claim is made.",
              "Pilots and superseded versions are excluded by the explicit input manifest, not counted as extra data.",
              "Structural/paragraph/sentence-block alternatives require parent merge decisions. Identity is not generated.",
              "Receipt-only holds/no-increment findings have no available-token estimate, not an assumed raw-corpus budget.",
              "Tokenized instruction/response sums validate available staging; stored tokens are a separate nonadditive measure.",
              "Report and input checksums, detailed groups, methods and errors are preserved in accounting.json.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/dfm12"))
    parser.add_argument("--sampled-root", type=Path, default=Path("data/sampled_dfm11"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("token_accounting_manifest.json"))
    parser.add_argument("--output", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--report", type=Path)
    source.add_argument("--fetch-inherited-report", action="store_true")
    parser.add_argument("--render-missing-limit", type=int, default=64)
    args = parser.parse_args()
    if args.render_missing_limit < 0:
        parser.error("Render limit must be nonnegative")
    args.output.mkdir(parents=True, exist_ok=False)
    report_path = args.output / "inherited-sample-report.log"
    if args.fetch_inherited_report:
        command = ["ssh", "-p", "6977", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                   "ucloud@ssh.cloud.sdu.dk", "cat /work/dfm/HRM-Text/logs/dfm11/sample_corrected.log"]
        with report_path.open("wb") as handle:
            subprocess.run(command, stdout=handle, check=True, timeout=60)
        write_json(args.output / "retrieval.json", {"command": command, "read_only": True})
    else:
        import shutil
        shutil.copyfile(args.report, report_path)
    baseline = inherited_budget(report_path, args.sampled_root)
    print("BASELINE", baseline["T"], baseline["english_pair_cap"], baseline["non_english_pair_cap"], flush=True)
    from .prepare import Renderer
    renderer = Renderer(load(args.sampled_root / "metadata.json")["tokenizer_info"], 4096)
    manifest = load(args.manifest)
    manifest_evidence = evidence(args.manifest)
    command_evidence = evidence(Path(__file__))
    write_json(args.output / "input-manifest.json", manifest)
    components = []
    for spec in component_specs(args.root, manifest):
        print("ACCOUNT", spec["name"], flush=True)
        try:
            item = account_component(spec, renderer, args.render_missing_limit)
        except (ValueError, OSError, KeyError) as exc:
            item = {"name": spec["name"], "inventory_class": spec["inventory_class"],
                    "status": "accounting_error", "error": str(exc), "exact_tokens": None}
        components.append(item)
    caps = []
    for c in components:
        if not c["name"].startswith("opus-") or c.get("exact_tokens") is None:
            continue
        pair = c.get("pair", "-".join(c["name"].removeprefix("opus-").split("-")[:2]))
        cap = baseline["english_pair_cap"] if "en" in pair.split("-") else baseline["non_english_pair_cap"]
        caps.append({"pair": pair, "component": c["name"], "available_tokens": c["exact_tokens"], "cap": cap,
                     "available_fraction": c["exact_tokens"] / cap,
                     "headroom_tokens": max(0, cap - c["exact_tokens"]),
                     "excess_tokens": max(0, c["exact_tokens"] - cap)})
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "final_sampling": False,
              "inherited_baseline": baseline, "manifest": manifest_evidence,
              "command_source": command_evidence, "components": components, "translation_caps": caps,
              "notes": manifest["notes"], "accepted_tokens": None}
    write_json(args.output / "accounting.json", report)
    with atomic(args.output / "accounting.md") as handle:
        handle.write(markdown(report))
    print("COMPLETE", args.output, "errors", sum(c["status"] == "accounting_error" for c in components), flush=True)


if __name__ == "__main__":
    main()
