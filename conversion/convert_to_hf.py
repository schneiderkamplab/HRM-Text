import argparse
import json
import math
import re
import sys
from pathlib import Path

import torch
import yaml
from safetensors.torch import save_file
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, PreTrainedTokenizerFast

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

ATTN_PACKED_RE = re.compile(r"^(model\.[HL]_module\.layers\.\d+)\.attn\.gqkv_proj\.weight$")
ATTN_OUT_RE = re.compile(r"^(model\.[HL]_module\.layers\.\d+)\.attn\.o_proj\.weight$")
MLP_PACKED_RE = re.compile(r"^(model\.[HL]_module\.layers\.\d+)\.mlp\.gate_up_proj\.weight$")


def remap_key(key: str, *, weight_layout: str) -> str | None:
    if key in DROP_KEYS or key.startswith(SKIP_PREFIXES):
        return None
    key = key.replace("model.H_level.core.layers.", "model.H_module.layers.")
    key = key.replace("model.L_level.core.layers.", "model.L_module.layers.")
    if weight_layout == "hf_split":
        key = key.replace(".attn.o_proj.", ".self_attn.o_proj.")
    key = key.replace("model.zL_init", "model.z_L_init")
    return "model.embed_tokens.weight" if key == "embed_tokens.embedding_weight" else key


def _token_id(tokenizer, token: str | None) -> int | None:
    if token is None:
        return None
    token_id = tokenizer.convert_tokens_to_ids(token)
    if token_id is None or token_id == getattr(tokenizer, "unk_token_id", None):
        return None
    return int(token_id)


def _split_attention_projection(cfg: dict, key: str, value: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    num_heads = int(cfg["num_heads"])
    num_key_value_heads = int(cfg.get("num_key_value_heads", num_heads))
    if num_key_value_heads != num_heads:
        raise ValueError(
            f"{key}: HF HRM-Text export currently supports MHA checkpoints only "
            f"(num_heads={num_heads}, num_key_value_heads={num_key_value_heads})"
        )
    head_dim = int(cfg["hidden_size"]) // num_heads
    split_sizes = [num_heads * head_dim, num_heads * head_dim, num_key_value_heads * head_dim, num_key_value_heads * head_dim]
    if value.shape[0] != sum(split_sizes):
        raise ValueError(f"{key}: expected packed attention rows {sum(split_sizes)}, got {value.shape[0]}")
    return value.split(split_sizes, dim=0)


def convert_state_dict(
    state_dict: dict[str, torch.Tensor],
    cfg: dict,
    *,
    weight_layout: str = "vllm_packed",
) -> tuple[dict[str, torch.Tensor], list[str]]:
    if cfg.get("name") in ("baselines.sandwich@Sandwich", "baselines.ouro@Ouro"):
        if weight_layout != "vllm_packed":
            raise ValueError("Sandwich/Ouro export currently supports vllm_packed only")
        return {("model.embed_tokens.weight" if k == "embed_tokens.embedding_weight" else k): v.contiguous()
                for k, v in state_dict.items() if not k.startswith("model.rotary_emb.")}, []
    if cfg.get("name") == "baselines.transformer_wrapper@TransformerWrapper":
        # A single H pass with zero L passes and zero initial L state is
        # exactly a non-recurrent Transformer stack. L weights are never used,
        # but both installed HF/vLLM implementations declare their tensors.
        mapped = {}
        for key, value in state_dict.items():
            if key.startswith("model.layers."):
                suffix = key.removeprefix("model.layers.")
                mapped["model.H_module.layers." + suffix] = value
                mapped["model.L_module.layers." + suffix] = torch.zeros_like(value)
            elif not key.startswith("model.rotary_emb."):
                mapped[key] = value
        mapped["model.z_L_init"] = torch.zeros(
            cfg["hidden_size"], dtype=next(iter(state_dict.values())).dtype
        )
        state_dict = mapped
    if any("invocation_gates" in key.split(".") for key in state_dict):
        raise ValueError("HRM v2 gates require a gate-aware HF/vLLM architecture; use native inference until supported")
    out, skipped = {}, []
    for key, value in state_dict.items():
        new_key = remap_key(key, weight_layout=weight_layout)
        if new_key is None:
            skipped.append(key)
        elif weight_layout == "hf_split" and (match := ATTN_PACKED_RE.match(new_key)):
            prefix = match.group(1)
            gate, query, key_tensor, val = _split_attention_projection(cfg, new_key, value)
            out[f"{prefix}.self_attn.gate_proj.weight"] = gate.contiguous()
            out[f"{prefix}.self_attn.q_proj.weight"] = query.contiguous()
            out[f"{prefix}.self_attn.k_proj.weight"] = key_tensor.contiguous()
            out[f"{prefix}.self_attn.v_proj.weight"] = val.contiguous()
        elif weight_layout == "hf_split" and (match := MLP_PACKED_RE.match(new_key)):
            prefix = match.group(1)
            gate, up = value.chunk(2, dim=0)
            out[f"{prefix}.mlp.gate_proj.weight"] = gate.contiguous()
            out[f"{prefix}.mlp.up_proj.weight"] = up.contiguous()
        elif weight_layout == "hf_split" and (match := ATTN_OUT_RE.match(new_key)):
            prefix = match.group(1)
            out[f"{prefix}.self_attn.o_proj.weight"] = value.contiguous()
        else:
            out[new_key] = value.contiguous()
    return out, skipped


def validate_hf_state(out_dir: Path, hf_state: dict[str, torch.Tensor]) -> None:
    config = AutoConfig.from_pretrained(out_dir, trust_remote_code=True)
    with torch.device("meta"):
        model = AutoModelForCausalLM.from_config(config, trust_remote_code=True)
    expected = model.state_dict()
    missing = sorted(set(expected) - set(hf_state))
    unexpected = sorted(set(hf_state) - set(expected))
    shape_mismatches = sorted(
        (key, tuple(hf_state[key].shape), tuple(expected[key].shape))
        for key in set(expected) & set(hf_state)
        if tuple(hf_state[key].shape) != tuple(expected[key].shape)
    )
    if missing or unexpected or shape_mismatches:
        details = []
        if missing:
            details.append("missing HF tensors:\n" + "\n".join(f"  - {key}" for key in missing))
        if unexpected:
            details.append("unexpected HF tensors:\n" + "\n".join(f"  - {key}" for key in unexpected))
        if shape_mismatches:
            details.append(
                "shape mismatches:\n"
                + "\n".join(f"  - {key}: got {got}, expected {expected_shape}" for key, got, expected_shape in shape_mismatches)
            )
        raise RuntimeError("converted checkpoint does not match HF architecture:\n" + "\n".join(details))


def validate_vllm_packed_state(hf_state: dict[str, torch.Tensor]) -> None:
    split_markers = (".self_attn.q_proj.", ".self_attn.k_proj.", ".self_attn.v_proj.", ".self_attn.gate_proj.", ".mlp.gate_proj.", ".mlp.up_proj.")
    split_keys = [key for key in hf_state if any(marker in key for marker in split_markers)]
    packed_attention = [key for key in hf_state if ATTN_PACKED_RE.match(key) or re.fullmatch(r"model\.layers\.\d+\.attn\.gqkv_proj\.weight", key)]
    packed_mlp = [key for key in hf_state if MLP_PACKED_RE.match(key) or re.fullmatch(r"model\.layers\.\d+\.mlp\.gate_up_proj\.weight", key)]
    if split_keys or not packed_attention or not packed_mlp:
        details = []
        if split_keys:
            details.append("split HF tensors are not vLLM-compatible:\n" + "\n".join(f"  - {key}" for key in split_keys[:20]))
        if not packed_attention:
            details.append("no packed attention gqkv tensors found")
        if not packed_mlp:
            details.append("no packed MLP gate_up tensors found")
        raise RuntimeError("converted checkpoint does not match vLLM packed HRM layout:\n" + "\n".join(details))


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


def _build_rope_parameters(cfg: dict, rope_theta: float) -> dict:
    scaling_type = cfg.get("H_rope_scaling_type", cfg.get("rope_scaling_type", "none"))
    scaling_factor = float(cfg.get("H_rope_scaling_factor", cfg.get("rope_scaling_factor", 1.0)))
    if scaling_type in {None, "none", "default"}:
        return {"rope_type": "default", "rope_theta": rope_theta}
    if scaling_factor < 1.0:
        raise ValueError(f"RoPE scaling factor must be >= 1, got {scaling_factor}")
    max_seq_len = int(cfg["max_seq_len"])
    original_max_positions = int(round(max_seq_len / scaling_factor))
    return {
        "rope_type": scaling_type,
        "factor": scaling_factor,
        "original_max_position_embeddings": original_max_positions,
        "rope_theta": rope_theta,
    }


def build_hf_config(cfg: dict, tokenizer) -> dict:
    ouro = cfg.get("name") == "baselines.ouro@Ouro"
    if ouro:
        if cfg.get("norm_type") != "pre" or cfg.get("pos_emb_type") != "rope" or cfg.get("attn_type", "prefixlm") not in ("causal", "prefixlm"):
            raise ValueError("Ouro export requires prenorm, RoPE, causal or PrefixLM attention")
        cfg = {"recurrence": 4} | cfg
        if type(cfg["recurrence"]) is not int or cfg["recurrence"] < 1 or cfg["n_layers"] < 1:
            raise ValueError("Invalid Ouro depths")
        cfg = cfg | {"H_cycles": 1, "L_cycles": 0, "half_layers": False, "bp_max_steps": 1}
    sandwich = cfg.get("name") == "baselines.sandwich@Sandwich"
    original_cfg = cfg
    if sandwich:
        if cfg.get("norm_type") != "pre" or cfg.get("pos_emb_type") != "rope" or cfg.get("attn_type", "prefixlm") not in ("causal", "prefixlm"):
            raise ValueError("Sandwich export requires prenorm, RoPE, causal or PrefixLM attention")
        cfg = {"prelude_layers": 3, "core_layers": 6, "coda_layers": 3, "recurrence": 7} | cfg
        if min(cfg[k] for k in ("prelude_layers", "core_layers", "coda_layers", "recurrence")) < 1 or cfg["n_layers"] != sum(cfg[k] for k in ("prelude_layers", "core_layers", "coda_layers")):
            raise ValueError("Invalid Sandwich depths")
        original_cfg = cfg
        cfg = cfg | {"H_cycles": 1, "L_cycles": 0, "half_layers": False, "bp_max_steps": 1}
    transformer = cfg.get("name") == "baselines.transformer_wrapper@TransformerWrapper"
    if transformer:
        if cfg.get("norm_type") != "pre" or cfg.get("attn_type") not in ("causal", "prefixlm", "mixedlm") or cfg.get("pos_emb_type") != "rope":
            raise ValueError("Transformer export currently requires prenorm, causal, PrefixLM or MixedLM attention, and RoPE")
        cfg = cfg | {"H_cycles": 1, "L_cycles": 0, "half_layers": False, "bp_max_steps": 1}
    if cfg.get("name") == "baselines.hrm_v2@HierarchicalReasoningModel":
        raise ValueError("HRM v2 HF/vLLM export is not yet supported; native inference preserves gates")
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
        "rope_parameters": _build_rope_parameters(cfg, rope_theta),
        "L_sliding_window": cfg.get("L_sliding_window"),
        "H_sliding_window": cfg.get("H_sliding_window"),
        "attention_bias": False,
        "attention_dropout": 0.0,
        "mlp_bias": False,
        "use_cache": True,
        "tie_word_embeddings": False,
        "initializer_range": in_std,
        "embedding_scale": 1.0 / in_std,
        "prefix_lm": cfg.get("attn_type", "prefixlm") != "causal",
        "pad_token_id": getattr(tokenizer, "pad_token_id", None) or 0,
    }
    if cfg.get("attn_type") == "mixedlm":
        hf_cfg["mixed_lm"] = True
        hf_cfg["mixed_lm_policy"] = "assistant-header-blocks-v1-tool-full-refresh"
        hf_cfg["mixed_lm_header_tokens"] = tokenizer.encode('<|turn>model\n', add_special_tokens=False)
        hf_cfg["mixed_lm_tool_tokens"] = [tokenizer.convert_tokens_to_ids(t) for t in ('<|tool_call>', '<|tool_response>')]
        if not hf_cfg["mixed_lm_header_tokens"] or any(t is None or t == getattr(tokenizer, 'unk_token_id', None) for t in hf_cfg["mixed_lm_tool_tokens"]):
            raise ValueError("MixedLM export requires the verified Gemma4 chat-token protocol")
    if ouro:
        hf_cfg.update(ouro_fixed_architecture=True, architectures=["OuroFixedForCausalLM"],
            recurrence=cfg["recurrence"], num_layers_per_stack=cfg["n_layers"],
            num_hidden_layers=cfg["n_layers"] * cfg["recurrence"])
    if sandwich:
        hf_cfg.update(sandwich_architecture=True, architectures=["SandwichForCausalLM"],
            num_layers_per_stack=cfg["n_layers"],
            num_hidden_layers=cfg["prelude_layers"] + cfg["core_layers"] * cfg["recurrence"] + cfg["coda_layers"])
        for key in ("prelude_layers", "core_layers", "coda_layers", "recurrence"):
            hf_cfg[key] = original_cfg[key]
    if transformer:
        hf_cfg["source_architecture"] = "TransformerWrapper"
        hf_cfg["transformer_single_pass"] = True
    for key, token_name in (("bos_token_id", "boq"), ("eos_token_id", "eoa")):
        if token_name in cfg:
            if (token_id := _token_id(tokenizer, cfg[token_name])) is not None:
                hf_cfg[key] = token_id
    for key, token_name in (("bos_token_id", "bos"), ("eos_token_id", "eos"), ("pad_token_id", "pad")):
        if token_name in cfg:
            if (token_id := _token_id(tokenizer, cfg[token_name])) is not None:
                hf_cfg[key] = token_id
    if cfg.get("template_mode") == "jinja_chat_template":
        for key, token_name in (
            ("bos_token_id", "<bos>"),
            ("eos_token_id", "<turn|>"),
            ("pad_token_id", "<pad>"),
        ):
            token_id = _token_id(tokenizer, token_name)
            if token_id is not None:
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
    if cfg.get("template_mode") != "jinja_chat_template":
        if "pad" in cfg and _token_id(tokenizer, cfg["pad"]) is not None:
            tokenizer.pad_token = cfg["pad"]
        if "boq" in cfg:
            tokenizer.bos_token = cfg["boq"]
        elif "bos" in cfg and _token_id(tokenizer, cfg["bos"]) is not None:
            tokenizer.bos_token = cfg["bos"]
        if "eoa" in cfg:
            tokenizer.eos_token = cfg["eoa"]
        elif "eos" in cfg and _token_id(tokenizer, cfg["eos"]) is not None:
            tokenizer.eos_token = cfg["eos"]
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
    parser.add_argument(
        "--weight-layout",
        choices=("vllm_packed", "hf_split"),
        default="vllm_packed",
        help=(
            "Weight layout to write. vllm_packed is the production default "
            "for vLLM HRM evals; hf_split writes explicit Transformers "
            "q/k/v/gate and MLP gate/up tensors."
        ),
    )
    parser.add_argument("--config-only", action="store_true", help="Write config/tokenizer only; do not load or save model weights.")
    args = parser.parse_args()
    if args.ckpt_epoch is not None and args.ckpt_tag is not None:
        parser.error("Specify only one of --ckpt_epoch and --ckpt_tag")

    metadata, _model_cfg, cfg = load_config(args.ckpt_path)

    tok_path = tokenizer_path(metadata, args.tokenizer_path)
    print(f"[convert] using tokenizer at {tok_path}")
    tokenizer = load_tokenizer(tok_path)
    tokenizer = set_tokenizer_special_tokens(tokenizer, metadata.tokenizer_info)

    if cfg.get("name") == "baselines.embla@Embla":
        if args.config_only:
            raise ValueError("Embla config-only export is not yet supported; export a verified checkpoint")
        from models.embla.export import export_pretrained
        ckpt = inference_load_checkpoint(
            str(args.ckpt_path), args.ckpt_epoch, args.ckpt_use_ema,
            ckpt_tag=args.ckpt_tag, tokenizer_path_override=tok_path,
        )
        export_pretrained(ckpt.model.model, args.out_dir)
        tokenizer.save_pretrained(args.out_dir)
        print(f"[convert] wrote Embla portable checkpoint to {args.out_dir}")
        return

    args.out_dir.mkdir(parents=True, exist_ok=True)
    hf_config = build_hf_config(cfg | metadata.tokenizer_info, tokenizer)
    if hf_config.get("sandwich_architecture") or hf_config.get("ouro_fixed_architecture"):
        if args.weight_layout != "vllm_packed":
            raise ValueError("Sandwich/Ouro export currently supports vllm_packed only")
    elif hf_config.get("mixed_lm") and args.weight_layout == "vllm_packed":
        hf_config["architectures"] = ["MixedLMForCausalLM"]
    elif hf_config.get("transformer_single_pass") and args.weight_layout == "vllm_packed":
        hf_config["architectures"] = ["Transformer48ForCausalLM"]
    elif not hf_config["prefix_lm"] and args.weight_layout == "vllm_packed":
        hf_config["architectures"] = ["RecurrentCausalForCausalLM"]
    (args.out_dir / "config.json").write_text(json.dumps(hf_config, indent=2))
    tokenizer.save_pretrained(args.out_dir)
    tokenizer_config_path = args.out_dir / "tokenizer_config.json"
    if tokenizer_config_path.is_file() and metadata.tokenizer_info.get("template_mode") == "jinja_chat_template":
        tokenizer_config = json.loads(tokenizer_config_path.read_text())
        tokenizer_config["fix_mistral_regex"] = True
        tokenizer_config_path.write_text(json.dumps(tokenizer_config, indent=2) + "\n")
    if args.config_only:
        print(f"[convert] wrote config/tokenizer only to {args.out_dir}")
        return

    ckpt = inference_load_checkpoint(
        str(args.ckpt_path),
        args.ckpt_epoch,
        args.ckpt_use_ema,
        ckpt_tag=args.ckpt_tag,
        tokenizer_path_override=tok_path,
    )
    hf_state, dropped = convert_state_dict(ckpt.model.state_dict(), cfg, weight_layout=args.weight_layout)
    print(f"[convert] mapped {len(hf_state)} tensors; dropped {len(dropped)}")
    if dropped:
        print("[convert] dropped tensors:")
        for key in dropped:
            print(f"  - {key}")

    if args.weight_layout == "hf_split":
        validate_hf_state(args.out_dir, hf_state)
    else:
        validate_vllm_packed_state(hf_state)
    save_file(hf_state, args.out_dir / "model.safetensors")
    print(f"[convert] wrote {args.weight_layout} checkpoint to {args.out_dir}")


if __name__ == "__main__":
    main()
