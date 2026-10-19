"""Bounded-memory, no-W&B native EMA generation canary for the matched pilot."""
import argparse
import gc
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import torch
from simple_inference_engine import inference_load_checkpoint, inference_generate
from models.baselines.hrm_v2 import InvocationGate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gpu', type=int, default=1)
    args = parser.parse_args()
    torch.set_num_threads(8)
    torch.cuda.set_device(args.gpu)
    torch.cuda.set_per_process_memory_fraction(
        6*1024**3 / torch.cuda.get_device_properties(args.gpu).total_memory)
    root = ROOT / 'logs/scheduler/hrm_v2_control_3820000_native'
    prompts = [('direct', 'Choose the correct option. Return only the option letter.\n\n'
                'Which is a mammal?\nA. Dolphin\nB. Trout'),
               ('direct', 'Hvad er hovedstaden i Danmark? Svar kort.')]
    results = []
    for mode in ('v2', 'control'):
        # Load full optimizer/EMA on CPU, then only the BF16 model goes to GPU.
        # This changes placement during the canary, not loading or EMA semantics.
        with patch('torch.cuda.is_available', return_value=False):
            ckpt = inference_load_checkpoint(str(root/'checkpoints'/mode), None, True,
                                              ckpt_tag='step_3820000')
        gates = [g for g in ckpt.model.modules() if isinstance(g, InvocationGate)]
        assert len(gates) == (8 if mode == 'v2' else 0)
        assert all(torch.isfinite(g.weight).all() and g.weight.abs().max() > 0 for g in gates)
        if gates:
            assert float(ckpt.model.model.gate_alpha) == 1
        ckpt.model.to(f'cuda:{args.gpu}')
        tokens = [ckpt.tokenize_prompt(*p).tolist() for p in prompts]
        outputs = list(inference_generate(ckpt, iter(enumerate(prompts)), 256, 24, 1, 0))
        assert len(outputs) == len(prompts) and all(text.strip() for _, text in outputs)
        results.append(dict(mode=mode, ema=True, gates=len(gates), tokens=tokens,
                            outputs=outputs, peak_mib=torch.cuda.max_memory_allocated()/1024**2))
        print(json.dumps(results[-1]), flush=True)
        del ckpt, gates
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
    assert results[0]['tokens'] == results[1]['tokens']
    (root/'smoke.json').write_text(json.dumps(results, indent=2)+'\n')


if __name__ == '__main__':
    main()
