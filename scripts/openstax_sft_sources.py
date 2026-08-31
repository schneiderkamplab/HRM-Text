#!/usr/bin/env python3
"""Materialize pinned OpenStax sources and prepare grounded Mimir SFT requests."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config/openstax_mimir_sft.json"
DEFAULT_INVENTORY = ROOT / "docs/openstax_cc_by_inventory.csv"
DEFAULT_DATA_ROOT = ROOT / "data/mimir_openstax_sft"
DEFAULT_VERIFIED_PASSAGES = ROOT / "data/mimir_grounded_500k/openstax_cc_by/passages.jsonl"
CC_BY_URL = "https://creativecommons.org/licenses/by/4.0/"

SKIP_MODULE_TITLES = re.compile(
    r"^(preface|index|answer key|references|acknowledg(?:e)?ments|about the authors?)$",
    re.IGNORECASE,
)
BLOCK_TAGS = {"title", "para", "item", "quote", "statement", "equation", "note", "caption"}
DROP_TAGS = {"media", "figure", "iframe", "video", "audio"}
RESTRICTED_TEXT_MARKERS = re.compile(
    r"(?:included|used|reprinted|adapted) with (?:the )?permission|all rights reserved",
    re.IGNORECASE,
)

TASK_PROMPTS = {
    "concept_explanation": (
        "Create one substantive learner question about a central concept in the source and a precise, "
        "self-contained teaching answer. Explain mechanism or causality where relevant."
    ),
    "grounded_application": (
        "Create one realistic application or case question that requires applying the source concept, then "
        "give a rigorous answer that explicitly connects the facts to the governing principle."
    ),
    "misconception_correction": (
        "Create one plausible but nontrivial misconception about the source topic as the learner's question. "
        "Correct it respectfully, explain why it fails, and state the accurate principle."
    ),
    "worked_problem": (
        "Create one novel worked problem grounded in the source. Use fresh names and numbers when applicable. "
        "Show a coherent derivation or decision process and make the final result unambiguous."
    ),
    "comparison_and_transfer": (
        "Create one question that compares two related ideas in the source or transfers one idea to a new "
        "setting. Answer with both the important distinction and the shared principle."
    ),
}


def stable_hex(*parts: object, size: int = 16) -> str:
    return hashlib.blake2b("\0".join(map(str, parts)).encode(), digest_size=size).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    temporary.replace(path)
    return count


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc


def load_policy(path: Path) -> dict[str, Any]:
    policy = json.loads(path.read_text())
    weights = policy["task_families"]
    if not math.isclose(sum(weights.values()), 1.0, rel_tol=0, abs_tol=1e-9):
        raise ValueError("task_families weights must sum to 1")
    return policy


def selected_slugs(policy: dict[str, Any]) -> dict[str, tuple[str, str]]:
    selected: dict[str, tuple[str, str]] = {}
    for category, slugs in policy["primary"].items():
        for slug in slugs:
            if slug in selected:
                raise ValueError(f"duplicate selected slug: {slug}")
            selected[slug] = ("primary", category)
    for slug in policy["supplemental"]:
        if slug in selected:
            raise ValueError(f"duplicate selected slug: {slug}")
        selected[slug] = ("supplemental", "supplemental")
    return selected


def load_manifest(policy_path: Path, inventory_path: Path) -> list[dict[str, Any]]:
    policy = load_policy(policy_path)
    selected = selected_slugs(policy)
    with inventory_path.open(newline="", encoding="utf-8") as handle:
        inventory = {row["slug"]: row for row in csv.DictReader(handle)}
    missing = sorted(set(selected) - set(inventory))
    if missing:
        raise ValueError(f"selected slugs absent from inventory: {missing}")
    rows = []
    for slug, (tier, category) in selected.items():
        row = dict(inventory[slug])
        if row["language"] != "en" or row["status"] != "ready":
            raise ValueError(f"selected row is not ready English content: {slug}")
        row.update({"tier": tier, "category": category})
        rows.append(row)
    return sorted(rows, key=lambda row: row["slug"])


def git_source(row: dict[str, Any]) -> tuple[str, str] | None:
    if row["artifact_type"] != "official_git_snapshot":
        return None
    parsed = urlparse(row["retrieval_url"])
    match = re.fullmatch(r"/(openstax/[^/]+)/archive/[0-9a-f]{40}\.tar\.gz", parsed.path)
    if not match:
        raise ValueError(f"unexpected Git retrieval URL: {row['retrieval_url']}")
    return match.group(1), row["immutable_ref"]


def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, **kwargs)


def safe_extract_stream(process: subprocess.Popen[bytes], destination: Path) -> None:
    assert process.stdout is not None
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
        for member in archive:
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
                raise ValueError(f"unsafe archive member: {member.name}")
            archive.extract(member, destination, filter="data")
    # Streaming tar readers stop at the end marker. Drain Git's trailing tar
    # padding so a large archive cannot block while we wait on stderr/exit.
    process.stdout.read()
    stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
    if process.wait() != 0:
        raise RuntimeError(f"git archive failed: {stderr}")


def materialize_repo(repo: str, commit: str, data_root: Path) -> dict[str, Any]:
    repo_name = repo.split("/")[-1]
    bare = data_root / "git" / f"{repo_name}.git"
    snapshot = data_root / "snapshots" / repo_name / commit
    marker = snapshot / "snapshot.json"
    if marker.exists():
        return json.loads(marker.read_text())
    bare.parent.mkdir(parents=True, exist_ok=True)
    if not bare.exists():
        run(["git", "clone", "--bare", "--filter=blob:none", f"https://github.com/{repo}.git", str(bare)])
    try:
        run(["git", f"--git-dir={bare}", "cat-file", "-e", f"{commit}^{{commit}}"])
    except subprocess.CalledProcessError:
        run(["git", f"--git-dir={bare}", "fetch", "--filter=blob:none", "origin", commit])
    resolved = run(
        ["git", f"--git-dir={bare}", "rev-parse", f"{commit}^{{commit}}"], capture_output=True
    ).stdout.strip()
    if resolved != commit:
        raise ValueError(f"commit mismatch for {repo}: wanted {commit}, got {resolved}")
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{repo_name}.", dir=snapshot.parent) as temporary:
        temporary_path = Path(temporary)
        process = subprocess.Popen(
            ["git", f"--git-dir={bare}", "archive", "--format=tar", commit, "collections", "modules"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        safe_extract_stream(process, temporary_path)
        result = {
            "repo": repo,
            "commit": commit,
            "source_url": f"https://github.com/{repo}/tree/{commit}",
            "collections": len(list((temporary_path / "collections").glob("*.collection.xml"))),
            "modules": len(list((temporary_path / "modules").glob("*/index.cnxml"))),
        }
        atomic_json(temporary_path / "snapshot.json", result)
        os.replace(temporary_path, snapshot)
    return result


def cmd_manifest(args: argparse.Namespace) -> None:
    rows = load_manifest(args.config, args.inventory)
    counts = Counter((row["tier"], row["artifact_type"]) for row in rows)
    result = {"selected": len(rows), "counts": {"/".join(key): value for key, value in counts.items()}, "rows": rows}
    atomic_json(args.data_root / "source_manifest.json", result)
    print(json.dumps({"selected": len(rows), "counts": result["counts"]}, indent=2))


def cmd_materialize(args: argparse.Namespace) -> None:
    rows = load_manifest(args.config, args.inventory)
    sources = sorted({git_source(row) for row in rows if git_source(row) is not None})
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = {
            executor.submit(materialize_repo, repo, commit, args.data_root / "sources"): (repo, commit)
            for repo, commit in sources
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"materialized {result['repo']}@{result['commit'][:12]} modules={result['modules']}", flush=True)
    unsupported = [row["slug"] for row in rows if git_source(row) is None]
    summary = {"git_snapshots": sorted(results, key=lambda row: row["repo"]), "pending_non_git": unsupported}
    atomic_json(args.data_root / "materialize_summary.json", summary)
    print(json.dumps({"repositories": len(results), "pending_non_git": unsupported}, indent=2))


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def text_from_cnxml(element: ET.Element) -> str:
    parts: list[str] = []

    def visit(node: ET.Element) -> None:
        tag = local_name(node.tag)
        if tag in DROP_TAGS:
            return
        if tag in BLOCK_TAGS:
            parts.append("\n")
            if tag == "item":
                parts.append("- ")
        if node.text:
            parts.append(node.text)
        for child in node:
            visit(child)
            if child.tail:
                parts.append(child.tail)
        if tag in BLOCK_TAGS:
            parts.append("\n")

    visit(element)
    text = "".join(parts).replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def collection_modules(collection: ET.Element) -> list[tuple[str, list[str]]]:
    modules: list[tuple[str, list[str]]] = []

    def walk(node: ET.Element, headings: list[str]) -> None:
        for child in node:
            tag = local_name(child.tag)
            if tag == "subcollection":
                title = next((text_from_cnxml(x) for x in child if local_name(x.tag) == "title"), "")
                walk(child, headings + ([title] if title else []))
            elif tag == "module":
                document = child.attrib.get("document")
                if document:
                    modules.append((document, headings))
            else:
                walk(child, headings)

    walk(collection, [])
    return modules


def split_passage(text: str, minimum: int, maximum: int, overlap: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > maximum:
            sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", paragraph)
        else:
            sentences = [paragraph]
        for unit in sentences:
            candidate = f"{current}\n\n{unit}".strip() if current else unit
            if current and len(candidate) > maximum:
                if len(current) >= minimum:
                    chunks.append(current)
                retained = current[-overlap:] if overlap else ""
                boundary = retained.find(" ")
                retained = retained[boundary + 1 :] if boundary >= 0 else retained
                current = f"{retained}\n\n{unit}".strip()
            else:
                current = candidate
    if len(current) >= minimum:
        chunks.append(current)
    return chunks


def extract_book(row: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    source = git_source(row)
    if source is None:
        return []
    repo, commit = source
    repo_name = repo.split("/")[-1]
    snapshot = args.data_root / "sources/snapshots" / repo_name / commit
    collection_path = snapshot / "collections" / f"{row['slug']}.collection.xml"
    if not collection_path.exists():
        raise FileNotFoundError(collection_path)
    collection = ET.parse(collection_path).getroot()
    records: list[dict[str, Any]] = []
    for module_id, chapter_path in collection_modules(collection):
        module_path = snapshot / "modules" / module_id / "index.cnxml"
        if not module_path.exists():
            continue
        try:
            module = ET.parse(module_path).getroot()
        except ET.ParseError:
            continue
        title = next((text_from_cnxml(node) for node in module if local_name(node.tag) == "title"), "")
        if SKIP_MODULE_TITLES.fullmatch(title.strip()):
            continue
        content = next((node for node in module if local_name(node.tag) == "content"), None)
        if content is None:
            continue
        text = text_from_cnxml(content)
        # OpenStax's book-level licence does not necessarily cover embedded
        # third-party lessons or examination questions licensed by permission.
        # Figures are removed above; reject remaining textual permission grants
        # at module granularity rather than trying to infer their scope.
        if RESTRICTED_TEXT_MARKERS.search(text):
            continue
        for chunk_index, passage in enumerate(
            split_passage(text, args.min_chars, args.max_chars, args.overlap_chars)
        ):
            passage_hash = hashlib.sha256(passage.encode()).hexdigest()
            passage_id = stable_hex(row["slug"], commit, module_id, chunk_index, passage_hash)
            records.append(
                {
                    "passage_id": passage_id,
                    "book_slug": row["slug"],
                    "book_title": row["title"],
                    "tier": row["tier"],
                    "category": row["category"],
                    "module_id": module_id,
                    "module_title": title,
                    "chapter_path": chapter_path,
                    "chunk_index": chunk_index,
                    "passage": passage,
                    "passage_sha256": passage_hash,
                    "source_repo": repo,
                    "source_commit": commit,
                    "source_path": f"modules/{module_id}/index.cnxml",
                    "source_url": f"https://github.com/{repo}/blob/{commit}/modules/{module_id}/index.cnxml",
                    "evidence_url": row["evidence_url"],
                    "license": "CC-BY-4.0",
                    "license_url": CC_BY_URL,
                    "attribution": f"OpenStax, {row['title']}, CC BY 4.0",
                }
            )
    return records


def cmd_extract(args: argparse.Namespace) -> None:
    policy = load_policy(args.config)
    args.min_chars = args.min_chars or policy["passage_min_chars"]
    args.max_chars = args.max_chars or policy["passage_max_chars"]
    args.overlap_chars = args.overlap_chars if args.overlap_chars is not None else policy["passage_overlap_chars"]
    rows = load_manifest(args.config, args.inventory)
    selected = {row["slug"]: row for row in rows}
    if args.verified_passages:
        all_records = []
        for source in iter_jsonl(args.verified_passages):
            slug = source.get("book_slug")
            if slug not in selected:
                continue
            if source.get("license") != "CC-BY-4.0" or not source.get("immutable_ref"):
                raise ValueError(f"{slug}: verified passage lacks license/provenance")
            policy_row = selected[slug]
            if source["immutable_ref"] != policy_row["immutable_ref"]:
                raise ValueError(
                    f"{slug}: verified passage uses {source['immutable_ref']}, "
                    f"policy requires {policy_row['immutable_ref']}"
                )
            passage = source["passage"]
            title_match = re.match(r"Section:\s*([^\n]+)", passage)
            module_title = title_match.group(1).strip() if title_match else slug
            passage_id = stable_hex(
                slug, source["immutable_ref"], source["document_id"],
                source["passage_index"], source["passage_sha256"],
            )
            all_records.append({
                "passage_id": passage_id,
                "book_slug": slug,
                "book_title": source["book_title"],
                "tier": policy_row["tier"],
                "category": policy_row["category"],
                "module_id": source["document_id"],
                "module_title": module_title,
                "chapter_path": [],
                "chunk_index": source["passage_index"],
                "passage": passage,
                "passage_sha256": source["passage_sha256"],
                "source_repo": source["dataset"],
                "source_commit": source["immutable_ref"],
                "source_path": source["local_provenance"],
                "source_url": source["source_url"],
                "evidence_url": source["evidence_url"],
                "license": source["license"],
                "license_url": CC_BY_URL,
                "attribution": source["attribution"],
            })
        all_records.sort(key=lambda row: (row["book_slug"], row["module_id"], row["chunk_index"]))
        output = args.data_root / "passages/openstax_cc_by_en.jsonl"
        count = atomic_jsonl(output, all_records)
        per_book = Counter(row["book_slug"] for row in all_records)
        summary = {
            "passages": count,
            "books_with_passages": len(per_book),
            "books_pending": sorted(set(selected) - set(per_book)),
            "per_book": dict(sorted(per_book.items())),
            "characters": sum(len(row["passage"]) for row in all_records),
            "source": str(args.verified_passages),
            "provenance_policy": "official immutable OpenStax artifacts only",
        }
        atomic_json(args.data_root / "passages/summary.json", summary)
        print(json.dumps(summary, indent=2))
        return
    all_records: list[dict[str, Any]] = []
    per_book: dict[str, int] = {}
    seen: set[str] = set()
    for row in rows:
        records = extract_book(row, args)
        kept = []
        for record in records:
            if record["passage_sha256"] in seen:
                continue
            seen.add(record["passage_sha256"])
            kept.append(record)
        all_records.extend(kept)
        per_book[row["slug"]] = len(kept)
        print(f"extracted {row['slug']}: {len(kept)} passages", flush=True)
    all_records.sort(key=lambda row: (row["book_slug"], row["module_id"], row["chunk_index"]))
    output = args.data_root / "passages/openstax_cc_by_en.jsonl"
    count = atomic_jsonl(output, all_records)
    summary = {
        "passages": count,
        "books_with_passages": sum(value > 0 for value in per_book.values()),
        "books_pending": sorted(slug for slug, value in per_book.items() if value == 0),
        "per_book": per_book,
        "characters": sum(len(row["passage"]) for row in all_records),
    }
    atomic_json(args.data_root / "passages/summary.json", summary)
    print(json.dumps(summary, indent=2))


def allocated_tasks(total: int, weights: dict[str, float]) -> list[str]:
    raw = {name: total * weight for name, weight in weights.items()}
    counts = {name: int(value) for name, value in raw.items()}
    remainder = total - sum(counts.values())
    for name in sorted(weights, key=lambda key: (raw[key] - counts[key], key), reverse=True)[:remainder]:
        counts[name] += 1
    result = []
    for name in sorted(counts):
        result.extend([name] * counts[name])
    return result


def balanced_passages(
    rows: list[dict[str, Any]],
    count: int,
    supplemental_weight: float,
    *,
    salt: str,
) -> list[dict[str, Any]]:
    queues: dict[str, deque[dict[str, Any]]] = {}
    for book, book_rows in _group(rows, key=lambda row: row["book_slug"]).items():
        book_rows.sort(key=lambda row: stable_hex(row["passage_id"], "pilot", salt))
        queues[book] = deque(book_rows)
    primary = sorted(book for book, queue in queues.items() if queue and queue[0]["tier"] == "primary")
    supplemental = sorted(book for book, queue in queues.items() if queue and queue[0]["tier"] == "supplemental")
    selected = []
    cycle = 0
    supplemental_period = max(1, round(1 / supplemental_weight))
    while (primary or supplemental) and len(selected) < count:
        schedule = primary + (supplemental if cycle % supplemental_period == 0 else [])
        for book in schedule:
            if queues[book]:
                selected.append(queues[book].popleft())
                if len(selected) == count:
                    break
        primary = [book for book in primary if queues[book]]
        supplemental = [book for book in supplemental if queues[book]]
        cycle += 1
    if len(selected) < count:
        raise ValueError(f"only {len(selected)} passages available for {count} requests")
    return selected


def _group(rows: Iterable[dict[str, Any]], key: Any) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[key(row)].append(row)
    return result


def generation_messages(passage: dict[str, Any], task: str) -> list[dict[str, str]]:
    schema = {
        "instruction": "standalone user instruction or question",
        "response": "complete assistant answer",
        "verification": {
            "supported": True,
            "support_summary": "brief statement of source support",
            "answerable_without_source_in_prompt": True,
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "You create academically rigorous English instruction data grounded only in the supplied "
                "OpenStax passage. Return one JSON object and no markdown wrapper. Do not mention the passage, "
                "OpenStax, a textbook, or synthetic data in the learner-facing instruction or response. Do not "
                "copy a sequence longer than 20 words from the source. Do not invent factual claims. The response "
                "must be self-contained, pedagogically useful, and directly satisfy the instruction."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Task family: {task}\n"
                f"Task requirement: {TASK_PROMPTS[task]}\n\n"
                f"Source title: {passage['book_title']}\n"
                f"Source section: {' > '.join(passage['chapter_path'] + [passage['module_title']])}\n"
                f"Grounding passage:\n{passage['passage']}\n\n"
                f"Required JSON shape:\n{json.dumps(schema, ensure_ascii=False)}"
            ),
        },
    ]


def cmd_requests(args: argparse.Namespace) -> None:
    policy = load_policy(args.config)
    passage_path = args.data_root / "passages/openstax_cc_by_en.jsonl"
    rows = list(iter_jsonl(passage_path))
    accepted_target = args.target or policy["pilot_target_rows"]
    request_count = math.ceil(accepted_target * policy["generation_oversample"])
    tasks = Counter(allocated_tasks(request_count, policy["task_families"]))
    requests = []
    for task, task_count in sorted(tasks.items()):
        passages = balanced_passages(
            rows,
            task_count,
            policy["supplemental_sampling_weight"],
            salt=task,
        )
        for passage in passages:
            request_id = stable_hex("openstax-mimir-sft-v2", passage["passage_id"], task)
            requests.append(
                {
                    "request_id": request_id,
                    "family": task,
                    "language": "en",
                    "messages": generation_messages(passage, task),
                    "provenance": {key: value for key, value in passage.items() if key != "passage"},
                    "grounding_passage": passage["passage"],
                }
            )
    requests.sort(key=lambda row: stable_hex(row["request_id"], "request-order"))
    request_root = args.data_root / "requests"
    atomic_jsonl(request_root / "all.jsonl", requests)
    shard_rows = [[] for _ in range(args.shards)]
    for row in requests:
        index = int(row["request_id"][:16], 16) % args.shards
        shard_rows[index].append(row)
    for index, shard in enumerate(shard_rows):
        atomic_jsonl(request_root / "shards" / f"part-{index:05d}-of-{args.shards:05d}.jsonl", shard)
    summary = {
        "accepted_target": accepted_target,
        "generation_requests": len(requests),
        "shards": args.shards,
        "tasks": Counter(row["family"] for row in requests),
        "books": Counter(row["provenance"]["book_slug"] for row in requests),
        "policy": str(args.config),
    }
    summary["tasks"] = dict(summary["tasks"])
    summary["books"] = dict(summary["books"])
    atomic_json(request_root / "summary.json", summary)
    print(json.dumps(summary, indent=2))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    result.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    result.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("manifest").set_defaults(func=cmd_manifest)
    materialize = commands.add_parser("materialize")
    materialize.add_argument("--jobs", type=int, default=4)
    materialize.set_defaults(func=cmd_materialize)
    extract = commands.add_parser("extract")
    extract.add_argument("--verified-passages", type=Path, default=DEFAULT_VERIFIED_PASSAGES)
    extract.add_argument("--min-chars", type=int)
    extract.add_argument("--max-chars", type=int)
    extract.add_argument("--overlap-chars", type=int)
    extract.set_defaults(func=cmd_extract)
    requests = commands.add_parser("requests")
    requests.add_argument("--target", type=int)
    requests.add_argument("--shards", type=int, default=64)
    requests.set_defaults(func=cmd_requests)
    return result


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
