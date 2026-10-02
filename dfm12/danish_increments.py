"""Read-only inherited-host comparison for the pinned Danish composite.

This runner proves unchanged reservoirs, not complete DFM11 decontamination.
Changed files fail closed: they need a broader inherited/held-out text index.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import unicodedata

from .io import atomic, file_hash, load, lock, write_json
from .records import chat_fingerprint

NAME = "dyna-instruct-da-increments"
DIRECT = {
    "wiki-instruct-da": "synquid_wiki_instruct_da__",
    "danish-verifiable-reasoning": "synquid_danish_verifiable_reasoning__",
    "ifbench-train": "synquid_ifbench_train__",
    "translation-100k": "synquid_translation_100k__",
}
LANGUAGES = {"dan": "da", "eng": "en", "fra": "fr", "deu": "de", "ita": "it"}

# Runs through SSH stdin without installing or changing anything on the source host.
REMOTE = r'''
import json, pathlib, sys
import numpy as np
root = pathlib.Path(sys.argv[1])
source = root / 'data/downloads/datasets/dfm_dyna_instruct'
union = root / 'data/tokenized_dfm11'
result = {'root': str(root), 'files': {}, 'tasks': {},
          'union_manifest': json.loads((union / 'union_manifest.json').read_text()),
          'sampled_metadata': json.loads((root / 'data/sampled_dfm11/metadata.json').read_text()),
          'policy': (root / 'data_io/prefix_config_dfm11.yaml').read_text()}
for path in sorted(source.glob('data/*/*.parquet')):
    rel = path.relative_to(source).as_posix()
    receipt = source / '.cache/huggingface/download' / (rel + '.metadata')
    lines = receipt.read_text().splitlines()
    result['files'][rel] = {'revision': lines[0], 'etag': lines[1],
        'download_timestamp': lines[2], 'size': path.stat().st_size,
        'mtime': int(path.stat().st_mtime)}
result['all_union_tasks'] = sorted(p.name for p in union.iterdir() if p.is_dir())
for path in sorted(union.iterdir()):
    if not path.name.startswith(('dfm_dyna_instruct__', 'synquid_')):
        continue
    if not (path / 'metadata.json').exists():
        continue
    result['tasks'][path.name] = {'resolved': str(path.resolve()),
        'metadata': json.loads((path / 'metadata.json').read_text()),
        'examples': int(np.load(path / 'inst_len.npy', mmap_mode='r').shape[0])}
print(json.dumps(result))
'''


def fingerprint(messages):
    """NFC + whitespace normalization; preserve case, roles, and turn order."""
    if not isinstance(messages, list) or not messages:
        raise ValueError("missing_messages")
    normalized = []
    for message in messages:
        if not isinstance(message, dict) or not all(isinstance(message.get(k), str)
                                                   for k in ("role", "content")):
            raise ValueError("nontext_message")
        normalized.append({k: unicodedata.normalize("NFC", message[k])
                           for k in ("role", "content")})
    return chat_fingerprint(normalized)


def language_label(value):
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list) or not values:
        return "und"
    return "+".join(sorted({LANGUAGES.get(v, v) for v in values if isinstance(v, str)})) or "und"


def policy_for(name, policy):
    return next((rule for rule in policy if name.startswith(rule["prefix"])), {})


def lineage(relative, source, evidence, policy):
    constituent = Path(relative).parts[1]
    old = evidence["files"].get(relative)
    if old is None or old["revision"] != source["revision"]:
        raise ValueError(f"Changed/missing inherited revision: {relative}; stage only, no inclusion")
    prefix = DIRECT.get(constituent, f"dfm_dyna_instruct__data__{constituent}")
    tasks = {name: item for name, item in evidence["tasks"].items()
             if name.startswith(prefix) and policy_for(name, policy).get("max_per_file") != 0
             and item["examples"] > 0}
    if not tasks:
        raise ValueError(f"No enabled inherited tokenized route for {relative}")
    return {"constituent": constituent, "inherited_file": old,
            "route": prefix, "tasks": tasks, "decision": "exclude_unchanged_inherited_reservoir"}


def run(args):
    import pyarrow as pa
    import pyarrow.parquet as pq
    import yaml
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = load(args.registry)["sources"][NAME]
    with lock(root / ".lock"):
        evidence_path = root / "inherited-evidence.json"
        if not evidence_path.exists():
            result = subprocess.run(["ssh", "-p", str(args.port), "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=20", args.host, args.remote_python, "-", args.remote_root],
                input=REMOTE, text=True, capture_output=True, check=True, timeout=180)
            write_json(evidence_path, json.loads(result.stdout))
        evidence = load(evidence_path)
        policy = yaml.safe_load(evidence["policy"])
        decisions = {rel: lineage(rel, source, evidence, policy) for rel in source["files"]}
        write_json(root / "lineage.json", {"source": source, "decisions": decisions,
            "license_authorization": "Owner authorizes all DynaInstruct licenses, 2026-09-24"})
        downloads = root / "downloads"
        downloads.mkdir(exist_ok=True)
        print("TRANSFER pinned inherited source snapshot", flush=True)
        subprocess.run(["rsync", "-a", "--partial", "--bwlimit=102400", "-e",
            f"ssh -p {args.port} -o BatchMode=yes -o ConnectTimeout=20",
            f"{args.host}:{args.remote_root}/data/downloads/datasets/dfm_dyna_instruct/",
            str(downloads) + "/"], check=True)
        info = load("data/sampled_dfm11/metadata.json")["tokenizer_info"]
        report = {"status": "indexing", "source": source, "constituents": {},
            "candidate_conversations": 0, "pretokenized_conversations": 0,
            "audit_status": "unaudited; no new material", "full_dfm11_dedup_complete": False,
            "coverage": "All pinned composite source reservoirs; NOT all DFM11 source text or exact sampled rows",
            "heldout_review": "No additions admitted. when2call is benchmark-derived and excluded independently. See review-evidence.json. No full held-out prompt/semantic scan performed.",
            "tokenizer_info": info,
            "tokenizer_sha256": file_hash(info["tokenizer_path"]),
            "template_sha256": file_hash(info["chat_template_path"])}
        db = sqlite3.connect(root / "fingerprints.sqlite")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA cache_size=-65536")
        db.execute("CREATE TABLE IF NOT EXISTS seen (hash TEXT PRIMARY KEY, constituent TEXT, ordinal INTEGER)")
        db.execute("CREATE TABLE IF NOT EXISTS completed (file TEXT PRIMARY KEY, result TEXT)")
        try:
            for relative, decision in decisions.items():
                cached = db.execute("SELECT result FROM completed WHERE file=?", (relative,)).fetchone()
                path = downloads / relative
                sha = file_hash(path)
                if sha != decision["inherited_file"]["etag"]:
                    raise ValueError(f"File does not match pinned LFS SHA256: {relative}")
                if cached:
                    report["constituents"][relative] = json.loads(cached[0])
                    continue
                print("INDEX", relative, flush=True)
                parquet = pq.ParquetFile(path)
                counts, languages = Counter(), Counter()
                columns = [c for c in ("messages", "language", "source") if c in parquet.schema_arrow.names]
                for batch in parquet.iter_batches(batch_size=256, columns=columns, use_threads=False):
                    for row in batch.to_pylist():
                        ordinal = counts["rows"]
                        counts["rows"] += 1
                        languages[language_label(row.get("language"))] += 1
                        try:
                            key = fingerprint(row.get("messages"))
                        except ValueError:
                            counts["unfingerprintable_excluded_by_file_identity"] += 1
                            continue
                        added = db.execute("INSERT OR IGNORE INTO seen VALUES (?,?,?)",
                            (key, decision["constituent"], ordinal)).rowcount
                        counts["unique_normalized" if added else "duplicate_normalized"] += 1
                    if counts["rows"] % 65536 == 0:
                        print(relative, dict(counts), flush=True)
                result = {"counts": dict(counts), "languages_upstream_not_audited": dict(languages),
                          "sha256": sha, "decision": decision["decision"]}
                db.execute("INSERT INTO completed VALUES (?,?)", (relative, json.dumps(result)))
                db.commit()
                report["constituents"][relative] = result
                write_json(root / "receipt.json", report)
                print("COMPLETE", relative, json.dumps(result), flush=True)
            report["unique_normalized_conversations"] = db.execute("SELECT count(*) FROM seen").fetchone()[0]
            report["input_rows"] = sum(x["counts"]["rows"] for x in report["constituents"].values())
            report["status"] = "complete_no_increments"
            # Deliberately do not invoke the tokenizer on an unchanged inherited corpus.
            with atomic(root / "candidates_unaudited.jsonl"):
                pass
            write_json(root / "receipt.json", report)
            print(json.dumps(report, indent=2), flush=True)
        finally:
            db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/dfm12/danish-increments"))
    parser.add_argument("--registry", type=Path, default=Path("data/dfm12/sources.lock.json"))
    parser.add_argument("--host", default="ucloud@ssh.cloud.sdu.dk")
    parser.add_argument("--port", type=int, default=6977)
    parser.add_argument("--remote-root", default="/work/dfm/HRM-Text")
    parser.add_argument("--remote-python", default="/home/ucloud/miniforge3/envs/hrm/bin/python")
    args = parser.parse_args()
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[variable] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    run(args)


if __name__ == "__main__":
    main()
