from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
import json
import os
import urllib.error
import urllib.request

from tqdm import tqdm
from vllm import LLM, SamplingParams
from vllm.inputs import TokensPrompt
from transformers import AutoTokenizer

from simple_inference_engine import inference_load_checkpoint, inference_generate

class BaseEngine:
    def generate(self, prompts: list[str]) -> list[str]:
        raise NotImplementedError

class VLLMEngine(BaseEngine):
    HRM_BOQ = "<|im_start|>"
    HRM_EOQ = "<|im_end|>"
    HRM_EOA_ID = 11
    HRM_CONDITION_MAPPING = {
        "direct": "<|object_ref_start|>",
        "cot": "<|object_ref_end|>",
        "noisy": "<|quad_start|>",
        "synth": "<|quad_end|>",
    }

    def __init__(self, ckpt_path: str, prompt_mode: str = "raw", **kwargs):
        if prompt_mode not in {"raw", "hrm", "hrm_tokens"}:
            raise ValueError(f"Unsupported VLLMEngine prompt_mode={prompt_mode!r}; expected raw, hrm, or hrm_tokens")
        self.prompt_mode = prompt_mode
        self.tokenizer = None
        if prompt_mode == "hrm_tokens":
            self.tokenizer = AutoTokenizer.from_pretrained(ckpt_path, use_fast=True)
        self.llm = LLM(model=ckpt_path, **kwargs)

    def _format_hrm_prompt(self, prompt: str, condition: str) -> str:
        condition_tokens = "".join(
            self.HRM_CONDITION_MAPPING[c] for c in condition.split(",")
        )
        return f"{self.HRM_BOQ}{condition_tokens}{prompt.strip()}{self.HRM_EOQ}"

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
                stop_token_ids = [self.HRM_EOA_ID]

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
    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 600.0,
        **_: object,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "inspectai")
        self.timeout = timeout

    def _generate_one(
        self,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float,
        stop: Optional[str | list[str]],
    ) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stop is not None:
            payload["stop"] = stop
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
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI-compatible request failed with HTTP {exc.code}: {body}") from exc
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
    ) -> list[str]:
        del max_context, condition
        if max_tokens is None:
            max_tokens = 1024
        outputs = [""] * len(prompts)
        workers = max(1, int(batch_size))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    self._generate_one,
                    prompt.strip(),
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stop=stop,
                ): index
                for index, prompt in enumerate(prompts)
            }
            pbar = tqdm(total=len(outputs), desc="generation")
            for future in as_completed(futures):
                outputs[futures[future]] = future.result()
                pbar.update()
            pbar.close()
        return outputs
