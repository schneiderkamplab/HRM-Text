"""CPU-only six-family calibration requests using existing native v4 contracts.

This prepares 100 attempts per language/family, not an accepted production quota.
It uses modernized English OpenHermes, never raw OpenHermes.
"""
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
import heapq
import json
import multiprocessing
import os
from pathlib import Path
from types import FunctionType

from huggingface_hub import HfApi, hf_hub_download
import typer

from dfm12.io import atomic, digest, file_hash, load, lock, rows, write_json
from dfm12 import multilingual_tasks as tasks
from dfm12.records import validate_messages
from dfm14.catalog import LANGUAGES
from dfm14.prepare_gpu import source_hold

app = typer.Typer()
factory = FunctionType(tasks.spec_for.__code__, dict(tasks.spec_for.__globals__, LANGUAGES=LANGUAGES),
    tasks.spec_for.__name__, tasks.spec_for.__defaults__, tasks.spec_for.__closure__)


def reservoir(items, size):
    heap, seen = [], set()
    for row in items:
        key = row["id"]
        if key in seen:
            continue
        seen.add(key)
        priority = int(digest(key), 16)
        entry = (-priority, key, row)
        if len(heap) < size:
            heapq.heappush(heap, entry)
        elif priority < -heap[0][0]:
            heapq.heapreplace(heap, entry)
    return [r for _, _, r in sorted(heap, reverse=True)]


def prepare_language(job):
    from tokenizers import Tokenizer
    language, audit_root, output, seed_file, count, tokenizer_path, source_chunks = job
    output, audit_root = Path(output), Path(audit_root)
    def documents():
        for chunk in source_chunks:
            path = audit_root / chunk["input"]
            if file_hash(path) != chunk["sha256"]:
                raise ValueError("Changed generation seed chunk")
            for row in rows(path):
                if source_hold(row):
                    continue
                yield dict(id=digest(row["audit_context"]["original"]), text=row["audit_context"]["original"],
                    provenance=row["provenance"], source_audit_id=row["audit_id"], language=language)
    seeds = {language:reservoir(documents(), max(600,count*3)), "openhermes":load(seed_file)}
    if not seeds[language] or not seeds["openhermes"]:
        raise ValueError("Missing generation seed pool")
    tokenizer = Tokenizer.from_file(tokenizer_path)
    config = dict(contract_version=4,cohort="dfm14-calibration-v1",quotas={k:count for k in tasks.QUOTAS})
    results = []
    for family in tasks.QUOTAS:
        path = output / language / (family+".jsonl")
        with atomic(path) as handle:
            for slot in range(count):
                spec = factory(language,family,slot,0,seeds,config)
                if spec.get("source") and family in {"multiturn", "grounded-instruct", "summary-rewrite"}:
                    spec.pop("topic",None)
                payload = tasks.request(spec)
                # Remove historical Northern-European-specific language advice.
                payload["messages"][0]["content"] = payload["messages"][0]["content"].replace(
                    "Pay particular\nattention to Faroese/Icelandic mathematical terms and Nynorsk/Bokmal distinctions.",
                    "Use natural native terminology and the correct script for the requested language.")
                budget = sum(len(tokenizer.encode(m["content"],add_special_tokens=False).ids) for m in payload["messages"])
                if budget+payload["max_tokens"] > 30000:
                    raise ValueError("Calibration request exceeds reserved 32K teacher budget")
                record = dict(id=digest([config["cohort"],language,family,slot]),spec=spec,request=payload,
                    estimated_prompt_tokens=budget,training_ready=False,admission_authorized=False,
                    source_review_required=bool(spec.get("source")))
                handle.write(json.dumps(record,ensure_ascii=False)+"\n")
        results.append(dict(language=language,family=family,path=str(path.resolve()),rows=count,sha256=file_hash(path)))
    print(json.dumps(dict(language=language,requests=count*len(tasks.QUOTAS))),flush=True)
    return results


@app.command()
def run(audit_root: Path = Path("data/dfm14/gpu-ready"),
        output: Path = Path("data/dfm14/generation-calibration-v1"), per_family: int = 100):
    manifest=load(audit_root/"manifest.json")
    if manifest["status"] != "ready_for_gpu_audit":
        raise ValueError("Source CPU preparation must finish first")
    with lock(output/".lock"):
        if (output/"manifest.json").exists():
            raise ValueError("Calibration already prepared; do not overwrite")
        repo = "schneiderkamplab/dfm8-openhermes-en"
        info = HfApi().dataset_info(repo)
        name = "data/train-00000.jsonl.gz"
        source = Path(hf_hub_download(repo,name,repo_type="dataset",revision=info.sha,
            local_dir=output/"downloads"/"modernized-openhermes-en"))
        def candidates():
            for ordinal,row in enumerate(rows(source)):
                messages = row.get("messages")
                if row.get("tools") or not isinstance(messages,list):
                    continue
                if not 2 <= len(messages) <= 12 or any(set(m)!={"role","content"} or m["role"] not in {"user","assistant"} for m in messages):
                    continue
                try:
                    validate_messages(messages)
                except ValueError:
                    continue
                if not 100 < len(json.dumps(messages,ensure_ascii=False)) < 6500:
                    continue
                yield dict(id=digest(messages),messages=messages,language="en",
                    provenance=dict(repo=repo,revision=info.sha,file=name,row=ordinal))
        seed_file = output/"modernized-openhermes-seeds.json"
        write_json(seed_file,reservoir(candidates(),600))
        write_json(output/"source-lock.json",dict(repo=repo,revision=info.sha,file=name,sha256=file_hash(source)))
        tokenizer = load("data/dfm14/cpu-preparation-expanded/configuration.json")["tokenizer"]["tokenizer_path"]
        with ProcessPoolExecutor(max_workers=16,mp_context=multiprocessing.get_context("spawn")) as pool:
            groups = list(pool.map(prepare_language,[(l,str(audit_root),str(output),str(seed_file),per_family,tokenizer,
                [c for c in manifest["chunks"] if c["language"]==l and c["task"]=="denoising"]) for l in LANGUAGES]))
        write_json(output/"manifest.json",dict(status="ready_for_generation_calibration",
            model=tasks.MODEL,context_length=32768,thinking=False,concurrency_per_endpoint=64,
            groups=[x for group in groups for x in group],rows=len(LANGUAGES)*len(tasks.QUOTAS)*per_family,
            source_manifest_sha256=file_hash(audit_root/"manifest.json"),
            code_sha256={str(p):file_hash(p) for p in [Path(__file__),Path(tasks.__file__)]},
            training_ready=False,production_requires="native quality calibration, source review and separate generated-output audit"))


if __name__ == "__main__":
    os.environ["TOKENIZERS_PARALLELISM"]="false"
    app()
