"""Bounded-memory HF tokenizer driver for historical HRM parquet inputs.

Preserves data_io's HRM token layout. Does not apply chat templates or truncate.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
import hashlib
import gzip
import json
import os
from pathlib import Path
import shutil
import tempfile

import numpy as np
import pyarrow.parquet as pq
from tokenizers import Tokenizer

CONDITIONS = dict(cot="<|object_ref_end|>", noisy="<|quad_start|>",
                  synth="<|quad_end|>", direct="<|object_ref_start|>")
DTYPES = dict(tokens="<u4", inst_start="<u8", inst_len="<u8",
              resp_start="<u8", resp_len="<u8")


def row_batches(path):
    if path.suffix == ".parquet":
        for batch in pq.ParquetFile(path).iter_batches(
                batch_size=256, columns=["condition", "instruction", "response"]):
            yield batch.to_pylist()
        return
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("response") is not None:
                yield [dict(condition=row.get("condition") or "direct",
                            instruction=row.get("instruction") or "", response=row["response"])]
                continue
            history = []
            for msg in row.get("messages") or []:
                content = msg.get("content", "")
                if msg["role"].lower() == "assistant" and content.strip():
                    reasoning = msg.get("reasoning_content", "").strip()
                    yield [dict(condition="direct", instruction="\n\n".join(history),
                                response=reasoning + "\n\n" + content.strip() if reasoning else content)]
                if content.strip():
                    role = msg["role"]
                    label = dict(system="System", user="User", assistant="Assistant", tool="Tool").get(
                        role.lower(), role)
                    history.append(label + ":\n" + content.strip())


def encode_row(tok, row):
    if any(not isinstance(row[k], str) for k in ("condition", "instruction", "response")):
        raise ValueError("Historical HRM rows require non-null strings")
    prefix = [tok.token_to_id("<|im_start|>")]
    prefix += [tok.token_to_id(CONDITIONS[c]) for c in row["condition"].split(",")]
    inst = prefix + tok.encode(row["instruction"], add_special_tokens=False).ids
    inst.append(tok.token_to_id("<|im_end|>"))
    resp = tok.encode(row["response"], add_special_tokens=False).ids
    resp.append(tok.token_to_id("<|box_end|>"))
    return inst, resp


def process_file(job):
    path, out, tokenizer_path, fingerprint = job
    path, out = Path(path), Path(out)
    stat = path.stat()
    metadata = dict(source_size=stat.st_size, source_mtime=int(stat.st_mtime))
    receipt = metadata | dict(tokenizer_sha256=fingerprint, driver="hf-hrm-v1")
    try:
        if json.loads((out / "hf_receipt.json").read_text()) == receipt:
            arrays = {k: np.load(out / f"{k}.npy", mmap_mode="r") for k in DTYPES}
            if all(v.ndim == 1 and v.dtype == np.dtype(DTYPES[k]) for k, v in arrays.items()):
                if len({len(v) for k, v in arrays.items() if k != "tokens"}) == 1:
                    return path.name, "cached"
    except (OSError, ValueError, EOFError):
        pass
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    tok = Tokenizer.from_file(str(tokenizer_path))
    tok.encode_special_tokens = True
    for special in ["<|im_start|>", "<|im_end|>", "<|box_end|>", *CONDITIONS.values()]:
        if tok.token_to_id(special) is None:
            raise ValueError(f"Missing token {special}")
    out.parent.mkdir(parents=True, exist_ok=True)
    # Interrupted staging directories must never look like sampler input tasks.
    temporary = Path(tempfile.mkdtemp(prefix=".hrm-", dir=out.parent.parent))
    try:
        counts = dict.fromkeys(DTYPES, 0)
        with ExitStack() as stack:
            files = {k: stack.enter_context((temporary / f"{k}.raw").open("wb")) for k in DTYPES}
            for batch in row_batches(path):
                buffers = {k: [] for k in DTYPES}
                for row in batch:
                    inst, resp = encode_row(tok, row)
                    start = counts["tokens"] + len(buffers["tokens"])
                    buffers["inst_start"].append(start)
                    buffers["inst_len"].append(len(inst))
                    buffers["resp_start"].append(start + len(inst))
                    buffers["resp_len"].append(len(resp))
                    buffers["tokens"].extend(inst)
                    buffers["tokens"].extend(resp)
                for k in DTYPES:
                    files[k].write(np.asarray(buffers[k], dtype=DTYPES[k]).tobytes())
                    counts[k] += len(buffers[k])
        for k, dtype in DTYPES.items():
            with (temporary / f"{k}.npy").open("wb") as target:
                np.lib.format.write_array_header_1_0(
                    target, dict(descr=dtype, fortran_order=False, shape=(counts[k],)))
                with (temporary / f"{k}.raw").open("rb") as source:
                    shutil.copyfileobj(source, target, length=8 * 1024 * 1024)
            (temporary / f"{k}.raw").unlink()
        if path.stat().st_size != stat.st_size or path.stat().st_mtime_ns != stat.st_mtime_ns:
            raise RuntimeError(f"Source changed while processing: {path}")
        (temporary / "metadata.json").write_text(json.dumps(metadata))
        (temporary / "hf_receipt.json").write_text(json.dumps(receipt))
        # Never merge partial arrays into a published result.
        if out.exists():
            shutil.rmtree(out)
        temporary.rename(out)
        return path.name, counts["inst_len"]
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output-dir", required=True, type=Path)
    parser.add_argument("--tokenizer-path", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    paths = sorted([*args.input.rglob("*.parquet"), *args.input.rglob("*.jsonl"),
                    *args.input.rglob("*.jsonl.gz")], key=lambda p: p.stat().st_size, reverse=True)
    if not paths:
        raise ValueError("No supported inputs")
    names = [str(p.relative_to(args.input)).replace("/", "__") for p in paths]
    if len(names) != len(set(names)):
        raise ValueError("Flattened output path collision")
    fingerprint = hashlib.sha256(args.tokenizer_path.read_bytes()).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Prevent concurrent drivers from replacing one another's outputs.
    import fcntl
    with (args.output_dir / ".hf-driver.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        jobs = [(str(p), str(args.output_dir / n), str(args.tokenizer_path), fingerprint)
                for p, n in zip(paths, names)]
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            from concurrent.futures import as_completed
            futures = [pool.submit(process_file, job) for job in jobs]
            for i, future in enumerate(as_completed(futures), 1):
                print(f"{i}/{len(jobs)} {future.result()}", flush=True)
        tok = Tokenizer.from_file(str(args.tokenizer_path))
        info = dict(tokenizer_path=str(args.tokenizer_path), template_mode="Hrm",
                    boq="<|im_start|>", eoq="<|im_end|>", eoa="<|box_end|>",
                    condition_mapping=CONDITIONS, vocab_size=tok.get_vocab_size(True))
        (args.output_dir / "tokenizer_info.json").write_text(json.dumps(info))


if __name__ == "__main__":
    main()
