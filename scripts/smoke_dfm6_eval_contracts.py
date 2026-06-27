#!/usr/bin/env python3
"""Smoke-test the DFM6 evaluation contract before launching a checkpoint eval.

This is intentionally a contract test, not a miniature benchmark run.  It
checks the pieces that previously caused misleading metrics: tokenizer EOS
metadata, Gemma chat-template rendering, vLLM/native-proxy routing, task lists,
task-specific generation limits, BFCL tool-parser expansion, and average-job
dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import jinja2
import yaml
from transformers import AutoTokenizer

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEDULER_ROOT = REPO_ROOT / "eval_scheduler"
if str(SCHEDULER_ROOT) not in sys.path:
    sys.path.insert(0, str(SCHEDULER_ROOT))

from eval_scheduler.catalog import (
    DFM_DEFAULT,
    EUROEVAL_GROUPS,
    STANDARD_DEFAULT,
    dfm_shards,
    standard_shards,
)
from eval_scheduler.model import Action, JobStatus
from eval_scheduler.plan import PlanConfig, make_plan
from eval_scheduler.runtime import gemma_bfcl_vllm_extra_args


GEMMA_TURN_END_ID = 106
GEMMA_TEMPLATE = REPO_ROOT / "evaluation/chat_templates/gemma4_native_chat.jinja"
DATA_TEMPLATE = REPO_ROOT / "data_io/chat_templates/gemma4_native_chat.jinja"
DFM6_STANDARD_CONFIG = REPO_ROOT / "evaluation/config/dfm6_vllm_benchmarking.yaml"
DFM_SINGLE_CONFIG = REPO_ROOT / "config/dfm_evals_hrm_single_tasks.yaml"
DFM_IFEVAL_CONFIG = REPO_ROOT / "config/dfm_evals_hrm_ifeval_da_32_shards.yaml"


EXPECTED_STANDARD_GENERATION: dict[str, dict[str, Any]] = {
    "GSM8k": {"max_tokens": 512, "condition": "direct"},
    "MATH": {"max_tokens": 3072},
    "DROP": {"max_tokens": 64, "condition": "direct"},
    "GovReport": {"max_tokens": 512, "condition": "direct", "max_context": 4096},
    "NordjyllandNews": {"max_tokens": 128, "condition": "direct", "max_context": 4096},
    "MMLU": {"max_tokens": 1, "condition": "direct", "max_context": 4096, "batch_size": 1},
    "ARC": {"max_tokens": 1, "condition": "direct", "max_context": 4096, "batch_size": 1},
    "HellaSwag": {"max_tokens": 1, "condition": "direct", "max_context": 4096, "batch_size": 1},
    "Winogrande": {"max_tokens": 1, "condition": "direct", "max_context": 4096, "batch_size": 1},
    "BoolQ": {"max_tokens": 1, "condition": "direct", "max_context": 4096, "batch_size": 1},
}

EXPECTED_DFM_TASKS: dict[str, dict[str, Any]] = {
    "danish_citizen_tests": {"suite": "hrm_danish_danish_citizen_tests", "max_gen_toks": 512},
    "dala": {"suite": "hrm_danish_dala", "max_gen_toks": 512},
    "gec_dala": {"suite": "hrm_danish_gec_dala", "max_gen_toks": 512},
    "wmt24pp_en_da": {"suite": "hrm_danish_wmt24pp_en_da", "max_gen_toks": 512},
    "multi_wiki_qa": {"suite": "hrm_danish_multi_wiki_qa", "max_gen_toks": 32},
    "piqa": {"suite": "hrm_danish_piqa", "max_gen_toks": 8},
    "generative_talemaader": {"suite": "hrm_danish_generative_talemaader", "max_gen_toks": 128},
    "govreport": {
        "suite": "hrm_summarization_govreport",
        "max_gen_toks": 512,
        "task_args": {"max_report_chars=9000"},
    },
    "nordjyllandnews": {"suite": "hrm_summarization_nordjyllandnews", "max_gen_toks": 128},
    "humaneval": {"suite": "hrm_code_humaneval_local", "max_gen_toks": 512},
}


def fail(message: str) -> None:
    raise AssertionError(message)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_contains(haystack: str, needle: str, label: str) -> None:
    if needle not in haystack:
        fail(f"{label}: missing {needle!r}")


def assert_eq(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        fail(f"{label}: expected {expected!r}, got {actual!r}")


def render_gemma_smoke(export_dir: Path) -> dict[str, Any]:
    tokenizer = AutoTokenizer.from_pretrained(export_dir, use_fast=True)
    assert_eq(tokenizer.bos_token_id, 2, "tokenizer bos_token_id")
    assert_eq(tokenizer.eos_token_id, GEMMA_TURN_END_ID, "tokenizer eos_token_id")
    assert_eq(tokenizer.pad_token_id, 0, "tokenizer pad_token_id")
    assert_eq(tokenizer.eos_token, "<turn|>", "tokenizer eos_token")
    if not getattr(tokenizer, "chat_template", None):
        fail("export tokenizer is missing chat_template")

    hf_config = json.loads((export_dir / "config.json").read_text(encoding="utf-8"))
    assert_eq(hf_config.get("bos_token_id"), 2, "HF config bos_token_id")
    assert_eq(hf_config.get("eos_token_id"), GEMMA_TURN_END_ID, "HF config eos_token_id")
    assert_eq(hf_config.get("pad_token_id"), 0, "HF config pad_token_id")
    tokenizer_config = json.loads((export_dir / "tokenizer_config.json").read_text(encoding="utf-8"))
    assert_eq(tokenizer_config.get("fix_mistral_regex"), True, "tokenizer_config fix_mistral_regex")

    template = jinja2.Environment().from_string(GEMMA_TEMPLATE.read_text(encoding="utf-8"))
    prompt = "What is tested by this smoke test?"
    rendered = template.render(
        messages=[{"role": "user", "content": prompt}],
        tools=None,
        add_generation_prompt=True,
        enable_thinking=False,
        bos_token=tokenizer.bos_token or "",
        eos_token=tokenizer.eos_token or "",
    )
    assert_contains(rendered, "<bos>", "rendered prompt")
    assert_contains(rendered, "<|turn>user", "rendered prompt")
    assert_contains(rendered, prompt, "rendered prompt")
    assert_contains(rendered, "<turn|>", "rendered prompt")
    if not rendered.rstrip().endswith("<|turn>model"):
        fail("rendered Gemma prompt does not end with the generation marker '<|turn>model'")

    eval_hash = sha256(GEMMA_TEMPLATE)
    data_hash = sha256(DATA_TEMPLATE)
    assert_eq(eval_hash, data_hash, "evaluation/data chat template hash")
    return {
        "bos_token_id": tokenizer.bos_token_id,
        "eos_token_id": tokenizer.eos_token_id,
        "pad_token_id": tokenizer.pad_token_id,
        "template_sha256": eval_hash,
        "rendered_excerpt": rendered[:220],
    }


def audit_standard_config() -> dict[str, Any]:
    cfg = load_yaml(DFM6_STANDARD_CONFIG)
    assert_eq(cfg.get("engine"), "VLLMEngine", "standard config engine")
    assert_eq(cfg.get("prompt_mode"), "gemma_chat", "standard prompt_mode")
    assert_eq(cfg.get("chat_template_path"), "evaluation/chat_templates/gemma4_native_chat.jinja", "standard template path")
    gen = cfg.get("generation_config") or {}
    assert_eq(gen.get("stop_token_ids"), [GEMMA_TURN_END_ID], "standard stop_token_ids")
    assert_eq(gen.get("temperature"), 0.0, "standard temperature")

    benchmarks = cfg.get("benchmarks") or []
    names = [item["name"] for item in benchmarks]
    assert_eq(set(names), set(EXPECTED_STANDARD_GENERATION), "standard benchmark set")

    base = dict(gen)
    overrides_by_name = {item["name"]: item.get("generation_config") or {} for item in benchmarks}
    # Static class-level overrides copied from evaluation/benchmarks.py.
    class_overrides = {
        "GovReport": {"condition": "direct", "max_context": 4096, "max_tokens": 512, "batch_size": 2},
        "NordjyllandNews": {"condition": "direct", "max_context": 4096, "max_tokens": 128, "batch_size": 8},
        "MMLU": {"max_tokens": 1},
        "ARC": {"max_tokens": 1},
        "HellaSwag": {"max_tokens": 1},
        "Winogrande": {"max_tokens": 1},
        "BoolQ": {"max_tokens": 1},
    }
    effective: dict[str, dict[str, Any]] = {}
    for name in names:
        merged = base | class_overrides.get(name, {}) | overrides_by_name.get(name, {})
        expected = EXPECTED_STANDARD_GENERATION[name]
        for key, value in expected.items():
            assert_eq(merged.get(key), value, f"standard {name} generation_config.{key}")
        effective[name] = {key: merged.get(key) for key in sorted(set(expected) | {"stop_token_ids", "temperature"})}

    return {
        "tasks": names,
        "effective_generation": effective,
    }


def _task_entry(task: Any) -> tuple[str, list[str]]:
    if isinstance(task, str):
        return task, []
    return task["name"], [str(part) for part in task.get("args") or []]


def audit_dfm_configs() -> dict[str, Any]:
    cfg = load_yaml(DFM_SINGLE_CONFIG)
    sets = cfg["sets"]
    assert_eq(set(DFM_DEFAULT), set(EXPECTED_DFM_TASKS), "DFM task set")
    details: dict[str, Any] = {}

    for task, expected in EXPECTED_DFM_TASKS.items():
        suite = expected["suite"]
        if suite not in sets:
            fail(f"DFM suite {suite!r} for task {task!r} missing")
        suite_cfg = sets[suite]
        task_name, args = _task_entry(suite_cfg["tasks"][0])
        for required in ("--model", "{{target_model}}", "--sample-shuffle", "4242", "--temperature", "0"):
            if required not in suite_cfg["args"]:
                fail(f"DFM suite {suite}: missing runner arg {required!r}")
        expected_max = expected["max_gen_toks"]
        if expected_max != 512:
            assert_contains(" ".join(args), f"max_gen_toks={expected_max}", f"DFM suite {suite}")
        if "task_args" in expected:
            for arg in expected["task_args"]:
                assert_contains(" ".join(args), arg, f"DFM suite {suite}")
        details[task] = {
            "suite": suite,
            "inspect_task": task_name,
            "args": args,
            "shards": dfm_shards(task),
        }

    ifeval = load_yaml(DFM_IFEVAL_CONFIG)["sets"]
    assert_eq(len(ifeval), 32, "DFM IFEval shard count")
    for shard in range(32):
        suite = f"hrm_danish_ifeval_da_shard_{shard}_of_32"
        if suite not in ifeval:
            fail(f"missing {suite}")
        _, args = _task_entry(ifeval[suite]["tasks"][0])
        joined = " ".join(args)
        assert_contains(joined, "num_shards=32", suite)
        assert_contains(joined, f"shard_index={shard}", suite)
    return {"tasks": details, "ifeval_shards": 32}


def audit_plan(export_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    cfg = PlanConfig(
        plan_dir=Path(args.plan_dir),
        ckpt_path=args.ckpt_path,
        ckpt_tag=args.ckpt_tag,
        eval_epoch=args.eval_epoch,
        log_root=args.log_root,
        dfm_log_root=args.dfm_log_root,
        euroeval_log_root=args.euroeval_log_root,
        wandb_project=args.wandb_project,
        wandb_run_id=args.wandb_run_id,
        wandb_run_name=args.wandb_run_name,
        model_prefix=args.model_prefix,
        run_euroeval=True,
        queue_order="euroeval-first",
        dfm_ifeval_shards=32,
        max_retries=5,
        standard_config=str(DFM6_STANDARD_CONFIG.relative_to(REPO_ROOT)),
        standard_engine_backend="vllm",
        standard_hf_export_dir=str(export_dir),
        hrm_server_backend="vllm",
        hrm_hf_export_dir=str(export_dir),
        hrm_vllm_native_proxy=True,
        hrm_vllm_gemma_bfcl_tools=True,
        hrm_vllm_gemma_bfcl_tool_mode="parser",
        vllm_dtype="bfloat16",
        vllm_max_model_len=4096,
        vllm_gpu_memory_utilization=0.28,
        vllm_attention_backend="FLASH_ATTN",
        vllm_extra_args=f"--enforce-eager --attention-backend FLASH_ATTN --chat-template {GEMMA_TEMPLATE}",
        euroeval_max_concurrent_calls=32,
        judge_model="openai/gemma-4-e4b-judge",
        judge_server_model="unsloth/gemma-4-E4B-it",
        judged_max_connections=16,
        judged_batch=16,
        judged_vllm_gpu_memory_utilization=0.18,
        govreport_max_report_chars=9000,
        checkpoint_wait_seconds=60,
    )
    jobs = make_plan(cfg)
    by_action = {}
    for job in jobs:
        by_action[job.action.value] = by_action.get(job.action.value, 0) + 1

    expected_standard_eval_jobs = sum(standard_shards(task) for task in STANDARD_DEFAULT)
    expected_dfm_eval_jobs = sum(dfm_shards(task) for task in DFM_DEFAULT)
    assert_eq(by_action.get(Action.EVAL_STANDARD.value), expected_standard_eval_jobs, "standard eval job count")
    assert_eq(by_action.get(Action.EVAL_DFM.value), expected_dfm_eval_jobs, "DFM eval job count")
    assert_eq(by_action.get(Action.EVAL_DFM_IFEVAL.value), 32, "DFM IFEval job count")
    assert_eq(
        by_action.get(Action.EVAL_EUROEVAL.value, 0) + by_action.get(Action.EVAL_EUROEVAL_BATCHED_IFEVAL.value, 0),
        len(EUROEVAL_GROUPS),
        "EuroEval job count",
    )

    standard_jobs = [job for job in jobs if job.action == Action.EVAL_STANDARD]
    dfm_jobs = [job for job in jobs if job.action == Action.EVAL_DFM]
    ifeval_jobs = [job for job in jobs if job.action == Action.EVAL_DFM_IFEVAL]
    euro_jobs = [job for job in jobs if job.family == "euroeval" and job.action.value.startswith("eval_")]
    eval_jobs = standard_jobs + dfm_jobs + ifeval_jobs + euro_jobs

    for job in eval_jobs:
        meta = job.metadata
        assert_eq(meta.get("standard_engine_backend"), "vllm", f"{job.job_id} standard backend")
        assert_eq(meta.get("hrm_server_backend"), "vllm", f"{job.job_id} HRM backend")
        assert_eq(meta.get("hrm_vllm_native_proxy"), True, f"{job.job_id} native proxy")
        assert_eq(meta.get("hrm_vllm_gemma_bfcl_tools"), True, f"{job.job_id} BFCL tools")
        assert_eq(meta.get("hrm_vllm_gemma_bfcl_tool_mode"), "parser", f"{job.job_id} BFCL tool mode")
        assert_eq(meta.get("standard_config"), "evaluation/config/dfm6_vllm_benchmarking.yaml", f"{job.job_id} standard config")
        assert_eq(meta.get("standard_hf_export_dir"), str(export_dir), f"{job.job_id} standard export dir")
        assert_eq(meta.get("hrm_hf_export_dir"), str(export_dir), f"{job.job_id} HRM export dir")
        expected_util = 0.18 if job.name == "generative_talemaader" else 0.28
        assert_eq(meta.get("vllm_gpu_memory_utilization"), expected_util, f"{job.job_id} vLLM utilization")
        assert_eq(meta.get("vllm_max_model_len"), 4096, f"{job.job_id} max model length")
        assert_eq(meta.get("vllm_attention_backend"), "FLASH_ATTN", f"{job.job_id} attention backend")
        assert_contains(str(meta.get("vllm_extra_args", "")), "--enforce-eager", f"{job.job_id} vLLM extra args")
        assert_contains(str(meta.get("vllm_extra_args", "")), "--attention-backend FLASH_ATTN", f"{job.job_id} vLLM extra args")
        assert_contains(str(meta.get("vllm_extra_args", "")), str(GEMMA_TEMPLATE), f"{job.job_id} vLLM extra args")

    for job in dfm_jobs:
        if job.name == "generative_talemaader":
            assert_eq(job.initial_batch, 16, f"{job.job_id} judged batch")
            assert_eq(job.metadata.get("max_connections"), 16, f"{job.job_id} judged max_connections")
            assert_eq(job.metadata.get("vllm_gpu_memory_utilization"), 0.18, f"{job.job_id} judged utilization")
            assert_eq(job.metadata.get("judge_model"), "openai/gemma-4-e4b-judge", f"{job.job_id} judge model")
            assert_eq(job.metadata.get("judge_server_model"), "unsloth/gemma-4-E4B-it", f"{job.job_id} judge server")
        if job.name == "govreport":
            assert_eq(job.metadata.get("dfm_task_args"), ["max_report_chars=9000"], f"{job.job_id} govreport args")

    for job in euro_jobs:
        if job.name in {"ifeval", "ifeval-da"}:
            assert_eq(job.action, Action.EVAL_EUROEVAL_BATCHED_IFEVAL, f"{job.job_id} batched EuroEval IFEval")
        if job.name == "valeu-da":
            assert_eq(job.status, JobStatus.SKIPPED, "EuroEval valeu-da status")
        if job.name == "bfcl-v2":
            expanded = shlex.split(gemma_bfcl_vllm_extra_args(job, True))
            for token in ("--enable-auto-tool-choice", "--tool-call-parser", "gemma4"):
                if token not in expanded:
                    fail(f"BFCL vLLM extra args missing {token!r}: {expanded}")

    average_jobs = {job.name: job for job in jobs if job.action == Action.AVERAGE}
    for name in ("standard-average", "dfm-average", "euroeval-average"):
        assert_eq(average_jobs[name].metadata.get("average_prefix"), "suite_avg_v2", f"{name} prefix")
    for name in ("danish-average", "english-average", "math-code-average", "headline-averages"):
        assert_eq(average_jobs[name].metadata.get("average_prefix"), "headline_avg_v2", f"{name} prefix")
    headline_deps = set(average_jobs["headline-averages"].deps)
    expected_headline_deps = {
        average_jobs["standard-average"].job_id,
        average_jobs["dfm-average"].job_id,
        average_jobs["euroeval-average"].job_id,
        average_jobs["danish-average"].job_id,
        average_jobs["english-average"].job_id,
        average_jobs["math-code-average"].job_id,
    }
    assert_eq(headline_deps, expected_headline_deps, "headline average deps")

    return {
        "plan_config": asdict(cfg),
        "job_counts": by_action,
        "standard_tasks": STANDARD_DEFAULT,
        "dfm_tasks": DFM_DEFAULT,
        "euroeval_groups": EUROEVAL_GROUPS,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-dir", default="/work/dfm/HRM-Text/exports/dfm6_XL_gas2_step_300000_ema_hf")
    parser.add_argument("--ckpt-path", default="checkpoints/dfm6/XL-gas2")
    parser.add_argument("--ckpt-tag", default="step_300000")
    parser.add_argument("--eval-epoch", type=float, default=1.2518828862576779)
    parser.add_argument("--plan-dir", default="logs/scheduler/dfm6_XL_gas2_step300000_stopfix_smoke")
    parser.add_argument("--log-root", default="logs/eval/dfm6_XL_gas2_step300000_stopfix_smoke")
    parser.add_argument("--dfm-log-root", default="logs/dfm_evals/dfm6_XL_gas2_step300000_stopfix_smoke")
    parser.add_argument("--euroeval-log-root", default="logs/euroeval/dfm6_XL_gas2_step300000_stopfix_smoke")
    parser.add_argument("--wandb-project", default="DFM5")
    parser.add_argument("--wandb-run-id", default="dfm6-xl-gas2-300k-stopfix-smoke")
    parser.add_argument("--wandb-run-name", default="dfm6-XL-gas2 300K stopfix smoke")
    parser.add_argument("--model-prefix", default="hrm-dfm6-XL-gas2-stopfix-vllm-native-proxy")
    parser.add_argument("--json-out", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    export_dir = Path(args.export_dir)
    if not export_dir.is_dir():
        fail(f"export dir does not exist: {export_dir}")
    if not (export_dir / "model.safetensors").is_file():
        fail(f"export dir is missing model.safetensors: {export_dir}")

    report = {
        "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "export_dir": str(export_dir),
        "template": render_gemma_smoke(export_dir),
        "standard": audit_standard_config(),
        "dfm": audit_dfm_configs(),
        "plan": audit_plan(export_dir, args),
    }

    out = Path(args.json_out) if args.json_out else REPO_ROOT / "logs/smoke" / f"dfm6_eval_contracts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"DFM6 eval smoke passed. Wrote {out}")
    print(f"Standard tasks: {len(report['standard']['tasks'])}")
    print(f"DFM tasks: {len(report['dfm']['tasks'])} + {report['dfm']['ifeval_shards']} IFEval shards")
    print(f"EuroEval groups: {len(report['plan']['euroeval_groups'])} (valeu-da skipped by plan)")


if __name__ == "__main__":
    main()
