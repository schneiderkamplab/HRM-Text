#!/usr/bin/env python3
"""Harvest and convert newly licensed Tidsskrift.dk articles conservatively."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree as ET

import pyarrow.parquet as pq
import requests
from langdetect import DetectorFactory, LangDetectException, detect
from lxml import etree as LET
from pypdf import PdfReader


OAI_ENDPOINT = "https://tidsskrift.dk/index/oai"
USER_AGENT = "HRM-Text academic metadata harvester/1.0 (contact: peter-sk@sdu.dk)"
XLINK = "{http://www.w3.org/1999/xlink}href"
STRICT_LICENSES = {"cc0", "cc-by", "cc-by-sa", "public-domain"}
DetectorFactory.seed = 0
logging.getLogger("pypdf").setLevel(logging.ERROR)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def descendants(element: ET.Element, name: str) -> list[ET.Element]:
    return [node for node in element.iter() if local_name(node.tag) == name]


def first_text(element: ET.Element, name: str) -> str:
    nodes = descendants(element, name)
    if not nodes:
        return ""
    return " ".join(" ".join(nodes[0].itertext()).split())


def canonical_url(value: str) -> str:
    if not value:
        return ""
    parts = urlsplit(value.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def classify_license(url: str, text: str) -> str:
    value = f"{url} {text}".lower().replace("_", "-")
    if "creativecommons.org/publicdomain/zero" in value or re.search(r"\bcc0\b", value):
        return "cc0"
    if "creativecommons.org/publicdomain/mark" in value or "public domain" in value:
        return "public-domain"
    if "creativecommons.org/licenses/" not in value:
        return "unknown"
    if "by-nc" in value or "by-nd" in value or "-nc" in value or "-nd" in value:
        return "restricted-cc"
    if "/by-sa/" in value:
        return "cc-by-sa"
    if "/by/" in value:
        return "cc-by"
    return "unknown-cc"


def parse_record(record: ET.Element) -> dict[str, Any] | None:
    headers = [node for node in record if local_name(node.tag) == "header"]
    if not headers:
        return None
    header = headers[0]
    oai_id = first_text(header, "identifier")
    if not oai_id:
        return None
    if header.attrib.get("status") == "deleted":
        return {"oai_id": oai_id, "deleted": 1}
    articles = descendants(record, "article")
    if not articles:
        return None
    article = articles[0]
    licenses = descendants(article, "license")
    license_url = licenses[0].attrib.get(XLINK, "") if licenses else ""
    license_text = " ".join(" ".join(licenses[0].itertext()).split()) if licenses else ""
    self_uris = descendants(article, "self-uri")
    article_url = ""
    pdf_url = ""
    for node in self_uris:
        href = node.attrib.get(XLINK, "")
        if node.attrib.get("content-type") == "application/pdf":
            pdf_url = href
        elif not article_url:
            article_url = href
    doi = ""
    publisher_id = ""
    for node in descendants(article, "article-id"):
        value = " ".join(node.itertext()).strip()
        if node.attrib.get("pub-id-type") == "doi":
            doi = value
        elif node.attrib.get("pub-id-type") == "publisher-id":
            publisher_id = value
    authors: list[str] = []
    for contrib in descendants(article, "contrib"):
        surname = first_text(contrib, "surname")
        given = first_text(contrib, "given-names")
        name = " ".join(part for part in (given, surname) if part)
        if name and name not in authors:
            authors.append(name)
    sets = [" ".join(node.itertext()).strip() for node in descendants(header, "setSpec")]
    return {
        "oai_id": oai_id,
        "datestamp": first_text(header, "datestamp"),
        "set_specs": sets,
        "language": article.attrib.get("{http://www.w3.org/XML/1998/namespace}lang", ""),
        "journal_slug": first_text(article, "journal-id"),
        "journal_title": first_text(article, "journal-title"),
        "publisher_id": publisher_id,
        "doi": doi,
        "title": first_text(article, "article-title"),
        "abstract": first_text(article, "abstract"),
        "authors": authors,
        "article_url": canonical_url(article_url),
        "pdf_url": canonical_url(pdf_url),
        "license_url": canonical_url(license_url),
        "license_text": license_text,
        "license_class": classify_license(license_url, license_text),
        "copyright": first_text(article, "copyright-statement"),
        "deleted": 0,
    }


def initialize_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS records (oai_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    return connection


def request_xml(session: requests.Session, params: dict[str, str], retries: int) -> ET.Element:
    error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = session.get(OAI_ENDPOINT, params=params, timeout=120)
            response.raise_for_status()
            try:
                root = ET.fromstring(response.content)
            except ET.ParseError:
                # A small number of legacy OJS records contain illegal XML 1.0
                # characters. Recover the page structure, but continue to apply
                # normal record and explicit-license validation downstream.
                parser = LET.XMLParser(recover=True, resolve_entities=False, no_network=True)
                recovered = LET.fromstring(response.content, parser=parser)
                root = ET.fromstring(LET.tostring(recovered, encoding="utf-8"))
                print(
                    f"warning: recovered malformed legacy OAI XML page url={response.url}",
                    file=sys.stderr,
                    flush=True,
                )
            errors = descendants(root, "error")
            if errors:
                code = errors[0].attrib.get("code", "unknown")
                message = " ".join(errors[0].itertext()).strip()
                if code == "noRecordsMatch":
                    return root
                raise RuntimeError(f"OAI {code}: {message}")
            return root
        except (requests.RequestException, ET.ParseError, RuntimeError) as exc:
            error = exc
            if attempt < retries:
                time.sleep(min(60.0, 2.0**attempt))
    raise RuntimeError(f"OAI request failed after {retries + 1} attempts: {error}")


def cmd_scan(args: argparse.Namespace) -> None:
    connection = initialize_db(args.database)
    token_row = connection.execute("SELECT value FROM state WHERE key='resumption_token'").fetchone()
    token = token_row[0] if token_row else ""
    session = requests.Session()
    session.headers["User-Agent"] = args.user_agent
    pages = 0
    while True:
        params = (
            {"verb": "ListRecords", "resumptionToken": token}
            if token
            else {"verb": "ListRecords", "metadataPrefix": "oai_openaire_jats"}
        )
        root = request_xml(session, params, args.retries)
        parsed = [row for record in descendants(root, "record") if (row := parse_record(record))]
        with connection:
            connection.executemany(
                "INSERT INTO records(oai_id,payload) VALUES(?,?) "
                "ON CONFLICT(oai_id) DO UPDATE SET payload=excluded.payload",
                [(row["oai_id"], json.dumps(row, ensure_ascii=False, separators=(",", ":"))) for row in parsed],
            )
            tokens = descendants(root, "resumptionToken")
            token = (tokens[0].text or "").strip() if tokens else ""
            connection.execute(
                "INSERT INTO state(key,value) VALUES('resumption_token',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (token,),
            )
        pages += 1
        total = connection.execute("SELECT count(*) FROM records").fetchone()[0]
        print(f"pages={pages} records={total} next_token={'yes' if token else 'no'}", flush=True)
        if not token or (args.max_pages and pages >= args.max_pages):
            break
        time.sleep(args.delay)


def list_base_sets(user_agent: str, delay: float, retries: int) -> list[str]:
    session = requests.Session()
    session.headers["User-Agent"] = user_agent
    token = ""
    result: set[str] = set()
    while True:
        params = (
            {"verb": "ListSets", "resumptionToken": token}
            if token
            else {"verb": "ListSets"}
        )
        root = request_xml(session, params, retries)
        for node in descendants(root, "setSpec"):
            value = " ".join(node.itertext()).strip()
            if value and ":" not in value and value != "driver":
                result.add(value)
        tokens = descendants(root, "resumptionToken")
        token = (tokens[0].text or "").strip() if tokens else ""
        if not token:
            break
        time.sleep(delay)
    return sorted(result)


def scan_one_set(args: argparse.Namespace, set_spec: str) -> tuple[str, int]:
    connection = initialize_db(args.database)
    state_key = f"set:{set_spec}"
    state = connection.execute("SELECT value FROM state WHERE key=?", (state_key,)).fetchone()
    if state and state[0] == "DONE":
        return set_spec, 0
    token = state[0] if state else ""
    session = requests.Session()
    session.headers["User-Agent"] = args.user_agent
    pages = 0
    while True:
        params = (
            {"verb": "ListRecords", "resumptionToken": token}
            if token
            else {
                "verb": "ListRecords",
                "metadataPrefix": "oai_openaire_jats",
                "set": set_spec,
            }
        )
        root = request_xml(session, params, args.retries)
        parsed = [row for record in descendants(root, "record") if (row := parse_record(record))]
        tokens = descendants(root, "resumptionToken")
        token = (tokens[0].text or "").strip() if tokens else ""
        with connection:
            connection.executemany(
                "INSERT INTO records(oai_id,payload) VALUES(?,?) "
                "ON CONFLICT(oai_id) DO UPDATE SET payload=excluded.payload",
                [(row["oai_id"], json.dumps(row, ensure_ascii=False, separators=(",", ":"))) for row in parsed],
            )
            connection.execute(
                "INSERT INTO state(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (state_key, token or "DONE"),
            )
        pages += 1
        if not token:
            break
        time.sleep(args.delay)
    connection.close()
    return set_spec, pages


def cmd_scan_sets(args: argparse.Namespace) -> None:
    sets = list_base_sets(args.user_agent, args.delay, args.retries)
    print(f"journal_sets={len(sets)} workers={args.workers}", flush=True)
    completed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(scan_one_set, args, set_spec): set_spec for set_spec in sets}
        for future in as_completed(futures):
            set_spec, pages = future.result()
            completed += 1
            print(
                f"sets_completed={completed}/{len(sets)} set={set_spec} pages={pages}",
                flush=True,
            )
    connection = initialize_db(args.database)
    records = connection.execute("SELECT count(*) FROM records").fetchone()[0]
    print(f"set_scan_complete records={records}", flush=True)


def existing_article_urls(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    result: set[str] = set()
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(columns=["sources"], batch_size=4096):
        for row in batch.to_pylist():
            for source in row.get("sources") or []:
                url = canonical_url(str(source.get("url") or ""))
                if url:
                    result.add(url)
    return result


def normalized_title(value: str) -> str:
    return re.sub(r"[^a-z0-9æøå]+", " ", value.lower()).strip()


def existing_raw_titles(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    result: set[str] = set()
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(columns=["text"], batch_size=2048):
        for row in batch.to_pylist():
            text = str(row.get("text") or "")
            headings = re.findall(r"(?m)^##\s+(.+?)\s*$", text[:4000])
            for heading in headings[:2]:
                title = normalized_title(heading)
                if len(title) >= 8 and title not in {"resume", "abstract", "indledning"}:
                    result.add(title)
    return result


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


def cmd_export(args: argparse.Namespace) -> None:
    connection = initialize_db(args.database)
    existing = existing_article_urls(args.existing_bt)
    raw_titles = existing_raw_titles(args.existing_raw)
    candidates: list[dict[str, Any]] = []
    license_counts: dict[str, int] = {}
    for (payload,) in connection.execute("SELECT payload FROM records ORDER BY oai_id"):
        row = json.loads(payload)
        license_class = row.get("license_class", "unknown")
        license_counts[license_class] = license_counts.get(license_class, 0) + 1
        if license_class not in STRICT_LICENSES:
            continue
        if (
            not row.get("pdf_url")
            or row.get("article_url") in existing
            or normalized_title(str(row.get("title") or "")) in raw_titles
        ):
            continue
        row["existing_tidsskrift_bt_overlap"] = False
        candidates.append(row)
    count = atomic_jsonl(args.output, candidates)
    summary = {
        "inventory_records": sum(license_counts.values()),
        "license_counts": dict(sorted(license_counts.items())),
        "existing_article_urls": len(existing),
        "existing_raw_titles": len(raw_titles),
        "strict_new_candidates": count,
        "candidate_output": str(args.output),
    }
    args.output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def cmd_download(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = args.user_agent
    downloaded = 0
    failed = 0
    failures_path = args.output_dir / "download_failures.jsonl"
    for index, row in enumerate(iter_jsonl(args.input)):
        if args.max_articles and downloaded >= args.max_articles:
            break
        if len(str(row.get("abstract") or "").strip()) < args.min_abstract_chars:
            continue
        destination = args.output_dir / f"{re.sub(r'[^A-Za-z0-9_.-]+', '_', row['oai_id'])}.pdf"
        if destination.is_file() and destination.stat().st_size > 1000:
            continue
        temporary = destination.with_suffix(".pdf.part")
        try:
            response = session.get(row["pdf_url"], timeout=180, stream=True)
            response.raise_for_status()
            size = 0
            with temporary.open("wb") as handle:
                for block in response.iter_content(1024 * 1024):
                    size += len(block)
                    if size > args.max_bytes:
                        raise ValueError(f"article exceeds --max-bytes: {row['pdf_url']}")
                    handle.write(block)
            if temporary.read_bytes()[:5] != b"%PDF-":
                raise ValueError("response is not a PDF")
        except (OSError, requests.RequestException, ValueError) as exc:
            temporary.unlink(missing_ok=True)
            with failures_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "oai_id": row["oai_id"],
                            "pdf_url": row["pdf_url"],
                            "error": f"{type(exc).__name__}: {exc}",
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            failed += 1
            print(f"failed={failed} index={index} url={row['pdf_url']}", flush=True)
            time.sleep(args.delay)
            continue
        temporary.replace(destination)
        downloaded += 1
        print(f"downloaded={downloaded} index={index} file={destination.name}", flush=True)
        time.sleep(args.delay)
    print(json.dumps({"downloaded": downloaded, "failed": failed}, sort_keys=True))


def clean_pdf_text(text: str) -> str:
    text = text.replace("\u00ad", "").replace("\x00", "")
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def detected_language(text: str) -> str:
    try:
        return detect(text[:20000])
    except LangDetectException:
        return "unknown"


def normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def word_spans(value: str) -> list[tuple[str, int, int]]:
    return [(match.group().casefold(), match.start(), match.end()) for match in re.finditer(r"\w+", value)]


def find_token_sequence(
    haystack: list[str], needle: list[str], start: int = 0
) -> int:
    if not needle:
        return -1
    stop = len(haystack) - len(needle) + 1
    for index in range(start, max(start, stop)):
        if haystack[index : index + len(needle)] == needle:
            return index
    return -1


def remove_exact_abstract(article: str, abstract: str) -> tuple[str, bool]:
    """Remove an abstract despite PDF whitespace and punctuation differences."""
    article_spans = word_spans(article)
    abstract_spans = word_spans(abstract)
    abstract_tokens = [token for token, _, _ in abstract_spans]
    article_tokens = [token for token, _, _ in article_spans]
    if len(abstract_tokens) < 20:
        return article, False
    anchor_size = min(12, len(abstract_tokens))
    start_index = find_token_sequence(article_tokens, abstract_tokens[:anchor_size])
    if start_index < 0:
        return article, False
    end_index = find_token_sequence(
        article_tokens,
        abstract_tokens[-anchor_size:],
        start_index + 1,
    )
    if end_index < 0:
        return article, False
    matched_tokens = end_index + anchor_size - start_index
    if matched_tokens > len(abstract_tokens) * 2 + 30:
        return article, False
    start_char = article_spans[start_index][1]
    end_char = article_spans[end_index + anchor_size - 1][2]
    return clean_pdf_text(article[:start_char] + "\n\n" + article[end_char:]), True


def target_leaks_into_prompt(article: str, abstract: str) -> bool:
    article_tokens = [token for token, _, _ in word_spans(article)]
    abstract_tokens = [token for token, _, _ in word_spans(abstract)]
    if len(abstract_tokens) < 20:
        return False
    window = min(20, len(abstract_tokens))
    probes = [
        abstract_tokens[offset : offset + window]
        for offset in {0, max(0, (len(abstract_tokens) - window) // 2), len(abstract_tokens) - window}
    ]
    return any(find_token_sequence(article_tokens, probe) >= 0 for probe in probes)


def extract_pdf_text(path: Path, engine: str, pdftotext: str) -> str:
    if engine == "pypdf":
        reader = PdfReader(path)
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    process = subprocess.run(
        [pdftotext, "-layout", str(path), "-"],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return process.stdout


def cmd_convert(args: argparse.Namespace) -> None:
    rows: list[dict[str, Any]] = []
    rejected: dict[str, int] = {}

    def reject(reason: str) -> None:
        rejected[reason] = rejected.get(reason, 0) + 1

    for source in iter_jsonl(args.input):
        pdf = args.pdf_dir / f"{re.sub(r'[^A-Za-z0-9_.-]+', '_', source['oai_id'])}.pdf"
        abstract = str(source.get("abstract") or "").strip()
        if not pdf.is_file():
            reject("missing_pdf")
            continue
        if len(abstract) < args.min_abstract_chars:
            reject("missing_or_short_abstract")
            continue
        try:
            extracted = extract_pdf_text(pdf, args.pdf_engine, args.pdftotext)
        except Exception:
            reject("pdf_text_extraction_failed")
            continue
        article = clean_pdf_text(extracted)
        article, abstract_removed = remove_exact_abstract(article, abstract)
        if target_leaks_into_prompt(article, abstract):
            reject("target_leakage")
            continue
        if not (args.min_article_chars <= len(article) <= args.max_article_chars):
            reject("article_length")
            continue
        language = detected_language(article)
        abstract_language = detected_language(abstract)
        if language not in {"da", "en"} or abstract_language != language:
            reject("language_mismatch")
            continue
        if language == "da":
            prompt = (
                "Skriv et kort, dækkende resumé af den følgende danske "
                "forsknings- eller fagartikel. Medtag kun oplysninger, som "
                f"fremgår af artiklen.\n\nArtikel:\n{article}"
            )
        else:
            prompt = (
                "Write a concise, comprehensive summary of the following research or "
                "professional article. Include only information supported by the "
                f"article.\n\nArticle:\n{article}"
            )
        rows.append(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    },
                    {"role": "assistant", "content": abstract},
                ],
                "source": "tidsskrift.dk",
                "source_id": source["oai_id"],
                "title": source.get("title"),
                "authors": source.get("authors"),
                "journal": source.get("journal_title"),
                "url": source.get("article_url"),
                "license": source.get("license_url"),
                "task": "article_to_author_abstract",
                "detected_language": language,
                "abstract_language": abstract_language,
                "author_abstract_removed_from_input": abstract_removed,
                "source_text_sha256": hashlib.sha256(article.encode("utf-8")).hexdigest(),
            }
        )
    count = atomic_jsonl(args.output, rows)
    print(
        json.dumps(
            {"rows": count, "rejected": dict(sorted(rejected.items())), "output": str(args.output)},
            indent=2,
            sort_keys=True,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan")
    scan.add_argument("--database", type=Path, default=Path("data/dfm10_tidsskrift_expansion/inventory.sqlite3"))
    scan.add_argument("--delay", type=float, default=1.0)
    scan.add_argument("--retries", type=int, default=5)
    scan.add_argument("--max-pages", type=int, default=0)
    scan.add_argument("--user-agent", default=USER_AGENT)
    scan.set_defaults(func=cmd_scan)
    scan_sets = subparsers.add_parser("scan-sets")
    scan_sets.add_argument("--database", type=Path, default=Path("data/dfm10_tidsskrift_expansion/inventory.sqlite3"))
    scan_sets.add_argument("--delay", type=float, default=0.5)
    scan_sets.add_argument("--retries", type=int, default=5)
    scan_sets.add_argument("--workers", type=int, default=2)
    scan_sets.add_argument("--user-agent", default=USER_AGENT)
    scan_sets.set_defaults(func=cmd_scan_sets)
    export = subparsers.add_parser("export")
    export.add_argument("--database", type=Path, default=Path("data/dfm10_tidsskrift_expansion/inventory.sqlite3"))
    export.add_argument("--existing-bt", type=Path, default=Path("data/downloads/datasets/oliverkinch_tidsskrift_dk_bt/data/train-00000-of-00001.parquet"))
    export.add_argument("--existing-raw", type=Path, default=Path("data/downloads/datasets/danish_dynaword/data/tidsskrift-dk/tidsskrift-dk.parquet"))
    export.add_argument("--output", type=Path, default=Path("data/dfm10_tidsskrift_expansion/strict_new_candidates.jsonl"))
    export.set_defaults(func=cmd_export)
    download = subparsers.add_parser("download")
    download.add_argument("--input", type=Path, default=Path("data/dfm10_tidsskrift_expansion/strict_new_candidates.jsonl"))
    download.add_argument("--output-dir", type=Path, default=Path("data/dfm10_tidsskrift_expansion/pdfs"))
    download.add_argument("--delay", type=float, default=1.5)
    download.add_argument("--max-articles", type=int, default=0)
    download.add_argument("--min-abstract-chars", type=int, default=120)
    download.add_argument("--max-bytes", type=int, default=50 * 1024 * 1024)
    download.add_argument("--user-agent", default=USER_AGENT)
    download.set_defaults(func=cmd_download)
    convert = subparsers.add_parser("convert")
    convert.add_argument("--input", type=Path, default=Path("data/dfm10_tidsskrift_expansion/strict_new_candidates.jsonl"))
    convert.add_argument("--pdf-dir", type=Path, default=Path("data/dfm10_tidsskrift_expansion/pdfs"))
    convert.add_argument(
        "--output",
        type=Path,
        default=Path("data/dfm10_tidsskrift_expansion/tidsskrift_open_article_summaries_candidates.jsonl"),
    )
    convert.add_argument("--pdftotext", default="pdftotext")
    convert.add_argument("--pdf-engine", choices=("pypdf", "pdftotext"), default="pypdf")
    convert.add_argument("--min-abstract-chars", type=int, default=120)
    convert.add_argument("--min-article-chars", type=int, default=1500)
    convert.add_argument("--max-article-chars", type=int, default=12000)
    convert.set_defaults(func=cmd_convert)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
