"""CPU-only checkpoint/compile boundary isolation, independent of production."""
import argparse
import copy
import json
from pathlib import Path
import traceback

import torch
from torch import nn
from torch.distributed._composable import checkpoint


class Block(nn.Module):
    def __init__(self):
        super().__init__()
        self.up = nn.Linear(32, 128, bias=False)
        self.down = nn.Linear(64, 32, bias=False)

    def forward(self, x):
        a, b = self.up(x).chunk(2, dim=-1)
        return x + self.down(torch.nn.functional.silu(a) * b) * 0.1


class Recurrent(nn.Module):
    def __init__(self):
        super().__init__()
        self.h = Block()
        self.l = Block()

    def forward(self, x):
        h, l = x, x * 0
        for _ in range(2):
            for _ in range(3):
                l = self.l(l + h)
            h = self.h(h + l)
        return h


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch._inductor.config.compile_threads = 1
    torch.manual_seed(0)
    reference = Recurrent()
    x = torch.randn(16, 32)
    reference(x).square().mean().backward()
    results = []
    for mode in ("eager", "outer_eager", "outer_aot_eager", "outer_inductor", "inner_inductor"):
        torch._dynamo.reset()
        model = copy.deepcopy(reference)
        model.zero_grad(set_to_none=True)
        if mode == "inner_inductor":
            for block in (model.h, model.l):
                block.forward = torch.compile(block.forward, backend="inductor", fullgraph=True)
        checkpoint(model.h)
        checkpoint(model.l)

        def step(value):
            loss = model(value).square().mean()
            loss.backward()
            return loss.detach()

        run = step
        if mode.startswith("outer_"):
            run = torch.compile(step, backend=mode.removeprefix("outer_"), dynamic=False)
        try:
            loss = run(x)
            for p, q in zip(model.parameters(), reference.parameters()):
                torch.testing.assert_close(p.grad, q.grad, rtol=1e-4, atol=1e-4)
            results.append({"mode": mode, "status": "pass", "loss": loss.item()})
        except Exception as error:
            results.append({"mode": mode, "status": "fail", "error": str(error),
                            "traceback": traceback.format_exc()})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2))
        print(mode, results[-1]["status"], flush=True)


if __name__ == "__main__":
    main()
