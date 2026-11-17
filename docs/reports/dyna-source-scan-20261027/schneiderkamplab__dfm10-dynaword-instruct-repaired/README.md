---
license: other
language:
- da
tags:
- instruction-tuning
- chat
- dfm10
- repaired
pretty_name: dfm10-dynaword-instruct-repaired
---

# dfm10-dynaword-instruct-repaired

Prompt-repaired and audited DynaWord instruction variants.

## Contents

- Format: gzip-compressed JSON Lines under `data/train-*.jsonl.gz`
- Schema: chat `messages`, optional `condition` and `tools`, plus provenance
- Shards: 1
- Rows: 65,548
- Category: Danish instruction

## Upstream material

- `oliverkinch/da-instruct-dynaword`
- `oliverkinch/da-instruct-dynaword-hq`
- `oliverkinch/da-instruct-dynaword-contemporary`
- `oliverkinch/da-instruct-dynaword-contemporary-hq`

## Processing

Targets are retained while mismatched prompts are regenerated and re-audited.

Every packaged row is taken from the accepted source tree used by the final
DFM10 build. Tokenized arrays and epoch sampling indices are not included.

## License and release review

This package does not assert a new license over upstream material. Preserve the
upstream licenses, notices, and attribution requirements. Review upstream terms and dataset-card attribution before upload.

## Validate

```bash
python recreate_dataset.py
```
