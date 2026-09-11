"""Local, opt-in telemetry of actual optimizer updates."""
import json
import math
from pathlib import Path

import torch
import torch.distributed as dist


def append_jsonl(path, record):
    def clean(value):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items()}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Caller is rank zero; each stage has its own output file.
    with destination.open("a") as stream:
        stream.write(json.dumps(clean(record), allow_nan=False) + "\n")
        stream.flush()


def local(value):
    return value.to_local() if hasattr(value, "to_local") else value


class ParameterUpdateProbe:
    """Observe actual updates, including weight decay, using CPU shard copies.

    Reduce squared sums and counts, not rank-local RMS values. Replicated
    parameters are counted repeatedly, which cancels in RMS and norm ratios.
    Only scalar statistics cross ranks; no full parameters are gathered.
    """

    def __init__(self, model):
        self.parameters = list(model.named_parameters())
        self.before = {
            name: local(parameter).detach().to(device="cpu", copy=True)
            for name, parameter in self.parameters
        }

    @torch.no_grad()
    def finish(self, device):
        rows = []
        for name, parameter in self.parameters:
            before = self.before.pop(name).double()
            after = local(parameter).detach().to(device="cpu", dtype=torch.float64)
            delta = after - before
            rows.append([before.square().sum().item(), after.square().sum().item(),
                         delta.square().sum().item(), before.numel()])
        values = torch.tensor(rows, device=device, dtype=torch.float64)
        if dist.is_initialized():
            dist.all_reduce(values)
        result = []
        for (name, _), (weight_sq, after_sq, update_sq, count) in zip(self.parameters, values.tolist()):
            result.append(dict(
                parameter=name,
                weight_rms_before=math.sqrt(weight_sq / max(count, 1)),
                weight_rms_after=math.sqrt(after_sq / max(count, 1)),
                update_rms=math.sqrt(update_sq / max(count, 1)),
                update_to_weight=math.sqrt(update_sq / max(weight_sq, 1e-300)),
            ))
        self.parameters.clear()
        return result
