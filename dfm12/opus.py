"""Direct OPUS pairs only; corpus-version licenses are explicit approvals."""
from collections import Counter
from itertools import combinations, zip_longest
import io
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.parse
import urllib.request
import zipfile

from .io import atomic, digest, file_hash, load, lock, Seen, write_json

LICENSES = {"public-domain", "cc0-1.0"} | {
    f"cc-by{suffix}-{version}" for suffix in ("", "-sa") for version in ("1.0", "2.0", "2.5", "3.0", "4.0")}


def pairs(cfg):
    if "opus_pairs" in cfg:
        result = set()
        for pair in cfg["opus_pairs"]:
            a, b = pair
            if a == b or a not in cfg["languages"] or b not in cfg["languages"]:
                raise ValueError("Invalid explicit OPUS pair")
            result.add(tuple(sorted((a, b))))
        return sorted(result)
    result = {tuple(sorted(("en", lang))) for lang in cfg["english_pairs"]}
    result.update(combinations(sorted(["da"] + cfg["new_languages"]), 2))
    return sorted(result)


def discover(root, cfg):
    destination = root / "opus" / "inventory.json"
    with lock(root / "opus" / ".inventory.lock"):
        found = load(destination)["pairs"] if destination.exists() else {}
        for a, b in pairs(cfg):
            pair = f"{a}-{b}"
            if pair in found and not found[pair].get("error"):
                continue
            codes = cfg.get("opus_codes", {})
            query = urllib.parse.urlencode(dict(source=codes.get(a, a), target=codes.get(b, b), preprocessing="moses", version="latest"))
            url = "https://opus.nlpl.eu/opusapi/?" + query
            try:
                with urllib.request.urlopen(url, timeout=60) as handle:
                    corpora = json.load(handle)["corpora"]
                # Tatoeba's current Moses release explicitly includes CC BY 2.0 FR.
                for corpus in corpora:
                    corpus["status"] = "license_review"
                    if corpus["corpus"] == "Tatoeba":
                        corpus.update(status="approved", license="cc-by-2.0",
                                      license_evidence="https://tatoeba.org/en/terms_of_use",
                                      require_readme_license="creativecommons.org/licenses/by/2.0/fr/")
                found[f"{a}-{b}"] = {"corpora": corpora, "api": url}
            except Exception as exc:
                found[f"{a}-{b}"] = {"corpora": [], "error": str(exc), "api": url}
            print(f"OPUS {a}-{b}: {len(found[f'{a}-{b}']['corpora'])} corpora", flush=True)
            write_json(destination, {"pairs": found, "policy": "direct-only; no pivot or synthetic shortfall filling"})
        result = {"pairs": found, "policy": "direct-only; no pivot or synthetic shortfall filling"}
        write_json(destination, result)
        return result


def validate_license(entry):
    if entry.get("status") != "approved" or entry.get("license") not in LICENSES or not entry.get("license_evidence"):
        raise ValueError("Corpus-version license is not approved")
    url = urllib.parse.urlparse(entry["url"])
    if url.scheme != "https" or url.hostname != "object.pouta.csc.fi":
        raise ValueError("Unexpected OPUS download host")


def prepare_pair(root, pair, cfg, renderer):
    if tuple(pair.split("-")) not in pairs(cfg):
        raise ValueError("Pair not in approved mesh")
    entries = load(root / "opus" / "inventory.json")["pairs"][pair]["corpora"]
    approved = [e for e in entries if e.get("status") == "approved"]
    if not approved:
        raise ValueError("No approved direct corpus for this pair; report shortfall")
    directory = root / "candidates" / ("opus-" + pair)
    directory.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    receipts = []
    with lock(directory / ".lock"), tempfile.TemporaryDirectory(dir=directory) as tmp:
        seen = Seen(Path(tmp) / "dedup.sqlite")
        try:
            with atomic(directory / "candidates.jsonl") as output:
                for entry in approved:
                    validate_license(entry)
                    archive = root / "opus" / "downloads" / (digest(entry["url"]) + ".zip")
                    archive.parent.mkdir(parents=True, exist_ok=True)
                    if not archive.exists():
                        fd, path = tempfile.mkstemp(dir=archive.parent)
                        try:
                            with os.fdopen(fd, "wb") as handle, urllib.request.urlopen(entry["url"], timeout=120) as remote:
                                for block in iter(lambda: remote.read(4 * 1024 * 1024), b""):
                                    handle.write(block)
                            os.replace(path, archive)
                        finally:
                            if os.path.exists(path):
                                os.unlink(path)
                    a, b = entry["source"], entry["target"]
                    requested = pair.split("-")
                    inverse = {cfg.get("opus_codes", {}).get(lang, lang): lang for lang in requested}
                    if {a, b} != set(inverse):
                        raise ValueError("OPUS response languages do not match requested pair")
                    with zipfile.ZipFile(archive) as z:
                        readme = z.read("README").decode("utf-8", errors="strict")
                        expected = entry.get("require_readme_license")
                        if expected and expected not in readme:
                            raise ValueError("OPUS release license does not match evidence")
                        # Retain upstream attribution; never extract arbitrary archive paths.
                        attribution = root / "opus" / "attribution" / digest(entry["url"])
                        write_json(attribution.with_suffix(".json"), {"entry": entry, "README": readme,
                                   "LICENSE": z.read("LICENSE").decode() if "LICENSE" in z.namelist() else ""})
                        names_a = [n for n in z.namelist() if n.endswith("." + a)]
                        names_b = [n for n in z.namelist() if n.endswith("." + b)]
                        if len(names_a) != 1 or len(names_b) != 1:
                            raise ValueError("Ambiguous Moses members")
                        with z.open(names_a[0]) as fa, z.open(names_b[0]) as fb:
                            lines_a, lines_b = io.TextIOWrapper(fa, encoding="utf-8"), io.TextIOWrapper(fb, encoding="utf-8")
                            for index, (ta, tb) in enumerate(zip_longest(lines_a, lines_b)):
                                if ta is None or tb is None:
                                    raise ValueError("Mismatched Moses line counts")
                                counts["pairs_read"] += 1
                                ta, tb = " ".join(ta.split()), " ".join(tb.split())
                                if not ta or not tb or max(len(ta), len(tb)) > 12000 or max(len(ta), len(tb)) > 5 * min(len(ta), len(tb)):
                                    counts["structural_rejected"] += 1
                                    continue
                                lang_a, lang_b = inverse[a], inverse[b]
                                texts = {lang_a: ta, lang_b: tb}
                                key = digest(texts)
                                if not seen.add(key):
                                    counts["duplicate_pairs"] += 1
                                    continue
                                conversations = []
                                for src, dst in ((lang_a, lang_b), (lang_b, lang_a)):
                                    prompt = f"Translate from {cfg['languages'][src]} into {cfg['languages'][dst]}. Output only the translation.\n\n{texts[src]}"
                                    conversations.append([{"role": "user", "content": prompt}, {"role": "assistant", "content": texts[dst]}])
                                try:
                                    tokens = sum(renderer.count(m) for m in conversations)
                                except ValueError:
                                    counts["overlength"] += 1
                                    continue
                                record = {"id": key, "messages": conversations[0], "reverse_messages": conversations[1],
                                          "language": lang_b, "reverse_language": lang_a, "task": "translation", "pair": pair,
                                          "rendered_tokens": tokens, "provenance": {"corpus": entry["corpus"],
                                          "version": entry["version"], "url": entry["url"], "line": index,
                                          "license": entry["license"], "attribution": str(attribution.with_suffix('.json'))},
                                          "audit_context": {"languages": {l: cfg["languages"][l] for l in requested},
                                              "instruction": "Both directions must be correct. Reject ambiguous or wrong language variants. pt_pt means European Portuguese, NOT generic Portuguese or Brazilian Portuguese."}}
                                output.write(json.dumps(record, ensure_ascii=False) + "\n")
                                counts["candidate_pairs"] += 1
                    receipts.append({"entry": entry, "archive_sha256": file_hash(archive)})
        finally:
            seen.close()
        report = {"pair": pair, "counts": dict(counts), "archives": receipts,
                  "tokenizer_info": renderer.info, "sha256": file_hash(directory / "candidates.jsonl"),
                  "future_sample_cap_fraction": cfg["english_translation_fraction"] if "en" in pair.split("-") else cfg["other_translation_fraction"]}
        write_json(directory / "receipt.json", report)
    return report
