import argparse
import json
import math
import sys
from pathlib import Path

import torch
import yaml
from safetensors.torch import save_file
from transformers import AutoTokenizer, PreTrainedTokenizerFast

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dataset_new import V1DatasetMeta
from pretrain import PretrainConfig
from simple_inference_engine import inference_load_checkpoint


SKIP_PREFIXES = (
    "model.H_level.core.rotary_emb.",
    "model.L_level.core.rotary_emb.",
)
DROP_KEYS = {"model.zH_init"}


def remap_key(key: str) -> str | None:
    if key in DROP_KEYS or key.startswith(SKIP_PREFIXES):
        return None
    key = key.replace("model.H_level.core.layers.", "model.H_module.layers.")
    key = key.replace("model.L_level.core.layers.", "model.L_module.layers.")
    key = key.replace("model.zL_init", "model.z_L_init")
    return "model.embed_tokens.weight" if key == "embed_tokens.embedding_weight" else key


def convert_state_dict(state_dict: dict[str, torch.Tensor]) -> tuple[dict[str, torch.Tensor], list[str]]:
    out, skipped = {}, []
    for key, value in state_dict.items():
        new_key = remap_key(key)
        if new_key is None:
            skipped.append(key)
        else:
            out[new_key] = value.contiguous()
    return out, skipped


def _compute_intermediate_size(hidden_size: int, expansion: float) -> int:
    return ((round(expansion * hidden_size * 2 / 3) + 255) // 256) * 256


def _compute_l_bp_cycles(cfg: dict) -> list[int]:
    H, L = int(cfg["H_cycles"]), int(cfg["L_cycles"])
    bp_steps = int(cfg.get("bp_max_steps", cfg.get("max_bp_steps", H + 1)))
    h_bp_steps = min(H, max(0, bp_steps - 1))
    l_bp_steps = min(H * L, max(0, bp_steps - h_bp_steps))
    threshold = H * L - l_bp_steps
    return [max(0, min(L, (i + 1) * L - threshold)) for i in range(H)]


def per_stack_layers(cfg: dict) -> int:
    n_layers = int(cfg["n_layers"])
    if cfg.get("half_layers"):
        if n_layers % 2 != 0:
            raise ValueError(f"half_layers=True requires an even n_layers, got {n_layers}")
        return n_layers // 2
    return n_layers


def load_config(ckpt_path: Path) -> tuple[V1DatasetMeta, PretrainConfig, dict]:
    model_cfg = PretrainConfig(**yaml.safe_load((ckpt_path / "all_config.yaml").read_text()))
    metadata = V1DatasetMeta(**yaml.safe_load((ckpt_path / "train_metadata.yaml").read_text()))
    return metadata, model_cfg, model_cfg.arch.model_dump() | metadata.model_dump() | model_cfg.data.model_dump()


def build_hf_config(cfg: dict, tokenizer) -> dict:
    hidden_size = cfg["hidden_size"]
    rope_theta = cfg.get("rope_theta", 10000.0)
    init_type, init_std = cfg.get("init_type", "fixed_normal"), cfg.get("init_std")
    if init_type == "lecun_normal":
        in_std = 1.0 / math.sqrt(hidden_size)
    elif init_std is not None:
        in_std = init_std
    else:
        in_std = 1.0 / math.sqrt(hidden_size) if init_type == "megatron" else 0.02

    hf_cfg = {
        "model_type": "hrm_text",
        "architectures": ["HrmTextForCausalLM"],
        "vocab_size": cfg["vocab_size"],
        "hidden_size": hidden_size,
        "intermediate_size": _compute_intermediate_size(hidden_size, cfg.get("expansion", 4.0)),
        "num_hidden_layers": per_stack_layers(cfg),
        "num_attention_heads": cfg["num_heads"],
        "num_key_value_heads": cfg["num_heads"],
        "head_dim": hidden_size // cfg["num_heads"],
        "hidden_act": "silu",
        "H_cycles": cfg["H_cycles"],
        "L_cycles": cfg["L_cycles"],
        "L_bp_cycles": _compute_l_bp_cycles(cfg),
        "max_position_embeddings": cfg["max_seq_len"],
        "rms_norm_eps": cfg.get("norm_eps", 1e-6),
        "rope_theta": rope_theta,
        "rope_parameters": {"rope_type": "default", "rope_theta": rope_theta},
        "attention_bias": False,
        "attention_dropout": 0.0,
        "mlp_bias": False,
        "use_cache": True,
        "tie_word_embeddings": False,
        "initializer_range": in_std,
        "embedding_scale": 1.0 / in_std,
        "prefix_lm": True,
        "pad_token_id": getattr(tokenizer, "pad_token_id", None) or 0,
    }
    for key, token_name in (("bos_token_id", "boq"), ("eos_token_id", "eoa")):
        if token_name in cfg:
            hf_cfg[key] = tokenizer.convert_tokens_to_ids(cfg[token_name])
    if cfg.get("template_mode") == "jinja_chat_template":
        for key, token_name in (
            ("bos_token_id", "<bos>"),
            ("eos_token_id", "<turn|>"),
            ("pad_token_id", "<pad>"),
        ):
            token_id = tokenizer.convert_tokens_to_ids(token_name)
            if token_id is not None and token_id != getattr(tokenizer, "unk_token_id", None):
                hf_cfg[key] = token_id
    return {k: v for k, v in hf_cfg.items() if v is not None}


def tokenizer_path(metadata: V1DatasetMeta, override: Path | None) -> Path:
    path = override or Path(metadata.tokenizer_info["tokenizer_path"])
    return path.parent if path.name == "tokenizer.json" else path


def set_tokenizer_special_tokens(tokenizer, cfg: dict):
    if cfg.get("template_mode") == "jinja_chat_template":
        # Gemma 4 uses a tokenizer JSON that Transformers warns about unless
        # this compatibility flag is persisted for downstream AutoTokenizer
        # loads. Without it, HF/vLLM can tokenize punctuation/spacing
        # differently from the intended Gemma tokenizer.
        tokenizer.init_kwargs["fix_mistral_regex"] = True
        if tokenizer.convert_tokens_to_ids("<pad>") != getattr(tokenizer, "unk_token_id", None):
            tokenizer.pad_token = "<pad>"
        if tokenizer.convert_tokens_to_ids("<bos>") != getattr(tokenizer, "unk_token_id", None):
            tokenizer.bos_token = "<bos>"
        if tokenizer.convert_tokens_to_ids("<turn|>") != getattr(tokenizer, "unk_token_id", None):
            tokenizer.eos_token = "<turn|>"
        chat_template_path = cfg.get("chat_template_path")
        if chat_template_path and Path(chat_template_path).is_file():
            tokenizer.chat_template = Path(chat_template_path).read_text()
    if tokenizer.pad_token is None:
        endoftext_id = tokenizer.convert_tokens_to_ids("<|endoftext|>")
        if endoftext_id != tokenizer.unk_token_id:
            tokenizer.pad_token = "<|endoftext|>"
    if "boq" in cfg:
        tokenizer.bos_token = cfg["boq"]
    if "eoa" in cfg:
        tokenizer.eos_token = cfg["eoa"]
    return tokenizer


def load_tokenizer(path: Path):
    tokenizer_file = path / "tokenizer.json" if path.is_dir() else path
    if tokenizer_file.is_file():
        return PreTrainedTokenizerFast(tokenizer_file=str(tokenizer_file))
    return AutoTokenizer.from_pretrained(str(path), use_fast=True)


def parse_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "y"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt_path", type=Path, required=True)
    parser.add_argument("--ckpt_epoch", type=int, default=None)
    parser.add_argument("--ckpt_tag", type=str, default=None)
    parser.add_argument("--ckpt_use_ema", type=parse_bool, default=True)
    parser.add_argument("--out_dir", type=Path, required=True)
    parser.add_argument("--tokenizer_path", type=Path, default=None)
    parser.add_argument("--config-only", action="store_true", help="Write config/tokenizer only; do not load or save model weights.")
    args = parser.parse_args()
    if args.ckpt_epoch is not None and args.ckpt_tag is not None:
        parser.error("Specify only one of --ckpt_epoch and --ckpt_tag")

    metadata, _model_cfg, cfg = load_config(args.ckpt_path)

    tok_path = tokenizer_path(metadata, args.tokenizer_path)
    print(f"[convert] using tokenizer at {tok_path}")
    tokenizer = load_tokenizer(tok_path)
    tokenizer = set_tokenizer_special_tokens(tokenizer, metadata.tokenizer_info)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "config.json").write_text(json.dumps(build_hf_config(cfg | metadata.tokenizer_info, tokenizer), indent=2))
    tokenizer.save_pretrained(args.out_dir)
    tokenizer_config_path = args.out_dir / "tokenizer_config.json"
    if tokenizer_config_path.is_file() and metadata.tokenizer_info.get("template_mode") == "jinja_chat_template":
        tokenizer_config = json.loads(tokenizer_config_path.read_text())
        tokenizer_config["fix_mistral_regex"] = True
        tokenizer_config_path.write_text(json.dumps(tokenizer_config, indent=2) + "\n")
    if args.config_only:
        print(f"[convert] wrote config/tokenizer only to {args.out_dir}")
        return

    ckpt = inference_load_checkpoint(str(args.ckpt_path), args.ckpt_epoch, args.ckpt_use_ema, ckpt_tag=args.ckpt_tag)
    hf_state, dropped = convert_state_dict(ckpt.model.state_dict())
    print(f"[convert] mapped {len(hf_state)} tensors; dropped {len(dropped)}")
    if dropped:
        print("[convert] dropped tensors:")
        for key in dropped:
            print(f"  - {key}")

    save_file(hf_state, args.out_dir / "model.safetensors")
    print(f"[convert] wrote checkpoint to {args.out_dir}")


if __name__ == "__main__":
    main()
