#!/usr/bin/env python
"""Compare local HRM inference with a vLLM HF export on identical prompt IDs."""

from __future__ import annotations

import argparse
import gc
import sys
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from simple_inference_engine import (
    _batched_decode,
    _prefill,
    _sample,
    inference_load_checkpoint,
)


def parse_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "y"}


@torch.inference_mode()
def simple_generate_token_ids(
    ckpt_path: str,
    ckpt_tag: str | None,
    ckpt_epoch: int | None,
    use_ema: bool,
    condition: str,
    prompt: str,
    max_context: int,
    max_new_tokens: int,
) -> tuple[list[int], list[int], str]:
    ckpt = inference_load_checkpoint(
        ckpt_path,
        ckpt_epoch=ckpt_epoch,
        ckpt_use_ema=use_ema,
        ckpt_tag=ckpt_tag,
    )
    prompt_ids_np = ckpt.tokenize_prompt(condition, prompt)
    prompt_ids = [int(x) for x in prompt_ids_np.tolist()]
    if len(prompt_ids) >= max_context:
        raise ValueError(f"Prompt has {len(prompt_ids)} tokens, max_context is {max_context}")

    stop_token = int(ckpt.tokenizer.convert_tokens_to_ids(ckpt.tokenizer_info["eoa"]))
    cache = ckpt.model.create_cache(
        max_batch_size=1,
        max_seq_len=max_context,
        dtype=torch.bfloat16,
        device="cuda",
    )
    cache_lengths = torch.zeros(1, dtype=torch.int32, device="cuda")
    inputs = torch.tensor(prompt_ids, dtype=torch.long, device="cuda")

    token = _sample(_prefill(ckpt.model, ckpt.carry, inputs, cache), 0.0)
    cache_lengths[0] = len(prompt_ids)
    generated = [int(token.item())]

    while generated[-1] != stop_token and len(generated) < max_new_tokens:
        token = _sample(_batched_decode(ckpt.model, ckpt.carry, token, cache, cache_lengths), 0.0)
        cache_lengths.add_(1).clamp_max_(max_context - 1)
        generated.append(int(token.item()))

    text = ckpt.decode_generation(torch.tensor(generated).cpu().numpy(), stop_token)
    del ckpt, cache, cache_lengths, inputs, token
    gc.collect()
    torch.cuda.empty_cache()
    return prompt_ids, generated, text


def vllm_generate_token_ids(
    export_dir: str,
    prompt_ids: list[int],
    max_model_len: int,
    max_new_tokens: int,
    gpu_memory_utilization: float,
    enforce_eager: bool,
    attention_backend: str | None,
) -> tuple[list[int], str]:
    from vllm import LLM, SamplingParams
    from vllm.inputs import TokensPrompt

    kwargs = {}
    if attention_backend:
        kwargs["attention_backend"] = attention_backend

    llm = LLM(
        model=export_dir,
        dtype="bfloat16",
        max_model_len=max_model_len,
        gpu_memory_utilization=gpu_memory_utilization,
        enforce_eager=enforce_eager,
        trust_remote_code=False,
        **kwargs,
    )
    outputs = llm.generate(
        [TokensPrompt(prompt_token_ids=prompt_ids)],
        SamplingParams(
            max_tokens=max_new_tokens,
            temperature=0.0,
            skip_special_tokens=False,
        ),
    )
    completion = outputs[0].outputs[0]
    token_ids = [int(x) for x in completion.token_ids]
    return token_ids, completion.text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt-path", required=True)
    parser.add_argument("--ckpt-tag")
    parser.add_argument("--ckpt-epoch", type=int)
    parser.add_argument("--ckpt-use-ema", type=parse_bool, default=True)
    parser.add_argument("--export-dir", required=True)
    parser.add_argument("--condition", default="direct")
    parser.add_argument("--prompt", default="Write one short sentence about Denmark.")
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--max-context", type=int, default=256)
    parser.add_argument("--max-new-tokens", type=int, default=16)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.08)
    parser.add_argument("--enforce-eager", type=parse_bool, default=True)
    parser.add_argument("--attention-backend")
    args = parser.parse_args()

    if args.ckpt_tag and args.ckpt_epoch is not None:
        parser.error("Specify only one of --ckpt-tag and --ckpt-epoch")
    if not Path(args.export_dir).is_dir():
        parser.error(f"Export dir does not exist: {args.export_dir}")
    if args.prompt_file is not None:
        args.prompt = args.prompt_file.read_text(encoding="utf-8")

    prompt_ids, simple_ids, simple_text = simple_generate_token_ids(
        args.ckpt_path,
        args.ckpt_tag,
        args.ckpt_epoch,
        args.ckpt_use_ema,
        args.condition,
        args.prompt,
        args.max_context,
        args.max_new_tokens,
    )
    print(f"prompt_tokens ({len(prompt_ids)}): {prompt_ids}")
    print(f"simple_ids ({len(simple_ids)}): {simple_ids}")
    print(f"simple_text: {simple_text!r}")

    vllm_ids, vllm_text = vllm_generate_token_ids(
        args.export_dir,
        prompt_ids,
        args.max_context,
        args.max_new_tokens,
        args.gpu_memory_utilization,
        args.enforce_eager,
        args.attention_backend,
    )
    print(f"vllm_ids   ({len(vllm_ids)}): {vllm_ids}")
    print(f"vllm_text: {vllm_text!r}")

    same_prefix = 0
    for left, right in zip(simple_ids, vllm_ids):
        if left != right:
            break
        same_prefix += 1
    print(f"same_ids: {simple_ids == vllm_ids}")
    print(f"same_prefix_tokens: {same_prefix}/{min(len(simple_ids), len(vllm_ids))}")


if __name__ == "__main__":
    main()
