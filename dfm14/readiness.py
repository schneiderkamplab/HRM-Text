"""Final CPU handoff checks against the actual local teacher tokenizer."""
from collections.abc import Mapping
import json
from pathlib import Path

import typer

from dfm12.io import digest, file_hash, load, rows, write_json
from dfm14.audit_protocol_extended import messages

TEACHER = Path("/work/dfm/.home/.cache/huggingface/hub/models--google--gemma-4-26B-A4B-it/snapshots/4d7ae4984b7db7de8f8457170b3f1a419ee76d52")
app=typer.Typer()


def count(tokenizer, conversation):
    ids=tokenizer.apply_chat_template(conversation,tokenize=True,add_generation_prompt=True,enable_thinking=False)
    if isinstance(ids,Mapping):
        ids=ids["input_ids"]
    if not isinstance(ids,list) or any(type(i) is not int for i in ids):
        raise ValueError("Unexpected teacher tokenizer output")
    return len(ids)


@app.command()
def run(root: Path=Path("data/dfm14/gpu-ready"), generation: Path=Path("data/dfm14/generation-calibration-v1"),
        teacher: Path=TEACHER, audit_only: bool=False):
    from transformers import AutoTokenizer
    manifest=load(root/"manifest.json")
    gen = dict(groups=[], rows=0) if audit_only else load(generation/"manifest.json")
    if manifest["status"]!="ready_for_gpu_audit" or (not audit_only and gen["source_manifest_sha256"]!=file_hash(root/"manifest.json")):
        raise ValueError("Handoff manifests do not agree")
    training_path=load("data/dfm14/cpu-preparation-expanded/configuration.json")["tokenizer"]["tokenizer_path"]
    training,served=load(training_path),load(teacher/"tokenizer.json")
    keys=("model","normalizer","pre_tokenizer","added_tokens")
    if any(training[k]!=served[k] for k in keys):
        raise ValueError("Teacher tokenization differs; recount all audit prompts")
    tokenizer=AutoTokenizer.from_pretrained(str(teacher),local_files_only=True,fix_mistral_regex=True)
    audit_checks=[]
    # Every language/task has context/header smoke checks; all bodies were bounded
    # at 28K with the identical tokenizer core during full CPU preparation.
    groups={}
    for chunk in manifest["chunks"]:
        groups.setdefault((chunk["language"],chunk["task"]),[]).append(chunk)
    for key,chunks in sorted(groups.items()):
        for chunk in (chunks[0],chunks[len(chunks)//2],chunks[-1]):
            path=root/chunk["input"]
            if file_hash(path)!=chunk["sha256"]:
                raise ValueError("Changed audit sample chunk")
            row=next(rows(path))
            actual=count(tokenizer,messages(row))
            overhead=actual-row["audit_prompt_tokens"]
            if overhead>2048 or actual+1024>32768:
                raise ValueError("Audit prompt exceeds conservative teacher budget")
            audit_checks.append(dict(language=key[0],task=key[1],audit_id=row["audit_id"],prompt_tokens=actual,overhead=overhead))
    generation_checks=[]
    for group in gen["groups"]:
        if file_hash(group["path"])!=group["sha256"]:
            raise ValueError("Changed generation requests")
        largest=0
        for row in rows(group["path"]):
            payload=row["request"]
            actual=count(tokenizer,payload["messages"])
            if actual+payload["max_tokens"]>32768:
                raise ValueError("Generation prompt exceeds teacher context; never truncate")
            largest=max(largest,actual+payload["max_tokens"])
        generation_checks.append(dict(language=group["language"],family=group["family"],max_total_tokens=largest,rows=group["rows"]))
    result=dict(status="cpu_complete_ready_for_gpu",manifest_sha256=file_hash(root/"manifest.json"),
        audit_protocol_module='dfm14.audit_protocol_extended',
        generation_manifest_sha256=None if audit_only else file_hash(generation/"manifest.json"),teacher=str(teacher),
        teacher_pins={name:file_hash(teacher/name) for name in ("config.json","tokenizer.json","tokenizer_config.json")},
        equivalent_tokenizer_core=list(keys),audit_context_samples=audit_checks,generation_context_checks=generation_checks,
        audit_rows=manifest["rows"],audit_chunks=len(manifest["chunks"]),generation_requests=gen["rows"],
        gpu_work_started=False,training_ready=False)
    write_json(root/"readiness.json",result)
    print(json.dumps({k:v for k,v in result.items() if k not in ("audit_context_samples","generation_context_checks","teacher_pins")}),flush=True)


if __name__=="__main__":
    app()
