---
type: Technical Reference
title: Size-ladder update on (2026-05-29)
description: 'Chronological record from Residual Risk: Size-ladder update on (2026-05-29).'
tags:
- flashattention
- b200
- cuda
- performance
status: stable
last_updated: 2026-09-17
confidence: high
part_of: /pages/flashattention-b200/residual-risk.md
---
# Size-ladder update on (2026-05-29)

Part of [Residual Risk](/pages/flashattention-b200/residual-risk.md).

Size-ladder update on 2026-05-29: added only the non-wide branch above `XXL`:

```text
XXXL:  n_layers=96,  hidden_size=2048, num_heads=16, head_dim=128
XXXXL: n_layers=128, hidden_size=2560, num_heads=20, head_dim=128
```

No new `*_wide` configs were kept. Hydra config composition was checked successfully for both `arch/size@arch=XXXL` and `arch/size@arch=XXXXL`. Confidence: high.

Historical parameter counts recorded for the May 2026 size configs, computed from the layer/embedding formula and matching the observed `XXS` W&B count:

```text
XXS:          39,059,456
XXS_wide:     57,999,360
XS:           89,128,960
S:           162,004,992
B:           300,941,312
L:           694,681,600
XL:        1,182,793,728
XXL:       3,273,654,272
XXL_wide:  3,082,813,440
XXXL:      5,603,590,144
XXXXL:    11,324,620,800
```

Confidence: high.
