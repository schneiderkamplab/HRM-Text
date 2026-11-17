---
type: Reference
title: Wide Model Size Presets
description: Owner-selected width-4096 model with 24 L and 24 H layers, targeting the deep XXXXL parameter scale.
tags: [architecture, hrm, parameters]
status: stable
last_updated: 2026-11-02
confidence: high
---
# Wide Model Size Presets

The owner selected `arch/size@arch=XXXXL_wide`: 48 stored transformer layers,
split into 24 L and 24 H by the HRM network's `half_layers: true`, hidden
dimension 4096, 32 attention heads (128 dimensions/head), expansion 4.
Pre-normalization, epsilon 1e-6, RoPE theta 10000 and LeCun-normal initialization
follow the existing wide configuration. H/L cycles and BP settings are inherited
from the network/training configuration, not changed by this size preset.

The objective is approximately the parameter count of the existing deep XXXXL,
not a continuation of the earlier suggested 16+16 wide presets. The owner's
final choice of 24+24 supersedes the suggested 23+23 closest total-count match.
The briefly added `XXXXL_wide` 16+16 preset was replaced, not retained as an alias.
The subsequent `XXXL_wide` name for this 24+24 configuration was superseded
by the owner's explicit naming correction on 2026-09-30: save it as
`XXXXL_wide`. The owner subsequently approved a separate `XXXL_wide` YAML
with the 20+20 configuration below.

CPU meta-device construction with the 262144-token Gemma vocabulary verifies:

| Component | Parameters |
| --- | ---: |
| Transformer backbone | 10,519,314,432 |
| Separate embeddings and output head | 2,147,483,648 |
| Total | 12,666,798,080 |

This is 2.72% larger in total than deep XXXXL (12,331,253,760), with a
smaller backbone and wider vocabulary projections. Recurrent passes share
weights and do not multiply stored parameter counts. No training, export,
dataset identity changes or GPU benchmark was launched by this config addition.

## XXXL-wide

The owner requested a proposal with 20 L + 20 H layers and 24 heads,
approximately matching deep XXXL's parameter count. Width 3072 retains
128 dimensions/head; expansion remains 4. Meta-device counts with Gemma's
262144 vocabulary are 4,907,335,680 backbone and 6,517,948,416 total,
versus deep XXXL's 5,335,154,688 backbone and 6,408,896,512 total.
This is a close total-count match (1.70% larger), not an exact match:
wider untied vocabulary projections offset the smaller backbone.
Saved as `config/arch/size/XXXL_wide.yaml`. Hydra composition and meta-device
construction passed for all 13 size presets; no training was started or changed.

## Size Comparison

Sorted by total parameters, with a 262144-token vocabulary and the default
two-level HRM half_layers configuration. All counts below are billions.
Embeddings + head includes separate input and output matrices of equal size.

| Preset | L + H layers | Hidden | Heads | Expansion | Backbone | Embeddings + head | Total |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| XXS | 3 + 3 | 256 | 2 | 4 | 0.006 | 0.134 | 0.140 |
| XXS_wide | 2 + 2 | 384 | 3 | 4 | 0.008 | 0.201 | 0.209 |
| XS | 3 + 3 | 512 | 4 | 4 | 0.022 | 0.268 | 0.290 |
| S | 4 + 4 | 768 | 6 | 4 | 0.061 | 0.403 | 0.464 |
| B | 6 + 6 | 1024 | 8 | 4 | 0.167 | 0.537 | 0.704 |
| L | 12 + 12 | 1280 | 10 | 4 | 0.527 | 0.671 | 1.198 |
| XL | 16 + 16 | 1536 | 12 | 4 | 0.981 | 0.805 | 1.787 |
| XXL | 36 + 36 | 1792 | 14 | 4 | 3.039 | 0.940 | 3.978 |
| XXL_wide | 16 + 16 | 2560 | 20 | 4 | 2.747 | 1.342 | 4.089 |
| XXXL | 48 + 48 | 2048 | 16 | 4 | 5.335 | 1.074 | 6.409 |
| XXXL_wide | 20 + 20 | 3072 | 24 | 4 | 4.907 | 1.611 | 6.518 |
| XXXXL | 64 + 64 | 2560 | 20 | 4 | 10.989 | 1.342 | 12.331 |
| XXXXL_wide | 24 + 24 | 4096 | 32 | 4 | 10.519 | 2.147 | 12.667 |

## Exact Component Counts (verified 2026-11-02)

Meta-device construction of all 13 presets (hrm net, `half_layers: true`,
262144-token Gemma vocabulary) confirms the table above and separates the two
vocabulary projections. H and L stacks always hold equal parameter counts;
recurrent cycles share weights and do not multiply stored parameters.

| Preset | L + H layers | Hidden | Vocab | Transformer blocks | Embeddings | LM head | Total |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| XXS | 3 + 3 | 256 | 262144 | 5,505,024 | 67,108,864 | 67,108,864 | 139,722,752 |
| XXS_wide | 2 + 2 | 384 | 262144 | 7,667,712 | 100,663,296 | 100,663,296 | 208,994,304 |
| XS | 3 + 3 | 512 | 262144 | 22,020,096 | 134,217,728 | 134,217,728 | 290,455,552 |
| S | 4 + 4 | 768 | 262144 | 61,341,696 | 201,326,592 | 201,326,592 | 463,994,880 |
| B | 6 + 6 | 1024 | 262144 | 166,723,584 | 268,435,456 | 268,435,456 | 703,594,496 |
| L | 12 + 12 | 1280 | 262144 | 526,909,440 | 335,544,320 | 335,544,320 | 1,197,998,080 |
| XL | 16 + 16 | 1536 | 262144 | 981,467,136 | 402,653,184 | 402,653,184 | 1,786,773,504 |
| XXL | 36 + 36 | 1792 | 262144 | 3,038,773,248 | 469,762,048 | 469,762,048 | 3,978,297,344 |
| XXL_wide | 16 + 16 | 2560 | 262144 | 2,747,269,120 | 671,088,640 | 671,088,640 | 4,089,446,400 |
| XXXL | 48 + 48 | 2048 | 262144 | 5,335,154,688 | 536,870,912 | 536,870,912 | 6,408,896,512 |
| XXXL_wide | 20 + 20 | 3072 | 262144 | 4,907,335,680 | 805,306,368 | 805,306,368 | 6,517,948,416 |
| XXXXL | 64 + 64 | 2560 | 262144 | 10,989,076,480 | 671,088,640 | 671,088,640 | 12,331,253,760 |
| XXXXL_wide | 24 + 24 | 4096 | 262144 | 10,519,314,432 | 1,073,741,824 | 1,073,741,824 | 12,666,798,080 |

Counts are parameters only: RMSNorm and RoPE carry no parameters (RoPE cos/sin
are non-persistent buffers), and the persistent `zL_init` buffer of
`hidden_size` elements is excluded. Checkpoint-side counts that include
buffers are therefore larger by exactly `hidden_size`; for example, the
earlier XXL figure of `3,978,299,136` recorded in
[dfm8-xxl-epoch1-resume-2026-08-26](../dfm8-plan/dfm8-xxl-epoch1-resume-2026-08-26.md)
equals the parameter total `3,978,297,344` plus the 1,792-element `zL_init`
buffer. Per block: fused gated QKVO projection (`4h^2`), output projection
(`h^2`), SwiGLU gate+up (`2*h*i`) and down (`i*h`) with
`i = find_multiple(round(8h/3), 256)`.
