#!/usr/bin/env python3
"""Serve an HRM checkpoint through a small OpenAI-compatible API."""

from __future__ import annotations

import argparse
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.engines import SimpleEngine
from simple_inference_engine import normalize_checkpoint_tag


class ChatMessage(BaseModel):
    role: str
    content: str | list[dict[str, Any]] | None = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float = 0.0
    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    stop: str | list[str] | None = None

    @property
    def requested_max_tokens(self) -> int | None:
        return self.max_tokens if self.max_tokens is not None else self.max_completion_tokens


class CompletionRequest(BaseModel):
    model: str
    prompt: str | list[str]
    temperature: float = 0.0
    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    stop: str | list[str] | None = None

    @property
    def requested_max_tokens(self) -> int | None:
        return self.max_tokens if self.max_tokens is not None else self.max_completion_tokens


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ckpt-path", required=True)
    parser.add_argument("--ckpt-epoch", type=int, default=None)
    parser.add_argument("--ckpt-tag", default=None, help="Checkpoint tag such as epoch_1 or step_10000.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--batch-timeout-ms", type=float, default=25.0)
    parser.add_argument("--max-context", type=int, default=4096)
    parser.add_argument("--condition", default="direct")
    parser.add_argument("--no-ema", action="store_true")
    args = parser.parse_args()
    if args.ckpt_epoch is not None and args.ckpt_tag is not None:
        parser.error("Specify only one of --ckpt-epoch and --ckpt-tag")
    return args


def content_to_text(content: str | list[dict[str, Any]] | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for item in content:
        if item.get("type") == "text":
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)


def messages_to_prompt(messages: list[ChatMessage]) -> str:
    rendered: list[str] = []
    for msg in messages:
        text = content_to_text(msg.content).strip()
        if not text:
            continue
        if msg.role == "user":
            rendered.append(text)
        else:
            rendered.append(f"{msg.role}: {text}")
    return "\n\n".join(rendered).strip()


def apply_stop(text: str, stop: str | list[str] | None) -> str:
    if stop is None:
        return text
    stops = [stop] if isinstance(stop, str) else stop
    cut = len(text)
    for marker in stops:
        if not marker:
            continue
        idx = text.find(marker)
        if idx >= 0:
            cut = min(cut, idx)
    return text[:cut]


@dataclass
class GenerationJob:
    prompt: str
    max_tokens: int | None
    temperature: float
    stop: str | list[str] | None
    event: threading.Event
    output: str | None = None
    error: BaseException | None = None


class BatchGenerator:
    def __init__(self, engine: SimpleEngine, args: argparse.Namespace):
        self.engine = engine
        self.args = args
        self.condition = threading.Condition()
        self.queue: list[GenerationJob] = []
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def submit(
        self,
        prompt: str,
        *,
        max_tokens: int | None,
        temperature: float,
        stop: str | list[str] | None,
    ) -> str:
        job = GenerationJob(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop,
            event=threading.Event(),
        )
        with self.condition:
            self.queue.append(job)
            self.condition.notify()

        job.event.wait()
        if job.error is not None:
            raise job.error
        assert job.output is not None
        return job.output

    def _run(self) -> None:
        while True:
            batch = self._next_batch()
            first = batch[0]
            try:
                generation_tokens = first.max_tokens if first.max_tokens is not None else self.args.max_context
                outputs = self.engine.generate(
                    [job.prompt for job in batch],
                    batch_size=self.args.batch_size,
                    max_context=self.args.max_context,
                    max_tokens=min(generation_tokens, self.args.max_context),
                    temperature=first.temperature,
                    condition=self.args.condition,
                )
                for job, output in zip(batch, outputs, strict=True):
                    job.output = apply_stop(output, job.stop)
            except BaseException as exc:
                for job in batch:
                    job.error = exc
            finally:
                for job in batch:
                    job.event.set()

    def _next_batch(self) -> list[GenerationJob]:
        with self.condition:
            while not self.queue:
                self.condition.wait()

            first = self.queue.pop(0)
            batch = [first]
            deadline = time.monotonic() + self.args.batch_timeout_ms / 1000.0

            while len(batch) < self.args.batch_size:
                self._take_compatible(batch, first)
                if len(batch) >= self.args.batch_size:
                    break

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.condition.wait(timeout=remaining)

            self._take_compatible(batch, first)
            return batch

    def _take_compatible(self, batch: list[GenerationJob], first: GenerationJob) -> None:
        keep: list[GenerationJob] = []
        for job in self.queue:
            if len(batch) < self.args.batch_size and self._compatible(first, job):
                batch.append(job)
            else:
                keep.append(job)
        self.queue = keep

    @staticmethod
    def _compatible(first: GenerationJob, job: GenerationJob) -> bool:
        return (
            first.max_tokens == job.max_tokens
            and first.temperature == job.temperature
            and first.stop == job.stop
        )


def make_app(args: argparse.Namespace) -> FastAPI:
    ckpt_label = normalize_checkpoint_tag(args.ckpt_tag) if args.ckpt_tag is not None else (
        f"epoch_{args.ckpt_epoch}" if args.ckpt_epoch is not None else "latest"
    )
    model_name = args.model_name or f"hrm-{ckpt_label}"
    engine = SimpleEngine(
        ckpt_path=args.ckpt_path,
        ckpt_epoch=args.ckpt_epoch,
        ckpt_tag=args.ckpt_tag,
        ckpt_use_ema=not args.no_ema,
    )
    generator = BatchGenerator(engine, args)
    app = FastAPI(title="HRM OpenAI compatibility server")

    def generate(prompts: list[str], *, max_tokens: int | None, temperature: float, stop: str | list[str] | None) -> list[str]:
        return [
            generator.submit(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop,
            )
            for prompt in prompts
        ]

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "model": model_name, "checkpoint": ckpt_label}

    @app.get("/v1/models")
    def models() -> dict[str, list[dict[str, str]]]:
        return {"data": [{"id": model_name, "object": "model"}]}

    @app.post("/v1/chat/completions")
    def chat_completions(req: ChatCompletionRequest) -> dict[str, Any]:
        if req.model not in {model_name, f"openai/{model_name}"}:
            raise HTTPException(status_code=404, detail=f"Unknown model: {req.model}")
        prompt = messages_to_prompt(req.messages)
        output = generate(
            [prompt],
            max_tokens=req.requested_max_tokens,
            temperature=req.temperature,
            stop=req.stop,
        )[0]
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": output},
                    "finish_reason": "stop",
                }
            ],
        }

    @app.post("/v1/completions")
    def completions(req: CompletionRequest) -> dict[str, Any]:
        if req.model not in {model_name, f"openai/{model_name}"}:
            raise HTTPException(status_code=404, detail=f"Unknown model: {req.model}")
        prompts = [req.prompt] if isinstance(req.prompt, str) else req.prompt
        outputs = generate(
            prompts,
            max_tokens=req.requested_max_tokens,
            temperature=req.temperature,
            stop=req.stop,
        )
        return {
            "id": f"cmpl-{uuid.uuid4().hex}",
            "object": "text_completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [
                {"index": idx, "text": output, "finish_reason": "stop"}
                for idx, output in enumerate(outputs)
            ],
        }

    return app


def main() -> None:
    args = parse_args()
    uvicorn.run(make_app(args), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
