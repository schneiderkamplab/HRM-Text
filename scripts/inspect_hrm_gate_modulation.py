"""Read-only native gate probe on real sampled examples, with capped GPU memory."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import torch
import torch.distributed.checkpoint as dcp
import torch.nn.functional as F
import yaml
from models.baselines.hrm_v2 import HierarchicalReasoningModel, InvocationGate
from models.lm_head import LMHead
from models.accelerator import set_accelerator_type
from models.common import prepare_prefixlm_batch, wrap_tensor
from dataset_new import V1Dataset, V1DatasetConfig, V1DatasetIndices
from stop_training_at_complete_checkpoint import preserve


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--gpu', type=int, default=1)
    parser.add_argument('--examples', type=int, default=32)
    args = parser.parse_args()
    free = subprocess.check_output(['nvidia-smi', f'--id={args.gpu}',
                                   '--query-gpu=memory.free', '--format=csv,noheader,nounits'], text=True)
    if int(free.strip()) < 11000:
        raise RuntimeError('Need at least 11,000 MiB free for the 6 GiB capped probe')
    args.output.mkdir(parents=True, exist_ok=False)
    pinned = args.output / 'checkpoint'
    preserve(args.checkpoint, pinned, args.tag)
    cfg = yaml.safe_load((pinned / 'all_config.yaml').read_text())
    meta = yaml.safe_load((pinned / 'train_metadata.yaml').read_text())
    # This gate-only probe also supports early v2 checkpoints predating opt-in gates.
    combined = cfg['arch'] | meta | cfg['data'] | {'fwd_bwd_dtype': 'bfloat16', 'gates_enabled': True}
    torch.set_num_threads(8)
    model = LMHead(HierarchicalReasoningModel(combined), combined).eval()
    dcp.load({'model': model.state_dict()}, checkpoint_id=pinned / f'fsdp2_{args.tag}')
    for p in model.parameters():
        p.data = p.data.to(torch.bfloat16)
    device = torch.device(f'cuda:{args.gpu}')
    torch.cuda.set_device(device)
    torch.cuda.set_per_process_memory_fraction(6 * 1024**3 / torch.cuda.get_device_properties(device).total_memory)
    set_accelerator_type('sm100')
    model.to(device)
    samples = {}
    injection_energy = {}
    current = {}

    def hook(name):
        def record(module, inputs, output):
            hidden, other, alpha = inputs
            hidden, other = torch.broadcast_tensors(hidden, other)
            logits = F.linear(torch.cat((hidden, other), dim=-1), module.weight, module.bias)
            delta = (alpha.to(logits.dtype) * logits.tanh()).float()
            # Sample token positions, retaining every channel for token-dependence.
            positions = torch.linspace(0, len(delta)-1, min(64, len(delta)), device=device).long()
            samples.setdefault(name, []).append(delta[positions].cpu())
            diff = output.float() - other.float()
            energy = injection_energy.setdefault(name, [0., 0.])
            energy[0] += float(diff.square().sum())
            energy[1] += float(other.float().square().sum())
            current[name] = {'mean_delta': float(delta.mean()), 'mean_abs_delta': float(delta.abs().mean()),
                             'relative_injection_change': math.sqrt(float(diff.square().sum()) / max(float(other.float().square().sum()), 1e-30))}
        return record

    for name, module in model.named_modules():
        if isinstance(module, InvocationGate):
            module.register_forward_hook(hook(name))
    data = Path(cfg['data']['path'])
    dataset = V1Dataset(V1DatasetConfig(seed=0, dataset_path=str(data), batch_max_length=4096,
                                      drop_last_batch=False, target_only=True, rank=0, num_replicas=1))
    dataset._data = np.load(data / 'tokens.npy', mmap_mode='r')
    dataset._data_indices = V1DatasetIndices(**{key: np.load(data / 'epoch_0' / f'{key}.npy', mmap_mode='r')
                                              for key in ('inst_start', 'inst_len', 'resp_start', 'resp_len')})
    ix = dataset._data_indices
    rng = np.random.default_rng(42)
    rows = []
    while len(rows) < args.examples:
        row = int(rng.integers(len(ix.inst_len)))
        length = int(ix.inst_len[row]) + int(ix.resp_len[row]) - 1
        if row not in rows and 2 <= length <=4096 and ix.inst_len[row] > 0 and ix.resp_len[row] > 0:
            rows.append(row)
    with torch.inference_mode(), (args.output / 'examples.jsonl').open('w') as log:
        for row in rows:
            length = int(ix.inst_len[row]) + int(ix.resp_len[row]) - 1
            dataset.config.batch_max_length = length
            batch, scalars = dataset._load_batch(np.array([row]))
            batch = prepare_prefixlm_batch({k:v.to(device) for k,v in batch.items()} |
                                          {k:wrap_tensor(torch.tensor(v)) for k,v in scalars.items()})
            x = model.embed_tokens(batch['inputs'])
            model.model(None, x, bp_steps=8, **{k:v for k,v in batch.items() if k not in ('inputs','labels')})
            log.write(json.dumps({'row':row, 'tokens':length, 'gates':dict(current)})+'\n'); log.flush()
            print(f'{len(rows)} examples: processed row {row} ({length} tokens)', flush=True)
    result = {'checkpoint':str(args.checkpoint), 'tag':args.tag, 'ema':False,
              'alpha':float(model.model.gate_alpha), 'examples':args.examples, 'seed':42,
              'peak_gpu_allocated_mib':torch.cuda.max_memory_allocated()/1024**2, 'gates':{}}
    for name, chunks in samples.items():
        d = torch.cat(chunks)
        e = injection_energy[name]
        result['gates'][name] = {
            'mean_multiplier':float(1+d.mean()), 'mean_abs_modulation':float(d.abs().mean()),
            'multiplier_p05_p50_p95':(1+torch.quantile(d.flatten(),torch.tensor([.05,.5,.95]))).tolist(),
            'fraction_abs_gt_10pct':float((d.abs()>.1).float().mean()),
            'fraction_saturated_95pct':float((d.abs()>.95*result['alpha']).float().mean()),
            'mean_channel_std_across_tokens':float(d.std(dim=0).mean()),
            'relative_injection_change':math.sqrt(e[0]/max(e[1],1e-30))}
    (args.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)


if __name__ == '__main__':
    main()
