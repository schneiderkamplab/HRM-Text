"""Create matched HF/GGUF HRM weights and an independent Transformers oracle."""

import argparse
import hashlib
import json
from pathlib import Path
import re

import gguf
import numpy as np
import torch
from transformers import HrmTextConfig, HrmTextForCausalLM

__all__ = []

_REFERENCE_REVISION = "ff2421c67f35cc83a0fbabbc2633c96734685918"


def _write_gguf(model, path, prefix_lm, tensor_dtype=np.float32, original_metadata=False):
    cfg = model.config
    writer = gguf.GGUFWriter(path, "hrm_text")
    writer.add_name("Deterministic HRM PrefixLM comparison fixture")
    writer.add_tokenizer_model("no_vocab")
    writer.add_vocab_size(cfg.vocab_size)
    writer.add_context_length(cfg.max_position_embeddings)
    writer.add_embedding_length(cfg.hidden_size)
    writer.add_block_count(cfg.num_hidden_layers)
    writer.add_feed_forward_length(cfg.intermediate_size)
    writer.add_head_count(cfg.num_attention_heads)
    writer.add_head_count_kv(cfg.num_attention_heads)
    writer.add_rope_dimension_count(cfg.head_dim)
    writer.add_rope_freq_base(10000.0)
    writer.add_layer_norm_rms_eps(cfg.rms_norm_eps)
    writer.add_embedding_scale(cfg.embedding_scale)
    if original_metadata:
        writer.add_uint32("hrm_text.layers_per_stack", cfg.num_layers_per_stack)
        writer.add_uint32("hrm_text.h_cycles", cfg.H_cycles)
        writer.add_uint32("hrm_text.l_cycles", cfg.L_cycles)
        if prefix_lm is not None:
            writer.add_bool("hrm_text.prefix_lm", prefix_lm)
    else:
        writer.add_hrm_layers_per_stack(cfg.num_layers_per_stack)
        writer.add_hrm_h_cycles(cfg.H_cycles)
        writer.add_hrm_l_cycles(cfg.L_cycles)
        if prefix_lm is not None:
            writer.add_hrm_prefix_lm(prefix_lm)
    names = {
        "model.z_L_init": "hrm.z_l_init",
        "model.embed_tokens.weight": "token_embd.weight",
        "lm_head.weight": "output.weight",
    }
    layers = {
        "self_attn.q_proj.weight": "attn_q.weight",
        "self_attn.k_proj.weight": "attn_k.weight",
        "self_attn.v_proj.weight": "attn_v.weight",
        "self_attn.o_proj.weight": "attn_output.weight",
        "self_attn.gate_proj.weight": "attn_gate.weight",
        "mlp.gate_proj.weight": "ffn_gate.weight",
        "mlp.up_proj.weight": "ffn_up.weight",
        "mlp.down_proj.weight": "ffn_down.weight",
    }
    for name, tensor in model.state_dict().items():
        target = names.get(name)
        if target is None:
            match = re.fullmatch(r"model\.([LH])_module\.layers\.(\d+)\.(.+)", name)
            if match is None:
                raise ValueError(f"Unmapped tensor: {name}")
            stack, index, suffix = match.groups()
            index = int(index) + (cfg.num_layers_per_stack if stack == "H" else 0)
            target = f"blk.{index}.{layers[suffix]}"
        original = tensor.detach().float().numpy()
        converted = original.astype(tensor_dtype, copy=False)
        if not np.array_equal(original, converted.astype(np.float32)):
            raise ValueError(f"Fixture conversion changed weight values: {name}")
        writer.add_tensor(target, converted)
    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file()
    writer.close()


def _step(tokens, attention="prefix", pos=0, **kwargs):
    return {"tokens": tokens, "attention": attention, "pos": pos, **kwargs}


def _cases():
    prompt = [2, 11, 23, 37, 41, 53]
    answer = [61, 73, 89]
    return [
        {"id": "prefix", "steps": [_step(prompt)]},
        {"id": "prefix_changed", "steps": [_step(prompt[:-1] + [57])]},
        {"id": "answer_chunk", "steps": [_step(prompt), _step(answer, "causal", 6)]},
        {"id": "answer_changed", "steps": [_step(prompt), _step([61, 73, 97], "causal", 6)]},
        {"id": "answer_single", "steps": [_step(prompt)] + [
            _step([token], "causal", 6 + i) for i, token in enumerate(answer)
        ]},
        {"id": "causal_control", "steps": [_step(prompt, "causal")]},
        {"id": "one_token_prefix", "steps": [_step([2]), _step(answer, "causal", 1)]},
        {"id": "turn_reset", "steps": [
            _step(prompt), _step(answer, "causal", 6),
            _step(prompt + answer + [101, 109], reset=True),
        ]},
        {"id": "turn_fresh", "steps": [_step(prompt + answer + [101, 109])]},
        {"id": "at_capacity", "n_ubatch": 4, "steps": [_step(prompt[:4])]},
        {"id": "oversized_prefix", "n_ubatch": 4, "steps": [
            _step(prompt, expect_reject=True), _step(prompt[:4], reset=True),
        ]},
        {"id": "reject_preserves_cache", "n_ubatch": 4, "steps": [
            _step(prompt[:4]), _step(prompt, pos=4, expect_reject=True),
            _step(answer[:2], "causal", 4),
        ]},
        {"id": "isolated_sequence", "steps": [
            _step([7, 17, 29], seq=1), _step(prompt, seq=0), _step(answer, "causal", 6),
        ]},
    ]


def _oracle(model, cases, out):
    report = {"reference_revision": _REFERENCE_REVISION, "cases": []}
    with torch.inference_mode():
        for case in cases:
            states = {}
            histories = {}
            result = {"id": case["id"], "steps": []}
            for index, step in enumerate(case["steps"]):
                seq = step.get("seq", 0)
                if step.get("reset", False):
                    states.pop(seq, None)
                    histories.pop(seq, None)
                if step.get("expect_reject", False):
                    result["steps"].append({"expect_reject": True})
                    continue
                ids = torch.tensor([step["tokens"]])
                pos = torch.arange(step["pos"], step["pos"] + ids.shape[1])[None]
                types = torch.ones_like(ids) if step["attention"] == "prefix" else torch.zeros_like(ids)
                output = model(ids, position_ids=pos, past_key_values=states.get(seq),
                               token_type_ids=types, use_cache=True)
                states[seq] = output.past_key_values
                rows = output.logits[0].float().numpy()
                histories.setdefault(seq, []).append((step["tokens"], types[0].tolist()))
                # Independent full-forward check of the HF cache and mask contract.
                full_ids = torch.tensor([[t for group, _ in histories[seq] for t in group]])
                full_types = torch.tensor([[t for _, group in histories[seq] for t in group]])
                direct = model(full_ids, token_type_ids=full_types, use_cache=False).logits[0, -len(rows):]
                np.testing.assert_allclose(rows, direct.numpy(), atol=2e-5, rtol=2e-5)
                if not step.get("all_logits", True):
                    rows = rows[-1:]
                filename = f"{case['id']}-{index}.f32"
                rows.astype(np.float32).tofile(out / filename)
                result["steps"].append({"file": filename, "shape": list(rows.shape)})
            report["cases"].append(result)
        prompt = torch.tensor([[2, 11, 23, 37, 41, 53]])
        generated = model.generate(prompt, token_type_ids=torch.ones_like(prompt),
                                   max_new_tokens=4, do_sample=False, eos_token_id=None,
                                   pad_token_id=0, use_cache=True)
        report["generate_smoke_tokens"] = generated[0].tolist()
    (out / "result.json").write_text(json.dumps(report, indent=2) + "\n")


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(73)
    torch.set_num_threads(4)
    config = HrmTextConfig(
        vocab_size=128, hidden_size=64, intermediate_size=128,
        num_hidden_layers=1, num_attention_heads=4, head_dim=16,
        H_cycles=2, L_cycles=3, max_position_embeddings=128,
        initializer_range=0.08, embedding_scale=12.5,
        prefix_lm=True, tie_word_embeddings=False,
        pad_token_id=0, bos_token_id=2, eos_token_id=None,
    )
    config._attn_implementation = "eager"
    model = HrmTextForCausalLM(config).float().eval()
    model.save_pretrained(args.output / "hf")
    for name, flag in [("true", True), ("false", False), ("absent", None)]:
        _write_gguf(model, args.output / f"hrm-{name}.gguf", flag)
    _write_gguf(model, args.output / "hrm-original.gguf", True, original_metadata=True)
    cases = _cases()
    (args.output / "cases.json").write_text(json.dumps(cases, indent=2) + "\n")
    controls = [{"id": "causal_control", "steps": [_step([2, 11, 23, 37, 41, 53])]}]
    (args.output / "metadata-cases.json").write_text(json.dumps(controls, indent=2) + "\n")
    oracle = args.output / "oracle"
    oracle.mkdir(exist_ok=True)
    _oracle(model, cases, oracle)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in args.output.glob("*.gguf")}
    payloads = {}
    for path in args.output.glob("*.gguf"):
        digest = hashlib.sha256()
        reader = gguf.GGUFReader(path)
        for tensor in sorted(reader.tensors, key=lambda t: t.name):
            digest.update(tensor.name.encode())
            digest.update(tensor.shape.tobytes())
            digest.update(tensor.data.tobytes())
        payloads[path.name] = digest.hexdigest()
    if len(set(payloads.values())) != 1:
        raise ValueError("Fixture tensor payloads differ across metadata variants")
    (args.output / "manifest.json").write_text(json.dumps({
        "seed": 73, "reference_revision": _REFERENCE_REVISION,
        "torch": torch.__version__, "gguf_sha256": hashes,
        "tensor_payload_sha256": payloads,
        "description": "Synthetic deterministic HRM; not a Mimir quality benchmark",
    }, indent=2) + "\n")


if __name__ == "__main__":
    _main()
