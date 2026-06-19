#!/usr/bin/env python3
"""Proxy OpenAI-compatible requests while matching the native HRM shim semantics."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18081)
    parser.add_argument("--target-base-url", required=True, help="Target OpenAI base URL, e.g. http://127.0.0.1:9700/v1")
    parser.add_argument("--model-name", required=True, help="Model name exposed by this proxy")
    parser.add_argument("--target-model-name", default=None, help="Model name served by the target; defaults to --model-name")
    parser.add_argument("--api-key", default="inspectai")
    parser.add_argument("--log-jsonl", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=600.0)
    return parser.parse_args()


def content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return str(content)


def messages_to_prompt(messages: list[dict[str, Any]]) -> str:
    rendered: list[str] = []
    for msg in messages:
        text = content_to_text(msg.get("content")).strip()
        if not text:
            continue
        if msg.get("role") == "user":
            rendered.append(text)
        else:
            rendered.append(f"{msg.get('role')}: {text}")
    return "\n\n".join(rendered).strip()


def normalize_stop(stop: Any) -> Any:
    # The native shim treats an empty stop list as no effective stop marker.
    if stop == []:
        return None
    return stop


def make_app(args: argparse.Namespace) -> FastAPI:
    app = FastAPI(title="Native-compatible OpenAI proxy for HRM")
    target_base = args.target_base_url.rstrip("/")
    target_model = args.target_model_name or args.model_name
    if args.log_jsonl is not None:
        args.log_jsonl.parent.mkdir(parents=True, exist_ok=True)

    def log_record(record: dict[str, Any]) -> None:
        if args.log_jsonl is None:
            return
        with args.log_jsonl.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    async def post_json(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=args.timeout) as client:
                response = await client.post(
                    f"{target_base}{endpoint}",
                    json=payload,
                    headers={"Authorization": f"Bearer {args.api_key}"},
                )
            if response.status_code >= 400:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return response.json()
        except HTTPException:
            raise
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail=str(exc)) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "model": args.model_name, "target": target_base}

    @app.get("/v1/models")
    def models() -> dict[str, list[dict[str, str]]]:
        return {"data": [{"id": args.model_name, "object": "model"}]}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> dict[str, Any]:
        incoming = await request.json()
        if incoming.get("model") not in {args.model_name, f"openai/{args.model_name}"}:
            raise HTTPException(status_code=404, detail=f"Unknown model: {incoming.get('model')}")
        prompt = messages_to_prompt(incoming.get("messages", []))
        outgoing: dict[str, Any] = {
            "model": target_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": incoming.get("temperature", 0.0),
        }
        max_tokens = incoming.get("max_tokens", incoming.get("max_completion_tokens"))
        if max_tokens is not None:
            outgoing["max_tokens"] = max_tokens
        stop = normalize_stop(incoming.get("stop"))
        if stop is not None:
            outgoing["stop"] = stop

        log_record(
            {
                "time": time.time(),
                "endpoint": "/v1/chat/completions",
                "stripped_keys": sorted(set(incoming) - set(outgoing) - {"messages", "max_completion_tokens"}),
                "incoming_keys": sorted(incoming),
                "outgoing": outgoing,
            }
        )
        response = await post_json("/chat/completions", outgoing)
        response["model"] = args.model_name
        return response

    @app.post("/v1/completions")
    async def completions(request: Request) -> dict[str, Any]:
        incoming = await request.json()
        if incoming.get("model") not in {args.model_name, f"openai/{args.model_name}"}:
            raise HTTPException(status_code=404, detail=f"Unknown model: {incoming.get('model')}")
        outgoing: dict[str, Any] = {
            "model": target_model,
            "prompt": incoming.get("prompt", ""),
            "temperature": incoming.get("temperature", 0.0),
        }
        max_tokens = incoming.get("max_tokens", incoming.get("max_completion_tokens"))
        if max_tokens is not None:
            outgoing["max_tokens"] = max_tokens
        stop = normalize_stop(incoming.get("stop"))
        if stop is not None:
            outgoing["stop"] = stop

        log_record(
            {
                "time": time.time(),
                "endpoint": "/v1/completions",
                "stripped_keys": sorted(set(incoming) - set(outgoing) - {"max_completion_tokens"}),
                "incoming_keys": sorted(incoming),
                "outgoing": outgoing,
            }
        )
        response = await post_json("/completions", outgoing)
        response["model"] = args.model_name
        return response

    return app


def main() -> None:
    args = parse_args()
    uvicorn.run(make_app(args), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
