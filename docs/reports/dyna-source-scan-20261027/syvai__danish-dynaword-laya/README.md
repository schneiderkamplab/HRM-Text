---
language:
- da
license: other
task_categories:
- text-classification
tags:
- laya
- typed-decisions
- danish
- calibrated-decisions
size_categories:
- 10K<n<100K
configs:
- config_name: default
  data_files:
  - split: train
    path: data/ctx16k/train.parquet
  - split: test
    path: data/ctx16k/test.parquet
- config_name: ctx1024
  data_files:
  - split: train
    path: data/ctx1024/train.parquet
  - split: test
    path: data/ctx1024/test.parquet
---

# Danish Dynaword Laya

Danish training data for [Laya](https://huggingface.co/convaiinnovations/laya) in the same format as [LocalLLaMA/typed-decisions](https://huggingface.co/datasets/LocalLLaMA/typed-decisions), so it plugs directly into Laya's official fine-tuning notebook.

It is derived from [syvai/danish-dynaword-extractions](https://huggingface.co/datasets/syvai/danish-dynaword-extractions): LLM-designed JSON schemas and extractions over Danish Dynaword texts, converted into typed questions with answers.

## Configs and size

| config | state window | train cases / questions | test cases / questions |
|---|---|---|---|
| `default` | up to 16,098 tokens (`max_len` 16384) | 41,300 / 336,662 | 802 / 6,672 |
| `ctx1024` | up to 738 tokens (`max_len` 1024, Laya's default) | 75,708 / 337,395 | 1,464 / 6,664 |

Token counts use the tokenizer of Laya's multilingual checkpoint (mmBERT). The split is by source document (about 2% of documents in test), so no text appears in both splits.

**The 16k config goes past the encoder's pretraining length.** mmBERT-base was pretrained to 8,192 tokens (`max_position_embeddings` 8192). Its rotary position encoding runs at 16k, but positions beyond 8k are extrapolation. Train with `cfg["max_len"] = 16384` and `cfg["head_max_len"] = 256`.

**Compute.** Laya encodes the full state once per question, so training cost scales with state length times questions. Per epoch, `default` is about 1.49B state tokens (mean 5,194 per question, p95 16,098) versus about 0.18B for `ctx1024` (mean 605).

### How long documents are handled

The median document is 582 tokens, 95% are under 14.6k and the longest is 75k. A document that fits in one window becomes one state with all its questions. Longer documents are split: the first window starts at token 0 and carries the document-level questions, and further windows start 200 tokens before the records they hold. Document-level choice and yes/no questions on documents longer than one window are dropped, since the evidence may be outside it (412 questions at 16k, 5,587 at 1k). A case holds at most 64 questions; larger groups are split into several cases with the same state.

## Columns

| column | content |
|---|---|
| `id` | `<source doc id>__<case index>` |
| `doc_id` | id in `syvai/danish-dynaword-extractions` |
| `workflow` | Dynaword source (e.g. `enevaeldens`, `kb`, `wiki`, `retspraksis`) |
| `split` | `train` or `test` |
| `state` | JSON string: the text window the questions are about |
| `questions` | JSON string: `{qid: {type, instructions, criteria}}` |
| `gold` | JSON string: `{qid: {type, label, probabilities, confidence[, noul]}}` |
| `n_questions` | questions in the case (max 64 in `default`, 16 in `ctx1024`) |
| `truncated` | the source document was longer than the window |
| `question_kinds` | JSON string: `{qid: kind}`, see below |

## Question kinds

| kind | Laya type | built from | count |
|---|---|---|---|
| `record_enum` | choice | enum field on a record in a list, addressed as `Om "<identifier>" (<field>): ...` | 184,167 |
| `record_bool` | noul | boolean field on a record in a list | 17,959 |
| `enum` | choice | document-level enum field | 5,304 |
| `bool` | noul | document-level boolean field | 8,739 |
| `presence` | noul | "Oplyser teksten følgende: X": true only if the value is found verbatim in the window, false if the extraction was null | 69,177 |
| `presence_negative` | noul | a specific field description borrowed from a document of a different source, answer false | 57,988 |

Counts are for `default`.

Nullable enums get an extra option `ikke_angivet`.

## How it was built and cleaned

- Record identifiers must occur in the text, be unique among the document's records, and be unambiguous inside the case window. Otherwise the record's questions are dropped.
- Options are shuffled per question. The extraction LLM put the correct answer first 43% of the time; after shuffling it is 21%, close to chance.
- True presence questions are capped at 2 per document and balanced with cross-source negatives. Before this, 96% of presence questions were true.
- Quoted example values are stripped from presence descriptions, since they often contained the answer (e.g. "Dokumentets type, her 'Proclama'").
- Enums with fewer than 2 or more than 20 options are dropped.
- Questions were run through Laya's own `build_sequence` with the multilingual tokenizer (about 32k at `max_len` 16384 and 89k at 1024, both with `head_max_len` 256): zero marker mismatches. Every gold label is one of its question's options.

The build and verification scripts are in `scripts/` and build `default`; the window size is set with `LAYA_MAX_LEN`. `ctx1024` was built by an earlier revision of the same scripts (see the repo history).

## Limitations

- **Hard labels.** Each answer comes from a single LLM extraction, so `probabilities` are one-hot, not the teacher distributions of typed-decisions. Fit temperatures on your own data before trusting Laya's probabilities, or rebuild with `LAYA_SMOOTH` set for label smoothing.
- **Labels are not human-verified.** Format and grounding are checked; the correctness of the LLM's category choices is not.
- **Historical Danish.** 24% of cases (`workflow == "enevaeldens"`) are 18th and 19th century newspapers with old spelling and OCR noise. Filter or down-weight them if the target is modern Danish.
- **Extraction-style questions.** The questions are about document content, not operational decisions such as triage or routing. The data improves Laya's Danish reading but does not replace task-specific decision data.
- **Licensing** follows the individual Danish Dynaword sources. Check the source licenses before redistributing models trained on specific subsets.

## Usage with Laya

```python
import json
from datasets import load_dataset
ds = load_dataset("syvai/danish-dynaword-laya", split="train")            # 16k windows
# ds = load_dataset("syvai/danish-dynaword-laya", "ctx1024", split="train")  # 1k windows
row = ds[0]
state, questions, gold = json.loads(row["state"]), json.loads(row["questions"]), json.loads(row["gold"])
```

The rows can be fed to `build_training_item` in Laya's typed-decisions fine-tuning notebook unchanged; for `default`, set `cfg["max_len"] = 16384` first. Use the multilingual checkpoint (`convaiinnovations/laya`, `subfolder="multilingual"`) as the starting point.
