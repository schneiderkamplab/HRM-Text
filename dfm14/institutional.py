"""Prepare document-preserving Irish/Maltese EU publication windows on CPU."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
import os
from pathlib import Path
import re
import zipfile

from defusedxml import ElementTree as ET
import requests
from sacremoses import MosesDetokenizer
import typer

from dfm12.io import atomic, digest, file_hash, load, lock, write_json
from dfm12.prepare import Renderer
from dfm14.catalog import institutional_sources
from dfm14.transforms import TASKS, transform, window

app = typer.Typer()


def paragraphs(xml, language):
    detokenizer = MosesDetokenizer(lang=language)
    tree = ET.fromstring(xml)
    for paragraph in tree.findall(".//p"):
        sentences = []
        for sentence in paragraph.findall(".//s"):
            if sentence.get("lang", language) != language:
                sentences = []
                break
            words = [w.text or "" for w in sentence.findall("w")]
            if words:
                sentences.append(detokenizer.detokenize(words))
        text = " ".join(sentences).strip()
        # A missing/boilerplate paragraph is a boundary, not permission to join across it.
        good = len(text) >= 100 and not re.search(r"\.{4,}|�", text)
        yield paragraph.get("id"), text if good else None


def blocks(xml, language):
    selected, ids, size = [], [], 0
    for key, text in paragraphs(xml, language):
        if text is None or (selected and size + len(text) > 6000):
            if selected:
                yield ids, "\n\n".join(selected)
            selected, ids, size = [], [], 0
        if text:
            selected.append(text)
            ids.append(key)
            size += len(text)
    if selected:
        yield ids, "\n\n".join(selected)


def prepare(job):
    source, root, tokenizer = job
    root = Path(root)
    language = source["languages"][0]
    directory = root / "candidates" / source["component"] / "v2"
    with lock(directory/".lock"):
        archive = root / "downloads" / (language + ".zip")
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            tmp = archive.with_suffix(".partial")
            with requests.get(source["url"], stream=True, timeout=120) as response:
                response.raise_for_status()
                with tmp.open("wb") as handle:
                    for block in response.iter_content(1024*1024):
                        handle.write(block)
            os.replace(tmp, archive)
        sha = file_hash(archive)
        if (directory/"receipt.json").exists():
            result = load(directory/"receipt.json")
            if result["input_sha256"] != sha or result["sha256"] != file_hash(directory/"candidates.jsonl") or result["transforms_sha256"] != file_hash(directory/"transforms.jsonl"):
                raise ValueError("Institutional receipt mismatch")
            return result
        counts, seen = Counter(), set()
        renderer = Renderer(tokenizer, max_length=8192)
        with zipfile.ZipFile(archive) as z, atomic(directory/"candidates.jsonl") as out, atomic(directory/"transforms.jsonl") as derived:
            write_json(root/"sources"/source["component"]/"source-lock.json", dict(source=source,
                revision="v2", input_sha256=sha, license=z.read("LICENSE").decode(), readme=z.read("README").decode()))
            for name in sorted(z.namelist()):
                if not name.endswith(".xml"):
                    continue
                counts["source_documents"] += 1
                if z.getinfo(name).file_size > 50000000:
                    counts["oversize_xml"] += 1
                    continue
                try:
                    document_blocks = list(blocks(z.read(name), language))
                except ET.ParseError:
                    counts["invalid_xml"] += 1
                    continue
                for ordinal, (ids, text) in enumerate(document_blocks):
                    counts["source_windows"] += 1
                    if len(text) < 250:
                        counts["short_window"] += 1
                        continue
                    fingerprint = digest([language,text])
                    if fingerprint in seen:
                        counts["duplicate"] += 1
                        continue
                    seen.add(fingerprint)
                    provenance = dict(repo=source["repo"], revision="v2", archive_sha256=sha,
                        url=source["url"], file=name, row=ordinal, paragraph_ids=ids,
                        split="unsplit_source", component=source["component"],
                        reconstruction="Moses detokenization within original XML paragraph boundaries")
                    record = dict(id=fingerprint, language=language, task="document_seed", text=text,
                        provenance=provenance, training_ready=False, admission_authorized=False)
                    out.write(json.dumps(record,ensure_ascii=False)+"\n")
                    counts["candidates"] += 1
                    counts["language:"+language] += 1
                    try:
                        text = window(text,renderer.tokenizer,fingerprint)
                    except ValueError as exc:
                        counts["transform_hold:"+str(exc)] += 1
                        continue
                    for task in TASKS:
                        try:
                            row = transform(text,language,task,provenance)
                            row["rendered_tokens"] = renderer.count(row["messages"])
                            derived.write(json.dumps(row,ensure_ascii=False)+"\n")
                            counts["transform:"+task] += 1
                        except ValueError as exc:
                            counts["transform_hold:"+str(exc)] += 1
        result = dict(source=source, revision="v2", counts=dict(counts), input_sha256=sha,
            sha256=file_hash(directory/"candidates.jsonl"), transforms_sha256=file_hash(directory/"transforms.jsonl"),
            training_ready=False)
        write_json(directory/"receipt.json",result)
        return result


@app.command()
def run(root: Path = Path("data/dfm14/institutional-supplements")):
    base = load("data/dfm14/curated-supplements/configuration.json")
    config = dict(tokenizer=base["tokenizer"],tokenizer_sha256=base["tokenizer_sha256"], sources=institutional_sources(),
        implementation_sha256=file_hash(__file__))
    with lock(root/".lock"):
        if (root/"configuration.json").exists() and load(root/"configuration.json") != config:
            raise ValueError("Changed institutional configuration")
        write_json(root/"configuration.json",config)
        write_json(root/"progress.json",dict(phase="preparing"))
        with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context("spawn")) as pool:
            results=list(pool.map(prepare,[(s,str(root),config["tokenizer"]) for s in institutional_sources()]))
        write_json(root/"progress.json",dict(phase="cpu_pass_finished", results=results, training_ready=False))
        print(json.dumps([r["counts"] for r in results]),flush=True)


if __name__ == "__main__":
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    app()
