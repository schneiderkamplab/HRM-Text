---
type: Runbook
title: DFM Mimir Hugging Face Space Demo
description: Deployment and maintenance notes for the public ZeroGPU demonstration of DFM Mimir.
tags: [mimir, hugging-face, spaces, gradio, zerogpu, oauth, inference]
status: stable
last_updated: 2026-09-17
confidence: high
sources:
  - id: mimir-model
    resource: https://huggingface.co/danish-foundation-models/DFM-Mimir
    title: DFM Mimir model repository
    author: org:danish-foundation-models
  - id: mimir-space
    resource: https://huggingface.co/spaces/peter-sk/DFM-Mimir-Demo
    title: DFM Mimir demonstration Space
    author: person:Peter-Schneider-Kamp
---
# DFM Mimir Hugging Face Space Demo

## Deployment

- Public Space: <https://huggingface.co/spaces/peter-sk/DFM-Mimir-Demo>
- Direct app: <https://peter-sk-dfm-mimir-demo.hf.space/>
- Repository source: `spaces/dfm-mimir-demo/`
- Runtime: Hugging Face ZeroGPU (`zero-a10g`), Gradio 6.24.0, Python 3.12.
- Model: `danish-foundation-models/DFM-Mimir`, loaded lazily in BF16 through
  the native Transformers `HrmTextForCausalLM` implementation.

The Space was placed in Peter Schneider-Kamp's namespace because requesting
ZeroGPU in the `danish-foundation-models` organization returned HTTP 402: the
organization does not currently have the Team or Enterprise entitlement
required for ZeroGPU organization Spaces.

## Access And Credential Handling

**Superseded access-policy claim (2026-09-17):** The gated research-license
description below records the 2026-08-18 deployment. The public model Hub API
now reports `gated: false` and Apache-2.0 metadata at revision
`2844f0178e695d7d9ce182cb660671fd34c76ce5`. The local demo source still contains
the older OAuth flow; its live deployment was not rechecked. See
[Apple chat feasibility](mimir-apple-chat-feasibility.md) for the current
model/runtime inspection.

DFM Mimir is gated. The Space enables Hugging Face OAuth with the
`gated-repos` scope and requires each visitor to sign in and accept the model's
research licence. The visitor's short-lived OAuth token is passed directly to
`transformers.from_pretrained`; no shared Hugging Face token is committed,
configured as a Space secret, or stored in the application source.

The deployment credential used to create and push the Space was held only in
an interactive shell environment. Do not replace the visitor OAuth design
with a repository token unless there is an explicit policy decision to let the
Space bypass per-user gating.

## Inference Contract

- Use the tokenizer's native Gemma-4-style chat template with
  `enable_thinking=False` and `add_generation_prompt=True`.
- Supply prompt `token_type_ids` containing ones. This preserves the
  prefix-LM prompt semantics expected by the exported HRM-Text model.
- Respect the 4,096-token context window. The app removes the oldest complete
  user/assistant pairs before rejecting an oversized current prompt.
- Keep one concurrent generation per ZeroGPU worker. Controls expose answer
  length, temperature, top-p, and repetition penalty.
- The interface supports Danish and English, system instructions, multi-turn
  history, examples, and an MCP endpoint.

## Verification

On 2026-08-18 the Hub reported stage `RUNNING`, requested/current hardware
`zero-a10g`, one replica, and commit
`b575cbb8e29c9245df00404741c6ba93210151ec`. The root page and Gradio config
both returned HTTP 200. Desktop (1280 px) and mobile (390 CSS px) Playwright
captures showed a nonblank, responsive interface without control overlap.
An authenticated API smoke test using the same visitor-OAuth path loaded the
gated model and returned `hej` for the constrained Danish prompt
`Svar kun med ordet hej.`. The test credential was held only in memory, unset
immediately afterward, and was not persisted as a Hub login or Space secret.

## Maintenance

Validate locally before deployment:

```bash
python -m py_compile spaces/dfm-mimir-demo/app.py
```

The `hf upload` client attempted to recreate the existing Space during this
deployment. A plain Git clone and push worked as a fallback. If that workaround
is needed again, use a transient credential helper and never embed the token in
the remote URL or Git configuration.
