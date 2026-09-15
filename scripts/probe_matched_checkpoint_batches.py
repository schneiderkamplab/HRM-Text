"""Repack an identical data stream for isolated GAS8/GAS2 validation."""
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from models.common import IGNORE_LABEL_ID, prepare_prefixlm_batch, unwrap_tensor, wrap_tensor
from models.flash_attention_prefixlm_v2 import compute_aux_seq_tensors_scalars


def scalar(batch, key):
    return int(unwrap_tensor(batch[key]).item())


def signature(batches):
    result = {}
    for key in ("inputs", "labels", "position_ids", "prefix_lens", "causal_lens"):
        digest = hashlib.sha256()
        for batch in batches:
            size = scalar(batch, "numseqs" if key.endswith("lens") else "total_seqlen")
            digest.update(batch[key][:size].detach().cpu().contiguous().numpy().tobytes())
        result[key] = digest.hexdigest()
    result["tokens"] = sum(scalar(b, "total_seqlen") for b in batches)
    result["sequences"] = sum(scalar(b, "numseqs") for b in batches)
    return result


def merge(batches):
    capacity = sum(b["inputs"].numel() for b in batches)
    device = batches[0]["inputs"].device
    result = {}
    for key in ("inputs", "labels", "position_ids"):
        values = torch.cat([b[key][:scalar(b, "total_seqlen")] for b in batches])
        result[key] = F.pad(values, (0, capacity - values.numel()), value=IGNORE_LABEL_ID if key == "labels" else 0)
    lens = [np.concatenate([b[key][:scalar(b, "numseqs")].cpu().numpy() for b in batches])
            for key in ("prefix_lens", "causal_lens")]
    tensors, scalars = compute_aux_seq_tensors_scalars(*lens, capacity)
    result.update({key: torch.from_numpy(value).to(device) for key, value in tensors.items()})
    result.update({key: wrap_tensor(torch.tensor(value)) for key, value in scalars.items()})
    return prepare_prefixlm_batch(result)


def install(pretrain):
    original = pretrain.train_accumulated_batches
    target = int(os.environ["PROBE_MATCH_GAS"])
    assert target in (2, 8)

    def run(config, rank, state, batches, *args, **kwargs):
        assert len(batches) == 8 and state.carry is None
        before = signature(batches)
        if target == 2:
            batches = [merge(batches[:4]), merge(batches[4:])]
        assert signature(batches) == before, "Repacking changed supervised examples"
        path = Path(os.environ["PROBE_OUTPUT"]) / f"batch_audit_rank{rank}.jsonl"
        with path.open("a") as handle:
            handle.write(json.dumps({"step": state.step, "effective_gas": target, **before}) + "\n")
        return original(config, rank, state, batches, *args, **kwargs)

    pretrain.train_accumulated_batches = run
