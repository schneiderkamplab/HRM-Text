#!/usr/bin/env python3
"""Small OpenAI-compatible chat server for local Transformers judge models."""

from __future__ import annotations

import argparse
import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any

import torch
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field
from transformers import AutoModelForImageTextToText, AutoProcessor


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    max_tokens: int | None = Field(default=256)
    temperature: float | None = Field(default=0.0)
    top_p: float | None = Field(default=None)
    stop: str | list[str] | None = Field(default=None)


def _message_content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") in {"text", "input_text"}:
                    parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return str(content)


def _trim_stops(text: str, stop: str | list[str] | None) -> str:
    stops = [stop] if isinstance(stop, str) else (stop or [])
    cut = len(text)
    for marker in stops:
        if not marker:
            continue
        pos = text.find(marker)
        if pos >= 0:
            cut = min(cut, pos)
    return text[:cut]


def build_app(args: argparse.Namespace) -> FastAPI:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dtype = getattr(torch, args.dtype)
    processor = AutoProcessor.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(
        args.model,
        torch_dtype=dtype,
        trust_remote_code=True,
        attn_implementation=args.attn_implementation,
    ).to(device)
    model.eval()
    tokenizer = processor.tokenizer
    lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield

    app = FastAPI(lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/models")
    async def models() -> dict[str, Any]:
        return {
            "object": "list",
            "data": [
                {
                    "id": args.served_model_name,
                    "object": "model",
                    "created": 0,
                    "owned_by": "local",
                }
            ],
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(request: ChatCompletionRequest) -> dict[str, Any]:
        messages = [
            {"role": message.role, "content": _message_content_to_text(message.content)}
            for message in request.messages
        ]
        max_new_tokens = max(1, min(request.max_tokens or 256, args.max_new_tokens))
        temperature = request.temperature if request.temperature is not None else 0.0
        do_sample = temperature > 0

        async with lock:
            prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            inputs = processor(text=[prompt], return_tensors="pt").to(device)
            generate_kwargs: dict[str, Any] = {
                "max_new_tokens": max_new_tokens,
                "do_sample": do_sample,
                "pad_token_id": tokenizer.eos_token_id,
            }
            if do_sample:
                generate_kwargs["temperature"] = temperature
                if request.top_p is not None:
                    generate_kwargs["top_p"] = request.top_p
            with torch.inference_mode():
                output_ids = model.generate(**inputs, **generate_kwargs)
            prompt_len = inputs["input_ids"].shape[-1]
            generated = output_ids[0, prompt_len:]
            text = tokenizer.decode(generated, skip_special_tokens=True)
            text = _trim_stops(text, request.stop)

        created = int(time.time())
        return {
            "id": f"chatcmpl-{created}",
            "object": "chat.completion",
            "created": created,
            "model": args.served_model_name,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": int(inputs["input_ids"].numel()),
                "completion_tokens": int(generated.numel()),
                "total_tokens": int(inputs["input_ids"].numel() + generated.numel()),
            },
        }

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("--served-model-name", default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float16", "float32"])
    parser.add_argument("--attn-implementation", default="sdpa", choices=["sdpa", "eager"])
    parser.add_argument("--max-new-tokens", type=int, default=512)
    args = parser.parse_args()
    args.served_model_name = args.served_model_name or args.model
    return args


def main() -> None:
    args = parse_args()
    uvicorn.run(build_app(args), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
