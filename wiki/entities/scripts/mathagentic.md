---
type: Software Source Code
title: Mathagentic
description: Standalone package for converting executable arithmetic programs into Gemma-4-native HRM-Text SFT.
tags: [dfm11, math, tool-calling, dataset-conversion, submodule]
status: draft
last_updated: 2026-09-03
confidence: high
---
# Mathagentic

`mathagentic/` is an independently versioned package and git submodule. It
converts TinyGSM Python programs and GSM8K-aligned Prolog programs into complete
native tool trajectories, validates call/result/final-answer invariants, and
can tokenize the resulting JSONL directly into HRM-Text task arrays with its
bundled Gemma 4 native template.

The Python program entrypoint is normalized to `solve()` and exposed through
`execute_python`. Prolog retains `solve/1` and is exposed through
`execute_prolog`. Each source row creates two assistant targets: the tool call
and the final exact `\boxed{...}` answer. Definitions and tool results remain
instruction context and receive no response loss.

See the submodule's own `wiki/` bundle for source gates, commands, security
boundaries, and build status.

The dedicated Conda environment is `/home/ucloud/miniforge3/envs/mathagentic`.
It uses Python 3.12 and conda-forge's SWI-Prolog 10.0; install the package's
Python dependencies into that interpreter with `uv pip install -e '.[test]'`.

The 2026-09-03 local conversion produced 500,000 TinyGSM execution-verified
candidates and 7,473 GSM8K-aligned Prolog trajectories. TinyGSM still requires
independent semantic admission. All Prolog gold mismatches were individually
reviewed, and 12 malformed source programs were narrowly repaired; both forms
of intervention are recorded as versioned, row-level provenance.
