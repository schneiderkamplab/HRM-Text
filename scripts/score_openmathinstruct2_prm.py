#!/usr/bin/env python3
"""Score verified OpenMath CoT traces with Qwen2.5-Math-PRM via vLLM."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


SYSTEM_PROMPT = r"Please reason step by step, and put your final answer within \boxed{}."
SCORED_FIELDS = [
    ("prm_step_scores", pa.list_(pa.float32())),
    ("prm_min_score", pa.float32()),
    ("prm_mean_score", pa.float32()),
    ("prm_final_score", pa.float32()),
    ("prm_num_steps", pa.int32()),
    ("prm_prompt_tokens", pa.int32()),
    ("prm_status", pa.string()),
]
PARAGRAPH_RE = re.compile(r"\n\s*\n+")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/openmathinstruct2_repair/candidates"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/openmathinstruct2_repair/prm_scores"))
    parser.add_argument("--model", type=Path, default=Path("/work/dfm/models/Qwen2.5-Math-PRM-7B"))
    parser.add_argument("--gpus", default="0,1,2,3,4,5,6,7")
    parser.add_argument("--gpu", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--file-list", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.90)
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--max-num-seqs", type=int, default=512)
    parser.add_argument("--max-num-batched-tokens", type=int, default=262_144)
    parser.add_argument("--request-batch-size", type=int, default=2048)
    parser.add_argument("--max-rows-per-file", type=int, default=None)
    parser.add_argument("--enforce-eager", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def solution_steps(solution: str) -> list[str]:
    steps = [step.strip() for step in PARAGRAPH_RE.split(solution) if step.strip()]
    if len(steps) <= 1:
        steps = [step.strip() for step in solution.splitlines() if step.strip()]
    if not steps:
        steps = [solution.strip()]
    return steps


def prm_conversation(tokenizer: Any, problem: str, solution: str) -> str:
    response = "<extra_0>".join(solution_steps(solution)) + "<extra_0>"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": problem},
        {"role": "assistant", "content": response},
    ]
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)


def scored_schema(input_schema: pa.Schema) -> pa.Schema:
    return pa.schema(list(zip(input_schema.names, input_schema.types, strict=True)) + SCORED_FIELDS)


def append_result(columns: dict[str, list[Any]], row: dict[str, Any], result: dict[str, Any]) -> None:
    for key in row:
        columns[key].append(row[key])
    for key, _type in SCORED_FIELDS:
        columns[key].append(result[key])


def score_files(args: argparse.Namespace, files: list[Path]) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
    os.environ.setdefault("VLLM_ENABLE_V1_MULTIPROCESSING", "0")
    from transformers import AutoTokenizer
    from vllm import LLM

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    llm = LLM(
        model=str(args.model),
        runner="pooling",
        trust_remote_code=True,
        gpu_memory_utilization=args.gpu_memory_utilization,
        max_model_len=args.max_model_len,
        max_num_seqs=args.max_num_seqs,
        max_num_batched_tokens=args.max_num_batched_tokens,
        enforce_eager=args.enforce_eager,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for source in files:
        output = args.output_dir / source.name
        meta = output.with_suffix(output.suffix + ".meta.json")
        signature = {
            "source_size": source.stat().st_size,
            "source_mtime_ns": source.stat().st_mtime_ns,
            "model": str(args.model.resolve()),
            "max_model_len": args.max_model_len,
            "step_format": 1,
            "max_rows_per_file": args.max_rows_per_file,
        }
        if output.exists() and meta.exists() and not args.force:
            if json.loads(meta.read_text()).get("signature") == signature:
                print(f"GPU{args.gpu}: current {source.name}", flush=True)
                continue
        temporary = output.with_suffix(output.suffix + ".partial")
        temporary.unlink(missing_ok=True)
        parquet = pq.ParquetFile(source)
        schema = scored_schema(parquet.schema_arrow)
        writer = pq.ParquetWriter(temporary, schema, compression="zstd")
        stats = {"seen": 0, "scored": 0, "too_long": 0}
        started = time.monotonic()
        try:
            stop = False
            for batch in parquet.iter_batches(batch_size=args.request_batch_size):
                rows = batch.to_pylist()
                if args.max_rows_per_file is not None:
                    remaining = args.max_rows_per_file - stats["seen"]
                    if remaining <= 0:
                        break
                    rows = rows[:remaining]
                    stop = len(rows) < batch.num_rows
                stats["seen"] += len(rows)
                prompts = [prm_conversation(tokenizer, row["problem"], row["generated_solution"]) for row in rows]
                token_ids = tokenizer(prompts, add_special_tokens=False, padding=False)["input_ids"]
                valid_indices = [index for index, ids in enumerate(token_ids) if len(ids) <= args.max_model_len]
                valid_prompts = [{"prompt_token_ids": token_ids[index]} for index in valid_indices]
                outputs = llm.encode(valid_prompts, pooling_task="token_classify", use_tqdm=False) if valid_prompts else []
                by_index = dict(zip(valid_indices, outputs, strict=True))
                columns: dict[str, list[Any]] = {name: [] for name in schema.names}
                for index, (row, ids) in enumerate(zip(rows, token_ids, strict=True)):
                    if index not in by_index:
                        stats["too_long"] += 1
                        result = {
                            "prm_step_scores": [],
                            "prm_min_score": float("nan"),
                            "prm_mean_score": float("nan"),
                            "prm_final_score": float("nan"),
                            "prm_num_steps": 0,
                            "prm_prompt_tokens": len(ids),
                            "prm_status": "too_long",
                        }
                    else:
                        data = by_index[index].outputs.data.float().cpu()
                        scores = data[:, 1].tolist()
                        stats["scored"] += 1
                        result = {
                            "prm_step_scores": scores,
                            "prm_min_score": min(scores),
                            "prm_mean_score": sum(scores) / len(scores),
                            "prm_final_score": scores[-1],
                            "prm_num_steps": len(scores),
                            "prm_prompt_tokens": len(ids),
                            "prm_status": "scored",
                        }
                    append_result(columns, row, result)
                writer.write_table(pa.Table.from_pydict(columns, schema=schema))
                elapsed = time.monotonic() - started
                rate = stats["seen"] / elapsed if elapsed else 0.0
                print(
                    f"GPU{args.gpu}: {source.name} {stats['seen']:,}/{parquet.metadata.num_rows:,} "
                    f"rows {rate:.1f} rows/s",
                    flush=True,
                )
                if stop:
                    break
        finally:
            writer.close()
        temporary.replace(output)
        elapsed = time.monotonic() - started
        payload = {
            "signature": signature,
            "stats": stats | {"elapsed_seconds": elapsed, "rows_per_second": stats["seen"] / elapsed},
            "runtime": {
                "gpu": args.gpu,
                "gpu_memory_utilization": args.gpu_memory_utilization,
                "max_num_seqs": args.max_num_seqs,
                "max_num_batched_tokens": args.max_num_batched_tokens,
                "request_batch_size": args.request_batch_size,
            },
        }
        meta.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"GPU{args.gpu}: complete {source.name} {payload['stats']}", flush=True)


def launch(args: argparse.Namespace) -> None:
    files = sorted(args.input_dir.glob("train-*-of-00032.parquet"))
    if not files:
        raise SystemExit(f"No candidate shards under {args.input_dir}")
    gpus = [int(value) for value in args.gpus.split(",") if value.strip()]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = args.output_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    processes: list[tuple[int, subprocess.Popen[Any], Any]] = []
    for worker_index, gpu in enumerate(gpus):
        assigned = files[worker_index::len(gpus)]
        file_list = args.output_dir / f"gpu{gpu}.files"
        file_list.write_text("".join(f"{path.resolve()}\n" for path in assigned))
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--input-dir", str(args.input_dir),
            "--output-dir", str(args.output_dir),
            "--model", str(args.model),
            "--gpu", str(gpu),
            "--file-list", str(file_list),
            "--gpu-memory-utilization", str(args.gpu_memory_utilization),
            "--max-model-len", str(args.max_model_len),
            "--max-num-seqs", str(args.max_num_seqs),
            "--max-num-batched-tokens", str(args.max_num_batched_tokens),
            "--request-batch-size", str(args.request_batch_size),
        ]
        if args.max_rows_per_file is not None:
            command.extend(["--max-rows-per-file", str(args.max_rows_per_file)])
        if args.enforce_eager:
            command.append("--enforce-eager")
        if args.force:
            command.append("--force")
        log_handle = (log_dir / f"gpu{gpu}.log").open("a")
        process = subprocess.Popen(command, stdout=log_handle, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append((gpu, process, log_handle))
        print(f"GPU{gpu}: pid={process.pid} files={len(assigned)} log={log_handle.name}")
    failures = []
    for gpu, process, log_handle in processes:
        status = process.wait()
        log_handle.close()
        if status:
            failures.append((gpu, status))
    if failures:
        raise SystemExit(f"PRM workers failed: {failures}")


def main() -> None:
    args = arguments()
    if args.gpu is None:
        launch(args)
    else:
        if args.file_list is None:
            raise SystemExit("worker mode requires --file-list")
        files = [Path(line) for line in args.file_list.read_text().splitlines() if line.strip()]
        score_files(args, files)


if __name__ == "__main__":
    main()
