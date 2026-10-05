#!/usr/bin/env python3
"""Compare actual vLLM launches without W&B or touching production servers."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time

import httpx
from transformers import AutoTokenizer


def cases():
    tool = {"type": "function", "function": {
        "name": "get_temperature", "description": "Get a city's temperature.",
        "parameters": {"type": "object", "properties": {
            "city": {"type": "string", "description": "City name"}}, "required": ["city"]}}}
    result = [
        {"id": "en_arithmetic", "messages": [{"role": "user", "content": "What is 17 + 25? Reply with only the number."}]},
        {"id": "da_arithmetic", "messages": [{"role": "user", "content": "Hvad er 17 + 25? Svar kun med tallet."}]},
        {"id": "en_summary", "messages": [{"role": "user", "content": "Summarize in one sentence: A storm damaged the town library on Monday. Volunteers repaired its roof on Tuesday. It reopened on Friday."}]},
        {"id": "da_summary", "messages": [{"role": "user", "content": "Opsummer i en enkelt s\u00e6tning: En storm beskadigede biblioteket mandag. Frivillige reparerede taget tirsdag. Biblioteket gen\u00e5bnede fredag."}]},
        {"id": "json", "messages": [{"role": "system", "content": "Respond with valid JSON only."}, {"role": "user", "content": 'Return an object with city set to Copenhagen and country set to Denmark.'}]},
        {"id": "multiturn", "messages": [{"role": "user", "content": "Remember the code 7381."}, {"role": "assistant", "content": "I will remember 7381."}, {"role": "user", "content": "What was the code? Reply only with the code."}]},
        {"id": "code", "messages": [{"role": "user", "content": "Write a Python function add(a, b) that returns their sum. Output only the code."}]},
        {"id": "tool_call", "tools": [tool], "messages": [{"role": "user", "content": "Use get_temperature to find the temperature in Copenhagen."}]},
        {"id": "tool_result_string", "tools": [tool], "messages": [
            {"role": "user", "content": "What is the temperature in Copenhagen?"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "get_temperature", "arguments": '{"city":"Copenhagen"}'}}]},
            {"role": "tool", "tool_call_id": "call_1", "name": "get_temperature", "content": '{"temperature":12,"unit":"C"}'}]},
    ]
    return result


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def template_comparison(model, template, output, examples):
    tokenizer = AutoTokenizer.from_pretrained(model, local_files_only=True)
    explicit = template.read_text()
    bundled = tokenizer.get_chat_template()
    checks = copy.deepcopy(examples)
    mapping = copy.deepcopy(checks[-1])
    mapping["id"] = "tool_result_mapping_local_only"
    mapping["messages"][-1]["content"] = {"temperature": 12, "unit": "C"}
    checks.append(mapping)
    rows = []
    for item in checks:
        row = {"id": item["id"]}
        for name, text in (("explicit", explicit), ("bundled", bundled)):
            try:
                kwargs = {"tools": item["tools"]} if "tools" in item else {}
                prompt = tokenizer.apply_chat_template(item["messages"], chat_template=text,
                                                       tokenize=False, add_generation_prompt=True, **kwargs)
                row[name] = {"prompt": prompt, "token_ids": tokenizer.encode(prompt, add_special_tokens=False)}
            except Exception as exc:
                row[name] = {"error": repr(exc)}
        row["identical"] = row["explicit"] == row["bundled"]
        rows.append(row)
    result = {"explicit_sha256": hashlib.sha256(explicit.encode()).hexdigest(),
              "bundled_sha256": hashlib.sha256(bundled.encode()).hexdigest(), "cases": rows}
    save(output / "templates.json", result)
    return result


def gpu_memory(gpu):
    result = subprocess.check_output(["nvidia-smi", "-i", str(gpu),
        "--query-gpu=memory.total,memory.free,memory.used", "--format=csv,noheader,nounits"], text=True)
    return dict(zip(("total_mib", "free_mib", "used_mib"), map(int, result.strip().split(","))))


def run_variant(args, name, eager, explicit, examples):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    before = gpu_memory(args.gpu)
    budget = before["total_mib"] * args.utilization
    if before["free_mib"] < budget + 4096:
        raise RuntimeError(f"Insufficient GPU margin: {before}, requested budget {budget}")
    command = [sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", str(args.model), "--served-model-name", "launch-smoke",
        "--host", "127.0.0.1", "--port", str(port), "--dtype", "bfloat16",
        "--attention-backend", "FLASH_ATTN", "--gpu-memory-utilization", str(args.utilization),
        "--max-model-len", "4096", "--max-num-batched-tokens", "4096", "--max-num-seqs", "2",
        "--enable-auto-tool-choice", "--tool-call-parser", "gemma4", "--seed", "0"]
    if eager:
        command.append("--enforce-eager")
    if explicit:
        command.extend(["--chat-template", str(args.template)])
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(args.gpu), OMP_NUM_THREADS="1",
               MKL_NUM_THREADS="1", WANDB_MODE="disabled", TOKENIZERS_PARALLELISM="false")
    env["PATH"] = str(Path(sys.executable).parent) + ":" + env.get("PATH", "")
    env["VLLM_USE_FLASHINFER_SAMPLER"] = "0"
    env["FLASHINFER_DISABLE_VERSION_CHECK"] = "1"
    if args.cuda_home:
        env["CUDA_HOME"] = env["CUDA_PATH"] = str(args.cuda_home)
        env["PATH"] = str(args.cuda_home / "bin") + ":" + env["PATH"]
    for key, subdir in (("VLLM_CACHE_ROOT", "vllm"), ("TORCHINDUCTOR_CACHE_DIR", "inductor"),
                        ("TRITON_CACHE_DIR", "triton"), ("CUDA_CACHE_PATH", "cuda")):
        path = (args.output / name / subdir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    result = {"command": command, "gpu_before": before, "requests": [], "memory_samples": []}
    stop = threading.Event()
    started = time.monotonic()
    with (args.output / f"{name}.server.log").open("w") as log:
        proc = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    result["pid"] = proc.pid

    def sample():
        while not stop.is_set():
            try:
                entry = gpu_memory(args.gpu)
                entry["elapsed_s"] = time.monotonic() - started
                usage = subprocess.check_output(["nvidia-smi", "--query-compute-apps=pid,used_memory",
                    "--format=csv,noheader,nounits"], text=True)
                owned = 0
                for line in usage.splitlines():
                    pid, memory = line.split(",")
                    try:
                        if os.getpgid(int(pid)) == proc.pid:
                            owned += int(memory)
                    except (ProcessLookupError, ValueError):
                        pass
                entry["server_processes_mib"] = owned
                result["memory_samples"].append(entry)
            except Exception as exc:
                result["memory_sample_error"] = repr(exc)
            stop.wait(2)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=180) as client:
            while True:
                if proc.poll() is not None:
                    raise RuntimeError(f"Server exited {proc.returncode}; see {name}.server.log")
                if time.monotonic() - started > args.startup_timeout:
                    raise TimeoutError("Server startup deadline exceeded")
                try:
                    if client.get("/health", timeout=2).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(2)
            result["startup_s"] = time.monotonic() - started
            print(f"{name}: ready after {result['startup_s']:.1f}s", flush=True)
            warmup = client.post("/v1/chat/completions", json={"model": "launch-smoke",
                "messages": [{"role": "user", "content": "Say hello."}], "temperature": 0, "max_tokens": 8})
            warmup.raise_for_status()
            for repeat in range(2):
                for item in examples:
                    payload = {k: v for k, v in item.items() if k != "id"}
                    payload.update(model="launch-smoke", temperature=0, seed=0,
                                   max_tokens=128, return_token_ids=True)
                    tick = time.monotonic()
                    response = client.post("/v1/chat/completions", json=payload)
                    row = {"id": item["id"], "repeat": repeat, "elapsed_s": time.monotonic() - tick,
                           "status": response.status_code, "response": response.json()}
                    result["requests"].append(row)
                    save(args.output / f"{name}.json", result)
                    print(f"{name}: round {repeat + 1} {item['id']} HTTP {response.status_code} {row['elapsed_s']:.2f}s", flush=True)
    except Exception as exc:
        result["error"] = repr(exc)
        print(f"{name}: {exc}", flush=True)
    finally:
        stop.set()
        sampler.join(timeout=10)
        # Signal only the session started above, never unrelated GPU processes.
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=10)
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        result["total_s"] = time.monotonic() - started
        save(args.output / f"{name}.json", result)
    time.sleep(5)
    return result


def main():
    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--template", type=Path, default=Path("evaluation/chat_templates/gemma4_native_chat.jinja"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gpu", type=int, default=7)
    parser.add_argument("--utilization", type=float, default=0.07)
    parser.add_argument("--startup-timeout", type=float, default=1200)
    parser.add_argument("--cuda-home", type=Path)
    args = parser.parse_args()
    args.model = args.model.resolve()
    args.template = args.template.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    examples = cases()
    save(args.output / "prompts.json", examples)
    templates = template_comparison(args.model, args.template, args.output, examples)
    print("Template comparisons: " + str([(row["id"], row["identical"]) for row in templates["cases"]]), flush=True)
    for name, eager, explicit in (("eager_explicit", True, True),
                                  ("non_eager_explicit", False, True),
                                  ("eager_bundled", True, False)):
        run_variant(args, name, eager, explicit, examples)


if __name__ == "__main__":
    main()
