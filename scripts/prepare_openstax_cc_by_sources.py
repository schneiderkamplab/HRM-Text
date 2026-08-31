#!/usr/bin/env python3
"""Mirror and extract the verified English OpenStax CC BY allowlist.

The Hugging Face ``izumi-lab/open-text-books`` repack is deliberately not an
input.  Sources must match the immutable official artifacts recorded in
``docs/openstax_cc_by_inventory.csv`` and the relevance allowlist documented in
``wiki/pages/mimir-v1-evaluation-gap-analysis.md``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
from urllib.request import Request, urlopen


PRIMARY: dict[str, tuple[str, ...]] = {
    "mathematics_statistics": (
        "algebra-1", "algebra-and-trigonometry-2e", "college-algebra-2e",
        "contemporary-mathematics", "elementary-algebra-2e",
        "intermediate-algebra-2e", "introductory-business-statistics-2e",
        "introductory-statistics-2e", "prealgebra-2e", "precalculus-2e",
    ),
    "natural_health_sciences": (
        "anatomy-and-physiology-2e", "astronomy-2e", "biology-2e",
        "chemistry-2e", "college-physics-2e", "microbiology", "nutrition",
        "pharmacology", "physics", "population-health",
        "university-physics-volume-1", "university-physics-volume-2",
        "university-physics-volume-3",
    ),
    "business_economics_professional": (
        "business-ethics", "entrepreneurship", "introduction-business",
        "introduction-intellectual-property", "organizational-behavior",
        "principles-economics-3e", "principles-finance",
        "principles-macroeconomics-3e", "principles-management",
        "principles-marketing", "principles-microeconomics-3e",
    ),
    "social_sciences_humanities": (
        "american-government-4e", "introduction-anthropology",
        "introduction-philosophy", "introduction-political-science",
        "introduction-sociology-3e", "life-liberty-and-pursuit-happiness",
        "lifespan-development", "psychology-2e", "us-history",
        "world-history-volume-1", "world-history-volume-2", "writing-guide",
    ),
    "computing_technical": (
        "additive-manufacturing-essentials", "foundations-information-systems",
        "introduction-python-programming", "principles-data-science",
        "workplace-software-skills",
    ),
}

SUPPLEMENTAL = (
    "biology-ap-courses", "chemistry-atoms-first-2e",
    "college-algebra-corequisite-support-2e", "college-physics-ap-courses-2e",
    "college-success-concise", "concepts-biology",
    "preparing-for-college-success", "principles-macroeconomics-ap-courses-2e",
    "principles-microeconomics-ap-courses-2e", "statistics",
)

CC_BY_URLS = {
    "http://creativecommons.org/licenses/by/4.0/",
    "https://creativecommons.org/licenses/by/4.0/",
}
DROP_ELEMENTS = {"figure", "media", "image", "audio", "video", "iframe"}
BLOCK_ELEMENTS = {
    "title", "para", "item", "equation", "preformat",
    # The one allowlisted versioned web book is archived as XHTML.
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre",
}
RESTRICTED_TEXT_MARKERS = re.compile(
    r"(?:included|used|reprinted|adapted) with (?:the )?permission|all rights reserved",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Book:
    title: str
    slug: str
    category: str
    tier: str
    artifact_type: str
    retrieval_url: str
    evidence_url: str
    immutable_ref: str


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "HRM-Text research corpus provenance mirror/1.0"})
    with urlopen(request, timeout=120) as response:
        return response.read()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def run(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def load_books(inventory_path: Path) -> list[Book]:
    rows = {row["slug"]: row for row in csv.DictReader(inventory_path.open())}
    categories = {slug: category for category, slugs in PRIMARY.items() for slug in slugs}
    expected = set(categories) | set(SUPPLEMENTAL)
    missing = expected - set(rows)
    if missing:
        raise ValueError(f"allowlisted slugs missing from inventory: {sorted(missing)}")
    books: list[Book] = []
    for slug in sorted(expected):
        row = rows[slug]
        if row["language"] != "en" or row["status"] != "ready":
            raise ValueError(f"{slug}: inventory row is not ready English material")
        books.append(Book(
            title=row["title"], slug=slug,
            category=categories.get(slug, "supplemental_overlap"),
            tier="primary" if slug in categories else "supplemental",
            artifact_type=row["artifact_type"], retrieval_url=row["retrieval_url"],
            evidence_url=row["evidence_url"], immutable_ref=row["immutable_ref"],
        ))
    return books


def github_repo(url: str) -> str:
    match = re.fullmatch(r"https://github\.com/([^/]+/[^/]+)/archive/[0-9a-f]{40}\.tar\.gz", url)
    if not match:
        raise ValueError(f"unexpected Git snapshot URL: {url}")
    return match.group(1)


def checkout_git_snapshot(repo: str, commit: str, root: Path) -> Path:
    name = repo.split("/")[-1]
    checkout = root / "checkouts" / f"{name}__{commit[:12]}"
    if not (checkout / ".git").is_dir():
        checkout.parent.mkdir(parents=True, exist_ok=True)
        run("git", "clone", "--filter=blob:none", "--no-checkout",
            f"https://github.com/{repo}.git", str(checkout))
        run("git", "sparse-checkout", "init", "--no-cone", cwd=checkout)
        (checkout / ".git/info/sparse-checkout").write_text(
            "/collections/*.xml\n/modules/*/index.cnxml\n/LICENSE*\n"
        )
    run("git", "fetch", "origin", commit, cwd=checkout)
    run("git", "checkout", "--detach", commit, cwd=checkout)
    actual = run("git", "rev-parse", "HEAD", cwd=checkout)
    if actual != commit:
        raise ValueError(f"{repo}: expected {commit}, checked out {actual}")
    return checkout


def collection_metadata(path: Path) -> tuple[str, str, list[str]]:
    root = ET.parse(path).getroot()
    slug = ""
    license_url = ""
    for element in root.iter():
        name = local_name(element.tag)
        if name == "slug" and element.text:
            slug = element.text.strip()
        elif name == "license":
            license_url = element.attrib.get("url", "").strip()
    modules = [element.attrib["document"] for element in root.iter()
               if local_name(element.tag) == "module" and element.attrib.get("document")]
    return slug, license_url, modules


def find_collection(checkout: Path, slug: str) -> tuple[Path, list[str]]:
    candidates = sorted((checkout / "collections").glob("*.xml"))
    for path in candidates:
        found_slug, license_url, modules = collection_metadata(path)
        if found_slug != slug:
            continue
        if license_url not in CC_BY_URLS:
            raise ValueError(f"{slug}: collection license is {license_url!r}, not CC BY 4.0")
        if not modules:
            raise ValueError(f"{slug}: collection has no modules")
        return path, modules
    raise FileNotFoundError(f"{slug}: no matching collection in {checkout}")


def remove_dropped(root: ET.Element) -> None:
    for parent in root.iter():
        for child in list(parent):
            if local_name(child.tag) in DROP_ELEMENTS:
                parent.remove(child)


def normalized_text(element: ET.Element) -> str:
    text = " ".join("".join(element.itertext()).split())
    return html.unescape(text)


def extract_blocks(data: bytes) -> tuple[str, list[str]]:
    root = ET.fromstring(data)
    remove_dropped(root)
    title = next((normalized_text(e) for e in root.iter()
                  if local_name(e.tag) == "title" and normalized_text(e)), "")
    blocks: list[str] = []
    for element in root.iter():
        name = local_name(element.tag)
        if name not in BLOCK_ELEMENTS:
            continue
        if name in {"item", "li"} and any(
            local_name(child.tag) in {"para", "p"}
            for child in element.iter() if child is not element
        ):
            continue
        value = normalized_text(element)
        if value and (not blocks or value != blocks[-1]):
            blocks.append(value)
    return title, blocks


def chunk_blocks(title: str, blocks: Iterable[str], min_chars: int, max_chars: int) -> list[str]:
    prefix = f"Section: {title}\n\n" if title else ""
    chunks: list[str] = []
    current = prefix
    for block in blocks:
        if len(block) > max_chars:
            pieces = [block[i:i + max_chars] for i in range(0, len(block), max_chars)]
        else:
            pieces = [block]
        for piece in pieces:
            candidate = f"{current}\n\n{piece}".strip()
            if current.strip() and len(candidate) > max_chars:
                if len(current.strip()) >= min_chars:
                    chunks.append(current.strip())
                current = f"{prefix}{piece}".strip()
            else:
                current = candidate
    if len(current.strip()) >= min_chars:
        chunks.append(current.strip())
    elif chunks and current.strip():
        merged = f"{chunks[-1]}\n\n{current.strip()}"
        if len(merged) <= max_chars:
            chunks[-1] = merged
    return chunks


def passage_record(book: Book, document_id: str, source_url: str, local_path: Path,
                   artifact_sha256: str, passage_index: int, passage: str) -> dict[str, Any]:
    return {
        "dataset": "OpenStax/official-cc-by-4.0",
        "book_title": book.title,
        "book_slug": book.slug,
        "category": book.category,
        "tier": book.tier,
        "document_id": document_id,
        "passage_index": passage_index,
        "source_url": source_url,
        "evidence_url": book.evidence_url,
        "license": "CC-BY-4.0",
        "attribution": f"OpenStax, {book.title}, https://openstax.org/details/books/{book.slug}",
        "immutable_ref": book.immutable_ref,
        "artifact_sha256": artifact_sha256,
        "local_provenance": str(local_path),
        "passage": passage,
        "passage_sha256": sha256_bytes(passage.encode()),
    }


def extract_git_book(book: Book, checkout: Path, min_chars: int, max_chars: int) -> list[dict[str, Any]]:
    collection, modules = find_collection(checkout, book.slug)
    repo = github_repo(book.retrieval_url)
    rows: list[dict[str, Any]] = []
    for module in modules:
        path = checkout / "modules" / module / "index.cnxml"
        if not path.is_file():
            raise FileNotFoundError(f"{book.slug}: missing module {module}")
        data = path.read_bytes()
        title, blocks = extract_blocks(data)
        if RESTRICTED_TEXT_MARKERS.search("\n".join(blocks)):
            continue
        source_url = f"https://github.com/{repo}/blob/{book.immutable_ref}/modules/{module}/index.cnxml"
        for index, passage in enumerate(chunk_blocks(title, blocks, min_chars, max_chars)):
            rows.append(passage_record(book, module, source_url, path, sha256_bytes(data), index, passage))
    if not rows:
        raise ValueError(f"{book.slug}: extraction yielded no passages from {collection}")
    return rows


def discover_archive_url(book: Book) -> str:
    page = fetch(book.retrieval_url).decode("utf-8", errors="replace")
    match = re.search(r'"archiveUrl":"([^"]+)"', page)
    if not match:
        raise ValueError(f"{book.slug}: could not discover official archive URL")
    return "https://openstax.org" + match.group(1)


def leaf_pages(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, dict):
        if node.get("slug") and not node.get("contents"):
            yield node
        for value in node.values():
            yield from leaf_pages(value)
    elif isinstance(node, list):
        for value in node:
            yield from leaf_pages(value)


def extract_web_book(book: Book, root: Path, min_chars: int, max_chars: int,
                     workers: int) -> list[dict[str, Any]]:
    archive = discover_archive_url(book)
    book_url = f"{archive}/contents/{book.immutable_ref}.json"
    book_data = fetch(book_url)
    metadata = json.loads(book_data)
    expected_id, expected_version = book.immutable_ref.split("@", 1)
    if metadata.get("id") != expected_id or metadata.get("version") != expected_version:
        raise ValueError(f"{book.slug}: archive returned a different immutable version")
    if metadata.get("license", {}).get("url") not in CC_BY_URLS:
        raise ValueError(f"{book.slug}: archived book is not CC BY 4.0")
    mirror = root / "web" / book.slug
    atomic_write(mirror / "book.json", book_data)
    pages = {page["id"].split("@", 1)[0]: page for page in leaf_pages(metadata["tree"])}

    def download(page_id: str) -> tuple[str, bytes, str]:
        url = f"{archive}/contents/{book.immutable_ref}:{page_id}.xhtml"
        return page_id, fetch(url), url

    downloaded: list[tuple[str, bytes, str]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(download, page_id) for page_id in sorted(pages)]
        for future in as_completed(futures):
            downloaded.append(future.result())
    rows: list[dict[str, Any]] = []
    for page_id, data, url in sorted(downloaded):
        path = mirror / "pages" / f"{page_id}.xhtml"
        atomic_write(path, data)
        title, blocks = extract_blocks(data)
        if RESTRICTED_TEXT_MARKERS.search("\n".join(blocks)):
            continue
        for index, passage in enumerate(chunk_blocks(title, blocks, min_chars, max_chars)):
            rows.append(passage_record(book, page_id, url, path, sha256_bytes(data), index, passage))
    if not rows:
        raise ValueError(f"{book.slug}: archived web extraction yielded no passages")
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=Path("docs/openstax_cc_by_inventory.csv"))
    parser.add_argument("--download-root", type=Path,
                        default=Path("data/downloads/datasets/openstax_cc_by"))
    parser.add_argument("--output-dir", type=Path,
                        default=Path("data/mimir_grounded_500k/openstax_cc_by"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--min-chars", type=int, default=800)
    parser.add_argument("--max-chars", type=int, default=6000)
    args = parser.parse_args()
    books = load_books(args.inventory)
    args.download_root.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    snapshots: dict[tuple[str, str], Path] = {}
    git_books = [book for book in books if book.artifact_type == "official_git_snapshot"]
    unique = {(github_repo(book.retrieval_url), book.immutable_ref) for book in git_books}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        future_map = {
            pool.submit(checkout_git_snapshot, repo, commit, args.download_root): (repo, commit)
            for repo, commit in sorted(unique)
        }
        for future in as_completed(future_map):
            key = future_map[future]
            snapshots[key] = future.result()
            print(f"verified snapshot {key[0]}@{key[1]}", flush=True)

    all_rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"books": {}, "total_books": len(books)}
    for book in books:
        if book.artifact_type == "official_git_snapshot":
            key = (github_repo(book.retrieval_url), book.immutable_ref)
            rows = extract_git_book(book, snapshots[key], args.min_chars, args.max_chars)
        elif book.artifact_type == "official_versioned_web_book":
            rows = extract_web_book(book, args.download_root, args.min_chars,
                                    args.max_chars, args.workers)
        else:
            raise ValueError(f"{book.slug}: unsupported allowlisted artifact {book.artifact_type}")
        all_rows.extend(rows)
        summary["books"][book.slug] = {
            "title": book.title, "tier": book.tier, "category": book.category,
            "artifact_type": book.artifact_type, "immutable_ref": book.immutable_ref,
            "passages": len(rows), "characters": sum(len(row["passage"]) for row in rows),
        }
        print(f"extracted {book.slug}: {len(rows):,} passages", flush=True)

    # Bundled OpenStax repositories intentionally reuse modules across related
    # editions. Prefer the primary title's attribution and prevent supplemental
    # overlap from multiplying identical grounding text.
    raw_passages = len(all_rows)
    unique_rows: list[dict[str, Any]] = []
    seen_passages: set[str] = set()
    for row in sorted(
        all_rows,
        key=lambda row: (
            row["tier"] != "primary", row["book_slug"],
            row["document_id"], row["passage_index"],
        ),
    ):
        if row["passage_sha256"] in seen_passages:
            continue
        seen_passages.add(row["passage_sha256"])
        unique_rows.append(row)
    unique_rows.sort(key=lambda row: (row["book_slug"], row["document_id"], row["passage_index"]))
    write_jsonl(args.output_dir / "passages.jsonl", unique_rows)
    summary["raw_passages_before_deduplication"] = raw_passages
    summary["exact_duplicate_passages_removed"] = raw_passages - len(unique_rows)
    summary["total_passages"] = len(unique_rows)
    summary["total_characters"] = sum(len(row["passage"]) for row in unique_rows)
    summary["license"] = "CC-BY-4.0"
    summary["source_policy"] = "official immutable artifacts only; no Hugging Face repack"
    atomic_write(args.output_dir / "summary.json",
                 (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({key: summary[key] for key in ("total_books", "total_passages", "total_characters", "license")}, indent=2))


if __name__ == "__main__":
    main()
