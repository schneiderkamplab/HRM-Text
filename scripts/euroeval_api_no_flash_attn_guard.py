#!/usr/bin/env python3
"""Run EuroEval API benchmarking without tripping its flash_attn import guard.

This wrapper is for API-only evaluation where EuroEval talks to a separate
OpenAI-compatible server. The HRM server process still sees the normal
environment, including FA4. Only this EuroEval process hides `flash_attn` from
EuroEval's package-compatibility check.
"""

from __future__ import annotations

import importlib.util
import os
import sys


_real_find_spec = importlib.util.find_spec


def _find_spec_without_flash_attn(name: str, *args, **kwargs):
    if name == "flash_attn" or name.startswith("flash_attn."):
        return None
    return _real_find_spec(name, *args, **kwargs)


importlib.util.find_spec = _find_spec_without_flash_attn

if max_concurrent_calls := os.environ.get("EUROEVAL_MAX_CONCURRENT_CALLS"):
    from euroeval.benchmark_modules.litellm import LiteLLMModel  # noqa: E402

    _real_litellm_init = LiteLLMModel.__init__

    def _init_with_max_concurrent_calls(self, *args, **kwargs):
        _real_litellm_init(self, *args, **kwargs)
        self.buffer["max_concurrent_calls"] = int(max_concurrent_calls)

    LiteLLMModel.__init__ = _init_with_max_concurrent_calls

from euroeval.cli import benchmark  # noqa: E402


if __name__ == "__main__":
    sys.exit(benchmark())
