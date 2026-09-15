"""Small FP32 AdamATan2 state-parity check for optimizer-only compilation."""
import torch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.adam_atan2 import AdamATan2


def main():
    torch.set_num_threads(1)
    torch._inductor.config.compile_threads = 1
    torch.manual_seed(42)
    a = [torch.nn.Parameter(torch.randn(32, 32)) for _ in range(3)]
    b = [torch.nn.Parameter(p.detach().clone()) for p in a]
    opts = [AdamATan2(ps, lr=7.5e-5, ema=.9999,
                     parameter_lr_scales=dict(zip(ps, [1., .5, 1/6]))) for ps in (a, b)]
    compiled = torch.compile(AdamATan2.step, dynamic=False)
    for step in range(5):
        rate = 7.5e-5 * (1 - step / 10)
        for x, y in zip(a, b):
            x.grad = torch.randn_like(x)
            y.grad = x.grad.clone()
        opts[0].param_groups[0]["lr"] = rate
        opts[1].param_groups[0]["lr"] = torch.tensor(rate, dtype=torch.float64)
        opts[0].step()
        compiled(opts[1])
        for x, y in zip(a, b):
            torch.testing.assert_close(x, y, atol=1e-6, rtol=1e-6)
            for key, value in opts[0].state[x].items():
                torch.testing.assert_close(value, opts[1].state[y][key], atol=1e-6, rtol=1e-6)
    print("PASS: parameters, moments, step counters and EMA across five varying-LR updates")


if __name__ == "__main__":
    main()
