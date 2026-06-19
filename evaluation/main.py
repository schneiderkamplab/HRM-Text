from typing import Any, Optional
from collections import defaultdict
import pydantic
import json
from pathlib import Path
import re
from omegaconf import OmegaConf

from utils.functions import load_model_class


class BenchmarkConfig(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra='allow')

    name: str
    generation_config: dict[str, Any] = {}
    num_shards: int = 1
    shard_index: int = 0
    max_samples: Optional[int] = None
    score_extractor: Optional[str] = None


class ShardOverrideConfig(pydantic.BaseModel):
    num_shards: int = 1
    shard_index: int = 0


class EvaluationConfig(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra='allow')

    run_only: Optional[list[str]] = None
    engine: str
    generation_config: dict[str, Any] = {}
    benchmarks: list[BenchmarkConfig]
    shard_overrides: dict[str, ShardOverrideConfig] = {}
    save_generations_dir: Optional[str] = None

    @pydantic.model_validator(mode='after')
    def check_run_only_against_benchmarks(self):
        if self.run_only is not None:
            assert self.run_only, "run_only cannot be empty."

            valid_set = {b_cfg.name for b_cfg in self.benchmarks}
            for b_name in self.run_only:
                if b_name not in valid_set:
                    raise ValueError(f"Unknown benchmark name in run_only: {b_name}")

        return self


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, set):
            return sorted(value)
        if isinstance(value, tuple):
            return [_jsonable(v) for v in value]
        if isinstance(value, list):
            return [_jsonable(v) for v in value]
        if isinstance(value, dict):
            return {str(k): _jsonable(v) for k, v in value.items()}
        return repr(value)


FINAL_INTEGER_RE = re.compile(
    r"(?:####|final\s+answer\s*(?:is|:)?|answer\s*(?:is|:)?|result\s*(?:is|:)?)\s*"
    r"(?P<answer>[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)",
    re.IGNORECASE,
)


def _extract_final_integer(text: str) -> str:
    matches = list(FINAL_INTEGER_RE.finditer(text))
    if not matches:
        return text
    return matches[-1].group("answer").replace(",", "")


def _extract_for_scoring(text: str, extractor: Optional[str]) -> str:
    if extractor is None:
        return text
    if extractor == "final_integer":
        return _extract_final_integer(text)
    raise ValueError(f"Unknown score_extractor: {extractor}")


def main():
    # 1. Load and Override Config
    cli_conf = OmegaConf.from_cli()
    config_path = cli_conf.pop("config", "evaluation/config/hrm_benchmarking.yaml")
    # Merge YAML config with CLI overrides
    base_conf = OmegaConf.load(config_path)
    cfg = EvaluationConfig(**OmegaConf.to_container(OmegaConf.merge(base_conf, cli_conf), resolve=True))  # type: ignore

    # 2. Initialize Engine
    print(f"Initializing Engine: {cfg.engine}...")
    engine_cls = load_model_class(f"engines@{cfg.engine}", prefix="evaluation.")
    engine = engine_cls(**(cfg.__pydantic_extra__ or {}))

    # 3. Group Benchmarks by Generation Config
    # To minimize bubbles, we group benchmarks sharing the exact same generation kwargs
    print("Preparing and grouping benchmarks...")

    # grouped_tasks maps a hashed config tuple -> {"prompts": [...], "benchmarks": [...]}
    grouped_tasks = defaultdict(lambda: {"prompts": [], "benchmarks": []})
    for b_cfg in cfg.benchmarks:
        b_name = b_cfg.name
        if cfg.run_only is not None and b_name not in cfg.run_only:
            continue

        # Instantiate benchmark
        bench_cls = load_model_class(f"benchmarks@{b_name}", prefix="evaluation.")
        benchmark = bench_cls(**(b_cfg.__pydantic_extra__ or {}))
        shard_cfg = cfg.shard_overrides.get(b_name)
        num_shards = shard_cfg.num_shards if shard_cfg is not None else b_cfg.num_shards
        shard_index = shard_cfg.shard_index if shard_cfg is not None else b_cfg.shard_index
        if num_shards < 1:
            raise ValueError(f"{b_name}: num_shards must be >= 1")
        if shard_index < 0 or shard_index >= num_shards:
            raise ValueError(f"{b_name}: shard_index must satisfy 0 <= shard_index < num_shards")
        if num_shards > 1:
            shard_prompts = []
            shard_ground_truths = []
            for index, (prompt, ground_truth) in enumerate(
                zip(benchmark.prompts, benchmark.ground_truths, strict=True)
            ):
                if index % num_shards == shard_index:
                    shard_prompts.append(prompt)
                    shard_ground_truths.append(ground_truth)
            benchmark.prompts = shard_prompts
            benchmark.ground_truths = shard_ground_truths
        if b_cfg.max_samples is not None:
            if b_cfg.max_samples < 1:
                raise ValueError(f"{b_name}: max_samples must be >= 1")
            benchmark.prompts = benchmark.prompts[:b_cfg.max_samples]
            benchmark.ground_truths = benchmark.ground_truths[:b_cfg.max_samples]

        # Resolve final generation config: Base -> Benchmark Specific -> Benchmark Overrides
        gen_cfg = cfg.generation_config | benchmark.generation_overrides | b_cfg.generation_config
        # Hash key for grouping identical ones
        gen_key = json.dumps(gen_cfg, sort_keys=True)
        
        # Track offsets to map flattened generations back to their source benchmarks
        start_idx = len(grouped_tasks[gen_key]["prompts"])
        grouped_tasks[gen_key]["prompts"].extend(benchmark.prompts)
        end_idx = len(grouped_tasks[gen_key]["prompts"])
        
        grouped_tasks[gen_key]["benchmarks"].append((b_name, benchmark, start_idx, end_idx, b_cfg.score_extractor))

    # 4. Generate and Evaluate per Group
    all_results = {}
    save_dir = Path(cfg.save_generations_dir) if cfg.save_generations_dir else None
    if save_dir is not None:
        save_dir.mkdir(parents=True, exist_ok=True)
    
    for gen_key, group in grouped_tasks.items():
        gen_kwargs = json.loads(gen_key)
        prompt_template = gen_kwargs.pop("prompt_template", "{prompt}")
        # Apply prompt templates
        prompts = [prompt_template.format(prompt=s) for s in group["prompts"]]
        
        print("\n" + "="*50)
        print(f"Running generation batch (Size: {len(prompts)}) with config:")
        for k, v in gen_kwargs.items():
            print(f"  {k}: {v}")
        print("="*50)

        # Generate all prompts for this config group
        generations = engine.generate(prompts, **gen_kwargs)

        # Dispatch results back to individual benchmarks
        for b_name, benchmark, start_idx, end_idx, score_extractor in group["benchmarks"]:
            b_generations = generations[start_idx:end_idx]
            scoring_generations = [
                _extract_for_scoring(generation, score_extractor)
                for generation in b_generations
            ]
            if save_dir is not None:
                output_path = save_dir / f"{b_name}.generations.jsonl"
                with output_path.open("w", encoding="utf-8") as f:
                    for local_index, (prompt, generation, scoring_generation, ground_truth) in enumerate(
                        zip(
                            prompts[start_idx:end_idx],
                            b_generations,
                            scoring_generations,
                            benchmark.ground_truths,
                            strict=True,
                        )
                    ):
                        row = {
                            "benchmark": b_name,
                            "index": local_index,
                            "prompt": prompt,
                            "generation": generation,
                            "scoring_generation": scoring_generation,
                            "score_extractor": score_extractor,
                            "ground_truth": _jsonable(ground_truth),
                        }
                        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            metrics = benchmark.compute_metrics(scoring_generations)
            all_results[b_name] = metrics

    # 5. Summary Report
    print("\n" + "#"*50 + "\nEVALUATION SUMMARY\n" + "#"*50)
    for b_name, metrics in all_results.items():
        print(f"\n--- {b_name} ---")
        for k, v in metrics.items():
            if isinstance(v, float):
                print(f"{k:.<25}: {v:.4f}")
            else:
                print(f"{k:.<25}: {v}")

if __name__ == "__main__":
    main()
