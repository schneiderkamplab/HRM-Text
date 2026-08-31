from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

import jinja2
from tqdm import tqdm
from vllm import LLM, SamplingParams
from vllm.inputs import TokensPrompt
from transformers import AutoTokenizer

from simple_inference_engine import inference_load_checkpoint, inference_generate


DEFAULT_GEMMA_CHAT_TEMPLATE = Path(__file__).parent / "chat_templates" / "gemma4_native_chat.jinja"


def _atomic_token_id(tokenizer, token: str) -> int | None:
    """Return the token ID only when ``token`` is represented atomically."""
    token_ids = tokenizer(
        token,
        return_attention_mask=False,
        add_special_tokens=False,
    )["input_ids"]
    if len(token_ids) != 1:
        return None
    return int(token_ids[0])


def _hrm_marker_ids(tokenizer) -> dict[str, int] | None:
    markers = (
        "<|im_start|>",
        "<|im_end|>",
        "<|box_end|>",
        "<|object_ref_start|>",
        "<|object_ref_end|>",
        "<|quad_start|>",
        "<|quad_end|>",
    )
    resolved = {marker: _atomic_token_id(tokenizer, marker) for marker in markers}
    if any(token_id is None for token_id in resolved.values()):
        return None
    return {marker: int(token_id) for marker, token_id in resolved.items()}

class BaseEngine:
    def generate(self, prompts: list[str]) -> list[str]:
        raise NotImplementedError

class VLLMEngine(BaseEngine):
    HRM_BOQ = "<|im_start|>"
    HRM_EOQ = "<|im_end|>"
    HRM_CONDITION_MAPPING = {
        "direct": "<|object_ref_start|>",
        "cot": "<|object_ref_end|>",
        "noisy": "<|quad_start|>",
        "synth": "<|quad_end|>",
    }

    def __init__(
        self,
        ckpt_path: str,
        prompt_mode: str = "raw",
        chat_template_path: str | None = None,
        **kwargs,
    ):
        if prompt_mode not in {"raw", "auto", "hrm", "hrm_tokens", "gemma_chat"}:
            raise ValueError(
                f"Unsupported VLLMEngine prompt_mode={prompt_mode!r}; "
                "expected raw, auto, hrm, hrm_tokens, or gemma_chat"
            )
        self.prompt_mode = prompt_mode
        self.tokenizer = None
        self.chat_template = None
        self.hrm_eoa_id = None
        if prompt_mode in {"auto", "hrm", "hrm_tokens", "gemma_chat"}:
            self.tokenizer = AutoTokenizer.from_pretrained(ckpt_path, use_fast=True)

        if prompt_mode == "auto":
            assert self.tokenizer is not None
            if _hrm_marker_ids(self.tokenizer) is not None:
                self.prompt_mode = "hrm_tokens"
            elif self.tokenizer.eos_token == "<turn|>":
                self.prompt_mode = "gemma_chat"
                chat_template_path = chat_template_path or str(DEFAULT_GEMMA_CHAT_TEMPLATE)
            else:
                raise ValueError(
                    "Could not infer a safe prompt mode from the checkpoint tokenizer. "
                    "Specify prompt_mode and its matching chat template explicitly."
                )

        if self.prompt_mode in {"hrm", "hrm_tokens"}:
            assert self.tokenizer is not None
            marker_ids = _hrm_marker_ids(self.tokenizer)
            if marker_ids is None:
                raise ValueError(
                    f"prompt_mode={self.prompt_mode!r} requires an HRM tokenizer with "
                    "atomic <|im_start|>, condition, <|im_end|>, and <|box_end|> markers. "
                    "This checkpoint does not have that tokenizer; use prompt_mode='gemma_chat' "
                    "with the checkpoint's training chat template."
                )
            self.hrm_eoa_id = marker_ids["<|box_end|>"]

        if self.prompt_mode == "gemma_chat":
            if chat_template_path is None:
                raise ValueError("VLLMEngine prompt_mode='gemma_chat' requires chat_template_path")
            self.chat_template = jinja2.Environment().from_string(Path(chat_template_path).read_text())
        self.llm = LLM(model=ckpt_path, **kwargs)

    def _format_hrm_prompt(self, prompt: str, condition: str) -> str:
        condition_tokens = "".join(
            self.HRM_CONDITION_MAPPING[c] for c in condition.split(",")
        )
        return f"{self.HRM_BOQ}{condition_tokens}{prompt.strip()}{self.HRM_EOQ}"

    def _format_gemma_chat_prompt(self, prompt: str) -> str:
        assert self.tokenizer is not None
        assert self.chat_template is not None
        return self.chat_template.render(
            messages=[{"role": "user", "content": prompt.strip()}],
            tools=None,
            add_generation_prompt=True,
            enable_thinking=False,
            bos_token=self.tokenizer.bos_token or "",
            eos_token=self.tokenizer.eos_token or "",
        )

    def generate(
        self,
        prompts: list[str],
        batch_size: int = 100,
        max_context: int = 1024,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
        condition: str = "direct",
        stop: Optional[str | list[str]] = None,
        stop_token_ids: Optional[list[int]] = None,
        skip_special_tokens: bool = False,
    ) -> list[str]:
        if max_tokens is None:
            max_tokens = max_context
        if self.prompt_mode in {"hrm", "hrm_tokens"}:
            prompts = [self._format_hrm_prompt(prompt, condition) for prompt in prompts]
            if stop_token_ids is None:
                assert self.hrm_eoa_id is not None
                stop_token_ids = [self.hrm_eoa_id]
        elif self.prompt_mode == "gemma_chat":
            prompts = [self._format_gemma_chat_prompt(prompt) for prompt in prompts]

        sampling_params = SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
            stop_token_ids=stop_token_ids,
            skip_special_tokens=skip_special_tokens,
        )
        batch_size = max(1, int(batch_size))
        generations: list[str] = []
        pbar = tqdm(total=len(prompts), desc="generation")
        for start in range(0, len(prompts), batch_size):
            batch_prompts = prompts[start:start + batch_size]
            if self.prompt_mode == "hrm_tokens":
                assert self.tokenizer is not None
                batch_prompts = [
                    TokensPrompt(
                        prompt_token_ids=self.tokenizer(
                            prompt,
                            return_attention_mask=False,
                            add_special_tokens=False,
                        )["input_ids"]
                    )
                    for prompt in batch_prompts
                ]
            outputs = self.llm.generate(batch_prompts, sampling_params)
            generations.extend(out.outputs[0].text for out in outputs)
            pbar.update(len(outputs))
        pbar.close()
        return generations

class SimpleEngine(BaseEngine):
    def __init__(
        self,
        ckpt_path: str,
        ckpt_epoch: Optional[int] = None,
        ckpt_use_ema: bool = True,
        ckpt_tag: Optional[str] = None,
    ):
        self.ckpt = inference_load_checkpoint(ckpt_path, ckpt_epoch, ckpt_use_ema, ckpt_tag=ckpt_tag)

    def generate(self, prompts: list[str], batch_size: int = 100, max_context: int = 1024, max_tokens: Optional[int] = None, temperature: float = 0.0, condition: str = "direct") -> list[str]:
        if max_tokens is None:
            max_tokens = max_context

        # Launch generation
        engine_prompts = [(i, (condition, p.strip())) for i, p in enumerate(prompts)]
        outputs = [""] * len(engine_prompts)

        pbar = tqdm(total=len(outputs), desc="generation")
        for gen_id, generated_text in inference_generate(
            self.ckpt, iter(engine_prompts), max_context, max_tokens, batch_size, temperature
        ):
            outputs[gen_id] = generated_text
            pbar.update()
        pbar.close()

        return outputs


class OpenAIEngine(BaseEngine):
    _CONTEXT_LENGTH_RE = re.compile(
        r"maximum context length is (?P<context>\d+) tokens.*?"
        r"requested (?P<output>\d+) output tokens.*?"
        r"prompt contains at least (?P<input>\d+) input tokens",
        re.IGNORECASE,
    )

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 600.0,
        context_window: int | None = None,
        tokenizer_path: str | None = None,
        chat_template_path: str | None = None,
        **_: object,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "inspectai")
        self.timeout = timeout
        self.context_window = context_window
        self.tokenizer = None
        self.chat_template = None
        if tokenizer_path is not None and chat_template_path is not None:
            self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, use_fast=True)
            self.chat_template = jinja2.Environment().from_string(
                Path(chat_template_path).read_text()
            )

    def _prompt_token_count(self, prompt: str) -> int | None:
        if self.tokenizer is None or self.chat_template is None:
            return None
        rendered = self.chat_template.render(
            messages=[{"role": "user", "content": prompt.strip()}],
            tools=None,
            add_generation_prompt=True,
            enable_thinking=False,
            bos_token=self.tokenizer.bos_token or "",
            eos_token=self.tokenizer.eos_token or "",
        )
        return len(
            self.tokenizer(
                rendered,
                return_attention_mask=False,
                add_special_tokens=False,
            )["input_ids"]
        )

    def _generate_one(
        self,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float,
        stop: Optional[str | list[str]],
        stop_token_ids: Optional[list[int]],
        skip_special_tokens: bool,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stop is not None:
            payload["stop"] = stop
        if stop_token_ids is not None:
            payload["stop_token_ids"] = stop_token_ids
        payload["skip_special_tokens"] = skip_special_tokens
        for attempt in range(2):
            request = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    data = json.loads(response.read())
                break
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                match = self._CONTEXT_LENGTH_RE.search(body)
                if exc.code == 400 and attempt == 0 and match is not None:
                    remaining = int(match.group("context")) - int(match.group("input"))
                    if 0 < remaining < int(payload["max_tokens"]):
                        payload["max_tokens"] = remaining
                        continue
                raise RuntimeError(
                    f"OpenAI-compatible request failed with HTTP {exc.code}: {body}"
                ) from exc
        return str(data["choices"][0]["message"]["content"])

    def generate(
        self,
        prompts: list[str],
        batch_size: int = 8,
        max_context: int = 1024,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
        condition: str = "direct",
        stop: Optional[str | list[str]] = None,
        stop_token_ids: Optional[list[int]] = None,
        skip_special_tokens: bool = False,
    ) -> list[str]:
        del max_context, condition
        if max_tokens is None:
            max_tokens = 1024
        output_budgets = [max_tokens] * len(prompts)
        if self.context_window is not None:
            for index, prompt in enumerate(prompts):
                prompt_tokens = self._prompt_token_count(prompt)
                if prompt_tokens is not None:
                    output_budgets[index] = max(
                        1,
                        min(max_tokens, self.context_window - prompt_tokens),
                    )
        outputs = [""] * len(prompts)
        workers = max(1, int(batch_size))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    self._generate_one,
                    prompt.strip(),
                    max_tokens=output_budgets[index],
                    temperature=temperature,
                    stop=stop,
                    stop_token_ids=stop_token_ids,
                    skip_special_tokens=skip_special_tokens,
                ): index
                for index, prompt in enumerate(prompts)
            }
            pbar = tqdm(total=len(outputs), desc="generation")
            for future in as_completed(futures):
                outputs[futures[future]] = future.result()
                pbar.update()
            pbar.close()
        return outputs
