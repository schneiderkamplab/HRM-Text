# Atomic multiview judge comparison

Same 200 parent conversations. One binary question per request; no explanations or JSON.

All view acceptance requires every applicable criterion to pass. Unresolved includes missing, invalid or over-context results; an unfinished model is reported entirely unresolved until its journals are finalized.

## Per-view coverage

| Model | View | Accept | Reject | Unresolved |
|---|---|---:|---:|---:|
| odin | seed | 167 | 31 | 2 |
| odin | message | 441 | 106 | 11 |
| odin | conversation | 187 | 4 | 9 |
| odin | message_pair | 319 | 22 | 17 |
| odin | exchange_pair | 60 | 1 | 18 |
| qwen27b | seed | 84 | 116 | 0 |
| qwen27b | message | 148 | 410 | 0 |
| qwen27b | conversation | 103 | 97 | 0 |
| qwen27b | message_pair | 129 | 229 | 0 |
| qwen27b | exchange_pair | 33 | 46 | 0 |
| flash | seed | 114 | 86 | 0 |
| flash | message | 275 | 283 | 0 |
| flash | conversation | 190 | 10 | 0 |
| flash | message_pair | 247 | 111 | 0 |
| flash | exchange_pair | 63 | 16 | 0 |
| mimir | seed | 82 | 5 | 113 |
| mimir | message | 380 | 51 | 127 |
| mimir | conversation | 119 | 2 | 79 |
| mimir | message_pair | 202 | 55 | 101 |
| mimir | exchange_pair | 62 | 4 | 13 |

## Frozen manual subset: 200 assistant messages

40 definite defects, 134 clean, 26 borderline. These are the earlier holistic assistant manual labels, not native-speaker certification. The expanded criterion-specific review below is separate and does not overwrite these historical labels.

| Judges | Accepted | Defects accepted / 40 | Clean rejected / 134 | Borderlines accepted / 26 | Unresolved |
|---|---:|---:|---:|---:|---:|
| odin | 174 | 21 | 2 | 21 | 2 |
| qwen27b | 78 | 6 | 70 | 8 | 0 |
| flash | 122 | 9 | 32 | 11 | 0 |
| mimir | 171 | 33 | 2 | 24 | 19 |
| odin+qwen27b | 73 | 2 | 71 | 8 | 0 |
| odin+flash | 118 | 7 | 33 | 10 | 1 |
| odin+mimir | 150 | 18 | 4 | 20 | 21 |
| qwen27b+flash | 69 | 2 | 75 | 8 | 0 |
| qwen27b+mimir | 70 | 6 | 70 | 8 | 8 |
| flash+mimir | 104 | 7 | 33 | 11 | 15 |
| odin+qwen27b+flash | 68 | 2 | 76 | 8 | 0 |
| odin+qwen27b+mimir | 65 | 2 | 71 | 8 | 8 |
| odin+flash+mimir | 101 | 6 | 34 | 10 | 16 |
| qwen27b+flash+mimir | 61 | 2 | 75 | 8 | 8 |
| odin+qwen27b+flash+mimir | 60 | 2 | 76 | 8 | 8 |

## Expanded blind manual review

Assistant manual judgments of seeds, every message, full conversations and adjacent windows. Not independent native-speaker certification. Grammar, clarity, consistency and compliance are distinct questions; borderline cases are not definite defects. Repeated views are correlated, so these are check counts, not independent sample sizes or production rejection rates.

[Annotation source](dfm16-multiview-manual-labels.json). Rebuild with `python -m scripts.dfm16_manual_multiview`.

| Model | View | Labelled checks | Defects | Defects accepted | Clear | Clear rejected | Borderline | Borderline accepted | Unresolved |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| odin | seed | 600 | 68 | 35 | 498 | 3 | 34 | 33 | 3 |
| odin | message | 1674 | 171 | 83 | 1412 | 14 | 91 | 74 | 13 |
| odin | conversation | 400 | 32 | 23 | 337 | 3 | 31 | 29 | 11 |
| odin | message_pair | 637 | 21 | 12 | 581 | 18 | 35 | 30 | 23 |
| odin | exchange_pair | 79 | 8 | 4 | 69 | 0 | 2 | 2 | 18 |
| qwen27b | seed | 600 | 68 | 11 | 498 | 128 | 34 | 20 | 0 |
| qwen27b | message | 1674 | 171 | 46 | 1412 | 527 | 91 | 46 | 0 |
| qwen27b | conversation | 400 | 32 | 9 | 337 | 111 | 31 | 12 | 0 |
| qwen27b | message_pair | 637 | 21 | 4 | 581 | 277 | 35 | 9 | 0 |
| qwen27b | exchange_pair | 79 | 8 | 5 | 69 | 42 | 2 | 1 | 0 |
| flash | seed | 600 | 68 | 17 | 498 | 82 | 34 | 23 | 0 |
| flash | message | 1674 | 171 | 51 | 1412 | 257 | 91 | 55 | 0 |
| flash | conversation | 400 | 32 | 28 | 337 | 8 | 31 | 30 | 0 |
| flash | message_pair | 637 | 21 | 16 | 581 | 135 | 35 | 25 | 0 |
| flash | exchange_pair | 79 | 8 | 7 | 69 | 14 | 2 | 1 | 0 |
| mimir | seed | 600 | 68 | 53 | 498 | 0 | 34 | 22 | 244 |
| mimir | message | 1674 | 171 | 121 | 1412 | 35 | 91 | 75 | 257 |
| mimir | conversation | 400 | 32 | 24 | 337 | 1 | 31 | 25 | 106 |
| mimir | message_pair | 637 | 21 | 15 | 581 | 53 | 35 | 24 | 139 |
| mimir | exchange_pair | 79 | 8 | 5 | 69 | 3 | 2 | 1 | 13 |
