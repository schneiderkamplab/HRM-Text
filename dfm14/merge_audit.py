"""Join completed audit-input manifests, removing any cross-campaign duplicates."""
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

import typer

from dfm12.io import atomic, file_hash, load, lock, rows, write_json
from dfm14.audit_protocol import POLICY
from dfm14.prepare_gpu import source_hold

app = typer.Typer()


@app.command()
def run(roots: list[Path] = typer.Option(...,"--root"), output: Path = Path("data/dfm14/gpu-ready")):
    with lock(output/".lock"):
        if (output/"manifest.json").exists():
            raise ValueError("Final manifest already exists; do not overwrite")
        seen, chunks, counts, duplicates, inputs = set(), [], defaultdict(Counter), 0, []
        held = Counter()
        for index,root in enumerate(roots):
            manifest=load(root/"manifest.json")
            if manifest["status"] != "ready_for_gpu_audit" or manifest["policy"] != POLICY:
                raise ValueError("Unfinished or incompatible audit input")
            inputs.append(dict(path=str((root/"manifest.json").resolve()),sha256=file_hash(root/"manifest.json")))
            for chunk in manifest["chunks"]:
                source=root/chunk["input"]
                if file_hash(source)!=chunk["sha256"]:
                    raise ValueError("Changed source chunk")
                all_rows=list(rows(source))
                if len(all_rows)!=chunk["rows"]:
                    raise ValueError("Chunk row count mismatch")
                kept=[]
                for row in all_rows:
                    if reason := source_hold(row):
                        held[reason] += 1
                        continue
                    if row["audit_id"] in seen:
                        duplicates+=1
                        continue
                    seen.add(row["audit_id"])
                    kept.append(row)
                    counts[row["language"]][row["task"]]+=1
                if not kept:
                    continue
                result=dict(chunk,job_id=f"input{index}-"+chunk["job_id"],input=str(source.resolve()))
                if len(kept)!=len(all_rows):
                    path=output/"deduplicated"/(result["job_id"]+".jsonl")
                    with atomic(path) as handle:
                        for row in kept:
                            handle.write(json.dumps(row,ensure_ascii=False)+"\n")
                    result.update(input=str(path.resolve()),rows=len(kept),sha256=file_hash(path))
                chunks.append(result)
                if len(chunks)%100==0:
                    progress=dict(chunks=len(chunks),rows=len(seen),duplicates=duplicates)
                    write_json(output/"progress.json",progress)
                    print(json.dumps(progress),flush=True)
        with atomic(output/"jobs.tsv") as handle:
            writer=csv.DictWriter(handle,fieldnames=list(chunks[0]),delimiter="\t")
            writer.writeheader()
            writer.writerows(chunks)
        result=dict(status="ready_for_gpu_audit",policy=POLICY,training_ready=False,inputs=inputs,
            rows=len(seen),cross_campaign_duplicates=duplicates,cpu_holds=dict(held),chunks=chunks,
            languages=dict(counts),remaining_gates=["GPU review/repair", "inherited/benchmark decontamination", "accepted export"])
        write_json(output/"manifest.json",result)
        write_json(output/"progress.json",dict(phase=result["status"],rows=len(seen),chunks=len(chunks),duplicates=duplicates))
        print(json.dumps(load(output/"progress.json")),flush=True)


if __name__=="__main__":
    app()
