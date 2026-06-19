#!/usr/bin/env python3
"""Capture OpenAI-compatible request payloads for eval debugging."""

from __future__ import annotations

import argparse
import json
import os
import signal
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--model-name", default="payload-capture")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-requests", type=int, default=20)
    parser.add_argument("--response", default="A")
    return parser.parse_args()


def make_app(args: argparse.Namespace) -> FastAPI:
    args.out.parent.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="OpenAI payload capture server")
    state = {"count": 0}

    def append_record(endpoint: str, payload: dict[str, Any]) -> None:
        state["count"] += 1
        record = {
            "time": time.time(),
            "index": state["count"],
            "endpoint": endpoint,
            "payload": payload,
        }
        with args.out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        if state["count"] >= args.max_requests:
            # Give the HTTP response time to flush, then stop the server process.
            threading.Timer(0.5, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "model": args.model_name}

    @app.get("/v1/models")
    def models() -> dict[str, list[dict[str, str]]]:
        return {"data": [{"id": args.model_name, "object": "model"}]}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> dict[str, Any]:
        payload = await request.json()
        append_record("/v1/chat/completions", payload)
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": args.model_name,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": args.response},
                    "finish_reason": "stop",
                }
            ],
        }

    @app.post("/v1/completions")
    async def completions(request: Request) -> dict[str, Any]:
        payload = await request.json()
        append_record("/v1/completions", payload)
        prompts = payload.get("prompt", "")
        count = len(prompts) if isinstance(prompts, list) else 1
        return {
            "id": f"cmpl-{uuid.uuid4().hex}",
            "object": "text_completion",
            "created": int(time.time()),
            "model": args.model_name,
            "choices": [
                {"index": idx, "text": args.response, "finish_reason": "stop"}
                for idx in range(count)
            ],
        }

    return app


def main() -> None:
    args = parse_args()
    uvicorn.run(make_app(args), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
