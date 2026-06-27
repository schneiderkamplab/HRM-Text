#!/usr/bin/env python3
"""Proxy OpenAI-compatible requests while matching the native HRM shim semantics."""

from __future__ import annotations

import argparse
import json
import re
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
    parser.add_argument(
        "--gemma-native-bfcl-tools",
        action="store_true",
        help=(
            "Detect EuroEval BFCL text prompts, pass functions as Gemma-native "
            "tools through the target chat template, and convert native tool "
            "calls back to BFCL JSON. Leave disabled for older text-only HRM "
            "evaluations."
        ),
    )
    parser.add_argument(
        "--gemma-native-bfcl-tools-as-text",
        action="store_true",
        help=(
            "Detect EuroEval BFCL text prompts and inject Gemma-native tool "
            "declarations as system text instead of sending OpenAI tools. This "
            "is a diagnostic path for comparing against vLLM's tool parser."
        ),
    )
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


def as_openai_tool(function: dict[str, Any]) -> dict[str, Any]:
    if function.get("type") == "function" and isinstance(function.get("function"), dict):
        return function
    return {"type": "function", "function": function}


def gemma_format_argument(value: Any, escape_keys: bool = True) -> str:
    if isinstance(value, str):
        return f'<|"|>{value}<|"|>'
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in sorted(value.items()):
            rendered_key = f'<|"|>{key}<|"|>' if escape_keys else str(key)
            parts.append(f"{rendered_key}:{gemma_format_argument(item, escape_keys=escape_keys)}")
        return "{" + ",".join(parts) + "}"
    if isinstance(value, list):
        return "[" + ",".join(gemma_format_argument(item, escape_keys=escape_keys) for item in value) + "]"
    return str(value)


def gemma_format_parameters(properties: dict[str, Any], required: list[str]) -> str:
    standard_keys = {"description", "type", "properties", "required", "nullable"}
    rendered: list[str] = []
    for key, value in sorted(properties.items()):
        if not isinstance(value, dict) or key in standard_keys:
            continue
        pieces: list[str] = []
        if value.get("description"):
            pieces.append(f'description:<|"|>{value["description"]}<|"|>')
        value_type = str(value.get("type", "")).upper()
        if value_type == "STRING" and value.get("enum"):
            pieces.append(f"enum:{gemma_format_argument(value['enum'])}")
        elif value_type == "ARRAY" and isinstance(value.get("items"), dict) and value["items"]:
            item_pieces: list[str] = []
            for item_key, item_value in sorted(value["items"].items()):
                if item_value is None:
                    continue
                if item_key == "type":
                    item_pieces.append(f"type:{gemma_format_argument(str(item_value).upper())}")
                elif item_key == "properties" and isinstance(item_value, dict):
                    item_pieces.append(f"properties:{{{gemma_format_parameters(item_value, value['items'].get('required', []))}}}")
                elif item_key == "required" and isinstance(item_value, list):
                    item_pieces.append(f"required:{gemma_format_argument(item_value)}")
                else:
                    item_pieces.append(f"{item_key}:{gemma_format_argument(item_value)}")
            if item_pieces:
                pieces.append("items:{" + ",".join(item_pieces) + "}")
        if value.get("nullable"):
            pieces.append("nullable:true")
        if value_type == "OBJECT":
            nested = value.get("properties")
            if isinstance(nested, dict):
                pieces.append(f"properties:{{{gemma_format_parameters(nested, value.get('required', []))}}}")
            if value.get("required"):
                pieces.append(f"required:{gemma_format_argument(value['required'])}")
        pieces.append(f'type:<|"|>{value_type}<|"|>')
        rendered.append(f"{key}:{{{','.join(pieces)}}}")
    return ",".join(rendered)


def gemma_tool_block(tools: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for tool in tools:
        function = tool.get("function") if isinstance(tool, dict) else None
        if not isinstance(function, dict):
            continue
        pieces = [f'description:<|"|>{function.get("description", "")}<|"|>']
        params = function.get("parameters")
        if isinstance(params, dict):
            param_pieces: list[str] = []
            properties = params.get("properties")
            if isinstance(properties, dict):
                param_pieces.append(f"properties:{{{gemma_format_parameters(properties, params.get('required', []))}}}")
            if params.get("required"):
                param_pieces.append(f"required:{gemma_format_argument(params['required'])}")
            if params.get("type"):
                param_pieces.append(f'type:<|"|>{str(params["type"]).upper()}<|"|>')
            if param_pieces:
                pieces.append("parameters:{" + ",".join(param_pieces) + "}")
        blocks.append(f'<|tool>declaration:{function.get("name", "")}' + "{" + ",".join(pieces) + "}<tool|>")
    return "".join(blocks)


def parse_bfcl_prompt(prompt: str) -> tuple[list[dict[str, Any]], str] | None:
    """Extract BFCL function declarations and the user question from text prompts.

    EuroEval BFCL currently sends the function list embedded in plain text.
    For Gemma-template checkpoints we can render those declarations with the
    native tool block instead, while keeping non-BFCL prompts unchanged.
    """
    marker = "Functions:"
    question_marker = "Question:"
    marker_pos = prompt.find(marker)
    if marker_pos < 0:
        return None
    json_start = marker_pos + len(marker)
    while json_start < len(prompt) and prompt[json_start].isspace():
        json_start += 1
    if json_start >= len(prompt) or prompt[json_start] != "[":
        return None
    try:
        functions, end = json.JSONDecoder().raw_decode(prompt[json_start:])
    except json.JSONDecodeError:
        return None
    if not isinstance(functions, list) or not all(isinstance(item, dict) for item in functions):
        return None

    rest = prompt[json_start + end :]
    question_pos = rest.find(question_marker)
    if question_pos < 0:
        return None
    question = rest[question_pos + len(question_marker) :].strip()
    for answer_marker in ("\nAnswer with a JSON", "\nAnswer in JSON", "\nYour answer"):
        if answer_marker in question:
            question = question.split(answer_marker, 1)[0].strip()
            break
    if not question:
        return None
    return [as_openai_tool(item) for item in functions], question


def _gemma_arg_text_to_jsonish(text: str) -> str:
    text = text.strip()
    text = text.replace("<|\"|>", '"')
    text = text.replace("<|\"|>", '"')
    text = re.sub(r"([,{]\s*)([A-Za-z_][A-Za-z0-9_-]*)(\s*:)", r'\1"\2"\3', "{" + text + "}")
    return text


def parse_gemma_tool_arguments(text: str) -> dict[str, Any] | str:
    jsonish = _gemma_arg_text_to_jsonish(text)
    try:
        parsed = json.loads(jsonish)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    equals_args: dict[str, Any] = {}
    pos = 0
    pattern = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'|[^,]+)\s*(?:,|$)", re.DOTALL)
    while pos < len(text.strip()):
        match = pattern.match(text, pos)
        if match is None:
            equals_args = {}
            break
        raw_value = match.group(2).strip()
        if raw_value.startswith("'") and raw_value.endswith("'"):
            raw_value = '"' + raw_value[1:-1].replace('"', '\\"') + '"'
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            if raw_value.lower() == "true":
                value = True
            elif raw_value.lower() == "false":
                value = False
            elif raw_value.lower() == "null":
                value = None
            else:
                value = raw_value
        equals_args[match.group(1)] = value
        pos = match.end()
    if equals_args:
        return equals_args
    return text.strip()


def parse_gemma_tool_calls(text: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    pattern = re.compile(r"(?:<\|tool_call\>)?\s*call:([A-Za-z0-9_.-]+)\{(.*?)\}(?:<tool_call\|>)?", re.DOTALL)
    for match in pattern.finditer(text or ""):
        calls.append(
            {
                "function": match.group(1),
                "arguments": parse_gemma_tool_arguments(match.group(2)),
            }
        )
    return calls


def adapt_bfcl_response(response: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    changed = False
    for choice in response.get("choices", []):
        message = choice.get("message") if isinstance(choice, dict) else None
        if not isinstance(message, dict):
            continue
        native_calls: list[dict[str, Any]] = []
        if isinstance(message.get("tool_calls"), list):
            for call in message["tool_calls"]:
                function = call.get("function") if isinstance(call, dict) else None
                if not isinstance(function, dict):
                    continue
                arguments = function.get("arguments", {})
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        pass
                native_calls.append({"function": function.get("name", ""), "arguments": arguments})
        if not native_calls:
            native_calls = parse_gemma_tool_calls(str(message.get("content") or ""))
        if native_calls:
            message["content"] = json.dumps({"tool_calls": native_calls}, ensure_ascii=False, separators=(",", ":"))
            # EuroEval reads text content. Avoid exposing provider-specific
            # tool_calls fields alongside the normalized JSON answer.
            message.pop("tool_calls", None)
            changed = True
    return response, changed


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
        bfcl_tools: list[dict[str, Any]] | None = None
        bfcl_question: str | None = None
        if args.gemma_native_bfcl_tools or args.gemma_native_bfcl_tools_as_text:
            parsed_bfcl = parse_bfcl_prompt(prompt)
            if parsed_bfcl is not None:
                bfcl_tools, bfcl_question = parsed_bfcl
        if bfcl_tools is not None and args.gemma_native_bfcl_tools_as_text:
            outgoing_messages = [
                {"role": "system", "content": gemma_tool_block(bfcl_tools)},
                {"role": "user", "content": bfcl_question or prompt},
            ]
        else:
            outgoing_messages = [{"role": "user", "content": bfcl_question or prompt}]
        outgoing: dict[str, Any] = {
            "model": target_model,
            "messages": outgoing_messages,
            "temperature": incoming.get("temperature", 0.0),
        }
        if bfcl_tools is not None and not args.gemma_native_bfcl_tools_as_text:
            outgoing["tools"] = bfcl_tools
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
                "gemma_native_bfcl_tools": bfcl_tools is not None,
                "gemma_native_bfcl_tools_as_text": bool(bfcl_tools is not None and args.gemma_native_bfcl_tools_as_text),
                "bfcl_tool_count": len(bfcl_tools or []),
                "outgoing": outgoing,
            }
        )
        response = await post_json("/chat/completions", outgoing)
        response["model"] = args.model_name
        if bfcl_tools is not None:
            response, changed = adapt_bfcl_response(response)
            log_record(
                {
                    "time": time.time(),
                    "endpoint": "/v1/chat/completions",
                    "gemma_native_bfcl_response_adapted": changed,
                    "response_id": response.get("id"),
                }
            )
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
