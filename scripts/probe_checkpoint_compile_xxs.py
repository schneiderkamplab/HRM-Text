"""Isolated XXS FSDP/FA4 probe entry point; never patch production modules on disk."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import torch
if "LOCAL_RANK" in os.environ:
    torch.cuda.set_device(int(os.environ["LOCAL_RANK"]))
import pretrain
from models.transformer import TransformerBlock
from torch.distributed._composable import checkpoint


def select_probe_blocks(model, policy):
    counters = {"H_level": 0, "L_level": 0}
    selected = []
    for name, block in model.named_modules():
        if not isinstance(block, TransformerBlock):
            continue
        level = next((key for key in counters if key in name.split(".")), None)
        if level is None:
            continue
        index = counters[level]
        counters[level] += 1
        h_interval = {"h_half_l_full": 2, "h_third_l_full": 3, "h_quarter_l_full": 4}.get(policy)
        if h_interval:
            include = level == "L_level" or index % h_interval == 0
        else:
            include = level == "L_level" and (policy == "l_only" or index % 4 != 3)
        if include:
            selected.append(block)
    return selected


def main():
    if os.environ.get("PROBE_MATCH_GAS"):
        from probe_matched_checkpoint_batches import install
        install(pretrain)
    rank = int(os.environ["LOCAL_RANK"])
    torch.cuda.set_device(rank)
    # Bound this side experiment below the available production headroom.
    torch.cuda.set_per_process_memory_fraction(float(os.environ.get("PROBE_MEMORY_FRACTION", "0.10")), rank)
    if os.environ.get("PROBE_MEMORY_GIB"):
        fraction = float(os.environ["PROBE_MEMORY_GIB"]) * 2**30 / torch.cuda.get_device_properties(rank).total_memory
        torch.cuda.set_per_process_memory_fraction(min(fraction, 1.), rank)
    torch.set_num_threads(1)
    torch._inductor.config.compile_threads = 1
    if os.environ.get("PROBE_COMPILE_SCOPE") == "no_fusion":
        torch._inductor.config.max_fusion_size = 1
        torch._inductor.config.epilogue_fusion = False
        torch._inductor.config.prologue_fusion = False
    original_apply = pretrain.apply_activation_checkpointing

    def apply(model, mode):
        if os.environ.get("PROBE_BLOCK_COMPILE") == "1":
            for name, block in model.named_modules():
                if isinstance(block, TransformerBlock):
                    scope = os.environ.get("PROBE_COMPILE_SCOPE", "block")
                    if scope in {"optimizer", "eager"}:
                        continue
                    if scope == "no_fusion":
                        scope = "block"
                    if scope in {"l_block", "h_block"}:
                        level = "L_level" if scope == "l_block" else "H_level"
                        if level not in name.split("."):
                            continue
                        scope = "block"
                    backend = os.environ.get("PROBE_COMPILE_BACKEND", "inductor")
                    if scope == "eager_norm":
                        block.norm = torch.compiler.disable(block.norm)
                    if scope in {"block", "eager_norm"}:
                        block.forward = torch.compile(block.forward, dynamic=False, backend=backend)
                    elif scope in {"attn", "mlp", "components"}:
                        if scope in {"attn", "components"}:
                            block.attn.forward = torch.compile(block.attn.forward, dynamic=False, backend=backend)
                        if scope in {"mlp", "components"}:
                            block.mlp.forward = torch.compile(block.mlp.forward, dynamic=False, backend=backend)
                    else:
                        raise ValueError(f"Unknown compile scope {scope}")
        policy = os.environ.get("PROBE_CHECKPOINT_POLICY", "")
        if policy:
            if policy not in {"h_half_l_full", "h_third_l_full", "h_quarter_l_full", "l_only", "l_three_quarters"}:
                raise ValueError(f"Unknown probe policy {policy}")
            blocks = select_probe_blocks(model, policy)
            for block in blocks:
                checkpoint(block)
            print(f"Probe checkpoint policy={policy} blocks={len(blocks)}", flush=True)
            return set(blocks)
        return original_apply(model, mode)

    pretrain.apply_activation_checkpointing = apply
    original_step = pretrain.AdamATan2.step
    optimizer_only = os.environ.get("PROBE_COMPILE_SCOPE") == "optimizer"
    compiled_optimizer_step = torch.compile(original_step, dynamic=False) if optimizer_only else None
    captured = False

    def step(optimizer, *args, **kwargs):
        nonlocal captured
        if not captured:
            gradients = {}
            for group_id, group in enumerate(optimizer.param_groups):
                for i, parameter in enumerate(group["params"]):
                    grad = parameter.grad
                    if grad is not None:
                        local = grad.to_local() if hasattr(grad, "to_local") else grad
                        gradients[f"{group_id}/{i}"] = local.detach().cpu()
            torch.save(gradients, Path(os.environ["PROBE_OUTPUT"]) / f"first_grad_rank{rank}.pt")
            captured = True
        if compiled_optimizer_step is not None:
            # Tensor-valued LR avoids a new graph for every cooldown value.
            rates = [group["lr"] for group in optimizer.param_groups]
            try:
                for group, rate in zip(optimizer.param_groups, rates):
                    group["lr"] = torch.tensor(rate, device=group["params"][0].device, dtype=torch.float64)
                return compiled_optimizer_step(optimizer, *args, **kwargs)
            finally:
                for group, rate in zip(optimizer.param_groups, rates):
                    group["lr"] = rate
        return original_step(optimizer, *args, **kwargs)

    pretrain.AdamATan2.step = step
    pretrain.launch()


if __name__ == "__main__":
    main()
