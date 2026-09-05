---
type: Dataset Export Record
title: DFM11 Mathagentic Export Packages
description: Upload staging, validation, provenance, and admission boundaries for DFM11 arithmetic tool-use trajectories.
tags: [dfm11, mathagentic, tool-calling, math, hugging-face, export]
status: stable
last_updated: 2026-09-03
confidence: high
sources:
  - id: tinygsm-dataset
    resource: https://huggingface.co/datasets/TinyGSM/TinyGSM
    title: TinyGSM dataset
    author: org:TinyGSM
  - id: gsm8k-prolog-prover-dataset
    resource: https://huggingface.co/datasets/niklasm222/gsm8k-prolog-prover
    title: GSM8K Prolog Prover dataset
  - id: gsm8k-dataset
    resource: https://huggingface.co/datasets/openai/gsm8k
    title: GSM8K dataset
    author: org:OpenAI
---
# DFM11 Mathagentic Export Packages

## Materialized packages

On 2026-09-03, `scripts/prepare_dfm11_mathagentic_exports.py` atomically
materialized two upload-staging packages under `exports_dfm11/`. Preparation
does not upload or admit either package into a sampled DFM11 corpus.

| Package | Intended Hugging Face ID | Rows | Shards | Compressed bytes | Admission |
|---|---|---:|---:|---:|---|
| `dfm11-mathagentic-tinygsm-python` | `schneiderkamplab/dfm11-mathagentic-tinygsm-python` | 367,749 | 4 | 59,334,300 | restricted execution plus accepted independent semantic verdict |
| `dfm11-mathagentic-gsm8k-prolog` | `schneiderkamplab/dfm11-mathagentic-gsm8k-prolog` | 7,473 | 1 | 1,940,101 | sandboxed execution plus reviewed GSM8K-gold agreement |

The root inventory is `exports_dfm11/manifest.json`. Each package contains
deterministic gzip JSONL shards, an HF dataset card, a checksummed manifest,
and a standalone `validate_dataset.py`.

## Publication

Both packages were uploaded and independently verified against downloaded
copies on 2026-09-03:

| Repository | Verified commit |
|---|---|
| [`schneiderkamplab/dfm11-mathagentic-tinygsm-python`](https://huggingface.co/datasets/schneiderkamplab/dfm11-mathagentic-tinygsm-python) | `17a3df5ccdd70ce71983485c6c48cce54b60f05e` |
| [`schneiderkamplab/dfm11-mathagentic-gsm8k-prolog`](https://huggingface.co/datasets/schneiderkamplab/dfm11-mathagentic-gsm8k-prolog) | `1d32034d3b2467e51a6128b2cb249852969f17d0` |

Local and remote file inventories and SHA-256 values matched, excluding only
the Hub-generated `.gitattributes`, and the validators reported 367,749 and
7,473 valid rows. Machine-readable receipts are retained in
`logs/dfm11_mathagentic_upload_receipts.jsonl`. The active source and sampling
policy is pinned in `config/data/dfm11_mathagentic.yaml`.

## TinyGSM audit boundary

The source reservoir is pinned to TinyGSM revision
`5049a7840fa546985eaae4c698d5daf6fdf7b47d`. Deterministic 1-in-20 sampling
produced 500,000 restricted-Python execution-verified candidates. A separate
Gemma 4 26B A4B audit used strict JSON Schema output and classified every
candidate:

| Outcome | Rows | Share |
|---|---:|---:|
| Accepted and packaged | 367,749 | 73.55% |
| Rejected and omitted | 132,251 | 26.45% |

Rejected counts were 110,774 wrong operation, 9,900 malformed question, 5,967
wrong quantity, 3,028 unsafe or irrelevant, 1,924 unit error, and 658
ambiguous. The verdict journal SHA-256 is
`9badd56a7c71a29c74cffc5ccc478a744b961b0a071a3657cabdfb7dfb048f97`.
The package is MIT-labelled in accordance with the upstream card. Accepted
rows are useful arithmetic tool trajectories but remain synthetic rather than
human-quality gold; avoid allowing this large family to dominate DFM11.

## Prolog verification boundary

The source is pinned to `niklasm222/gsm8k-prolog-prover` revision
`35e66243ccdc39614f93e4b65abebb9ea9e36bd3` and joined to pinned GSM8K train
answers. All 7,473 rows pass SWI-Prolog sandbox validation and execution.
Twelve malformed programs use tracked reviewed repairs, and 14 incorrect
GSM8K gold values use tracked reviewed overrides.

The package remains `license: other`: GSM8K declares MIT, but the derivative
Prolog dataset card does not declare a machine-readable license. Preserve its
paper citation and do not represent the package as MIT. Manual project release
approval to upload both Mathagentic packages was recorded on 2026-09-03.

## DFM11 sampling policy

Publication preserves the complete accepted source packages. DFM11 applies
the following separate deterministic epoch-sampling policy:

| Package | Available rows | Rows selected per epoch | Repeat |
|---|---:|---:|---:|
| `dfm11-mathagentic-tinygsm-python` | 367,749 | 50,000 distinct rows | 1 |
| `dfm11-mathagentic-gsm8k-prolog` | 7,473 | all 7,473 rows | 2 |

The Prolog source therefore contributes 14,946 row occurrences per epoch. The
TinyGSM cap is 50,000 without repetition; it supersedes the earlier tentative
10,000-row cap discussed during upload preparation. Rotate the deterministic
TinyGSM subset across epochs where the sampler supports that without changing
the 50,000-row per-epoch ceiling.

## Training schema

Every row preserves the Mathagentic native schema:

1. user word problem and explicit instruction to use the available tool;
2. assistant call to `execute_python` or `execute_prolog` with the program in
   structured arguments;
3. matching environment-owned `role=tool` result;
4. terminal assistant target containing exactly one `\boxed{...}` answer.

The packages load successfully with the Hugging Face streaming JSON loader.
They are directly consumable by Mathagentic's Gemma 4 native rendering path.
DFM11 training must retain `data.target_only=true` so tool declarations,
prompts, and environment results are context while assistant calls and final
answers are supervised targets.

## Tokenized reservoir

On 2026-09-03, both complete local export packages were tokenized directly
from their gzip JSONL shards into `data/tokenized_dfm11`. Mathagentic used five
processes (one per source shard), its mapping-aware bundled Gemma 4 native chat
template, the 262,144-entry Gemma tokenizer, target-only task boundaries, and a
strict 4,096-token maximum. No sampling or epoch-index construction was run.

```bash
cd /work/mimir/HRM-Text/mathagentic
TOKENIZERS_PARALLELISM=false \
  /home/ucloud/miniforge3/envs/mathagentic/bin/mathagentic tokenize \
  --source /work/mimir/HRM-Text/exports_dfm11 \
  --output /work/mimir/HRM-Text/data/tokenized_dfm11 \
  --tokenizer /work/mimir/brainsurgery/models/gemma4_31b/tokenizer.json \
  --template /work/mimir/HRM-Text/data_io/chat_templates/gemma4_native_chat.jinja \
  --max-seq-len 4096 \
  --workers 5 \
  --force
```

| Package | Source rows | Assistant targets | Stored tokens |
|---|---:|---:|---:|
| `dfm11-mathagentic-tinygsm-python` | 367,749 | 735,498 | 201,279,326 |
| `dfm11-mathagentic-gsm8k-prolog` | 7,473 | 14,946 | 6,046,904 |
| **Total** | **375,222** | **750,444** | **207,326,230** |

All rows yielded both expected assistant targets and no target exceeded the
4,096-token gate. Full rendered lengths have median 268, p99 427, and maximum
1,201 tokens. The five task directories occupy approximately 814 MiB.
Every task's instruction/response offsets and lengths were checked against its
token array. The aggregate receipts are `completion.json` (SHA-256
`7eea9b505f3ebc59056e011ac953bfe3830a6b96d02a088a7d292860cbe04df6`)
and `tokenizer_info.json` (SHA-256
`641e62ffb1e0aa74643f0a843b61e3200768eabf4167b5dda26635e7fea5e392`).
The DFM11 sampler must still apply the separate 50,000-row TinyGSM cap and
Prolog repeat-two policy; the token totals above describe the full reservoir,
not one sampled epoch.

An exhaustive source/token-array check confirmed the intended expansion:
every one of the 375,222 trajectories produced exactly two adjacent training
examples. The first target is the structured `execute_python` or
`execute_prolog` call. The second prompt contains that call and its matching
environment-owned tool result, and its target is the terminal boxed answer.
Counts are exactly 375,222 call targets plus 375,222 post-result targets, with
no malformed source trajectory. Decoded targets use Gemma native
`<|tool_call>call:...<tool_call|><|tool_response>` and
`\boxed{...}<turn|>` forms.

The canonical repository template was updated to handle mapping-valued tool
results before generic sequences. It is byte-identical to Mathagentic's tested
bundled template (SHA-256
`d8ae62ccf8e47299c8e912a86b16e93bf6b195d24e8b06fffb865e061e89f07e`).
The final tokenization receipt therefore names
`data_io/chat_templates/gemma4_native_chat.jinja`, matching inherited DFM
tokenized unions rather than a package-private path.

## Other DFM11 tool-use sources

DFM11 is planned as a delta over finalized DFM10, so it inherits several
earlier tool and agent families. All structured families ultimately render
through the same Gemma 4 native template, but their source contracts differ:

| Source | Inherited form | Assistant supervision before Gemma rendering |
|---|---|---|
| `allenai/Dolci-Instruct-SFT-Tool-Use{|-SA}` | DFM10 repaired replacement | Top-level OpenAI-shaped tools; parsed structured calls; monotonically assigned call IDs; `environment` outputs converted to matching `role=tool` results; multi-step calls and final text targets. |
| `glaiveai/glaive-function-calling-v2` | DFM7 native conversion | Legacy `<functioncall>` text and `FUNCTION RESPONSE` records parsed into structured calls and matching tool messages; ordinary assistant text remains a target. |
| `Team-ACE/ToolACE` | DFM7 native conversion | Declared schemas plus structured single/parallel calls, tool results, no-tool/direct answers, and clarification turns. |
| `Salesforce/xlam-function-calling-60k` | DFM7 native conversion | Query plus declared tools maps to one assistant structured call target; call-only supervision, without a simulated result/final-answer turn. |
| `nvidia/Nemotron-SFT-Agentic-v2` | DFM6/7 direct structured ingestion | Upstream `tool_calling`, `interactive_agent`, and `search` conversations retain top-level tools, assistant `tool_calls`, results, and later assistant turns. |
| `schneiderkamplab/dfm8-synthetic-native-tool-calling` | DFM8 generated and audited | Synthetic function/parameter records normalized to OpenAI-shaped structured calls, then rendered as Gemma-native calls; includes broader native-call behavior than call-only xLAM. |
| `nvidia/Nemotron-SFT-SWE-v2` | DFM10 repaired replacement | Structured `execute_bash` and `str_replace_editor` calls with matched results and final text; obsolete `think` actions are removed and each selected assistant turn becomes one target. |
| `zai-org/DeepDive` | DFM10 native conversion | Multi-step `search`, `click`, and `open` calls plus results; XML/ReAct wrappers and visible hidden reasoning are removed; legacy `finish` becomes a normal final assistant answer. |

`nvidia/Nemotron-Terminal-Corpus` is also inherited as role-preserving
terminal-agent dialogue, but it has no top-level function schemas and is not
BFCL-style structured function-call supervision. Likewise, DFM Dyna
`when2call` is auxiliary call/no-call decision data rather than assistant
tool-call targets. These should not be counted as interchangeable with the
structured sources above. The repaired English/Danish OpenHermes corpora are
general conversation/format-following sources and are not classified here as
canonical native tool-call supervision.

## Tool-source remediation assessment

The DFM7 validator established top-level tools, mapping-valued arguments,
native rendering, and removal of XML prompt remnants, but it did not establish
global call-ID uniqueness or complete call/result pairing. A 2026-09-03 code
review therefore identified these DFM11 actions:

| Priority | Source | Action |
|---:|---|---|
| 1 | `glaiveai/glaive-function-calling-v2` | Re-convert multi-step rows. The current parser assigns literal `call_0` to every call and every function response, so repeated calls can have duplicate identities. Assign monotonic IDs and validate every result against the pending call. |
| 1 | `Team-ACE/ToolACE` | Re-convert parallel/multi-call rows. The current converter remembers only `last_tool_call_id`, so a result after a parallel call group can be bound only to the final call. Pair results by declared order/name and reject ambiguous groups. |
| 2 | `nvidia/Nemotron-SFT-Agentic-v2` | Run exhaustive deterministic validation over unique IDs, declared tool names, mapping arguments, call/result completion, and mixed content-plus-call cases. It is already structured; repair only failing strata. |
| 2 | `schneiderkamplab/dfm8-synthetic-native-tool-calling` | Materialize the tokenizer's legacy `function`/`parameters` compatibility normalization into a canonical source artifact, then exhaustively validate it. Avoid relying indefinitely on an implicit tokenizer shim. |
| 2 | Repaired OpenHermes EN/DA | Scan for surviving legacy `<functioncall>`, XML, or call-like assistant text. Canonicalize genuine tool rows or exclude them from tool-format training; do not leave competing conventions in a general-chat source. |
| 3 | `Salesforce/xlam-function-calling-60k` | Keep the source as valid call-only supervision, but cap and label it separately. If result interpretation is desired, construct a distinct verified continuation dataset rather than inventing unavailable API results. |
| 3 | `nvidia/Nemotron-Terminal-Corpus` | Keep as role-preserving terminal-agent data. Convert to an explicit terminal function schema only where command/result boundaries are deterministic; otherwise keep it tool-adjacent rather than presenting it as BFCL-style data. |

Repaired DOLCI, repaired Nemotron SWE, DeepDive, and the two Mathagentic
packages already have source-specific canonical converters and structural
gates. They need regression validation when rebuilding DFM11, not another
format conversion. `when2call` remains intentional auxiliary decision data and
must not be relabeled as tool-call targets.

## Estimated remediation resources

These are planning estimates, not measured benchmarks. Conversion, exhaustive
schema validation, and tokenization are CPU/storage workloads; GPUs are needed
only for sampled semantic-quality audits.

| Work | CPU and memory | GPU | Estimated wall time |
|---|---|---|---:|
| Glaive and ToolACE converter repair plus exhaustive validation | 8-16 cores, 16-32 GiB | None | 1-2 hours |
| Nemotron Agentic and DFM8 synthetic deterministic validation/repair | 16-32 cores, 64-128 GiB | None | 2-5 hours |
| OpenHermes EN/DA legacy-format scan and selective repair | 16-32 cores, 64-128 GiB | None | 1-3 hours, plus retokenization if changed |
| Optional Nemotron Terminal canonicalization | 16-32 cores, 64-128 GiB | None | 2-6 hours after converter implementation |
| Retokenization of changed sources | 16 workers, 64-128 GiB, fast storage | None | Roughly 1-4 hours total |
| Stratified semantic audit of 6,000-10,000 rows | Modest client CPU | One B200 with Gemma 4 26B A4B | Roughly 0.5-1.5 GPU-hours including startup |

For the current DFM11 remediation run, reuse the existing vLLM services on
GPUs 0-3 without managing their processes. Run 64 concurrent requests against
each endpoint (`8100` through `8103`), for 256 requests in aggregate. CPU-bound
conversion, validation, packaging, and tokenization may use up to 128 workers.
Do not judge every row with an LLM: use exhaustive deterministic checks for
structural invariants and reserve model judging for stratified samples and
repaired/failing strata.

## DFM11 repaired tool-source execution

On 2026-09-04, four replacement reservoirs were built under `exports_dfm11/`.
Each package has pinned upstream provenance, deterministic gzip shards,
checksums, a self-contained validator, and an audit receipt in
`metadata/manifest.json`.

| Replacement package | Source rows | Training samples | Tokens before sampling | Semantic audit accepted |
|---|---:|---:|---:|---:|
| `dfm11-glaive-native-tool-use-repaired` | 71,376 | 204,276 | 48,206,342 | 1,976/2,000 |
| `dfm11-toolace-native-tool-use-repaired` | 10,378 | 12,824 | 8,177,428 | 1,974/2,000 |
| `dfm11-nemotron-agentic-tool-calling-repaired` | 8,443 | 44,925 | 147,240,984 | 1,927/2,000 |
| `dfm11-synthetic-native-tool-calling-repaired` | 836,675 | 1,810,418 | 513,097,730 | 1,999/2,000 |

All four packages were uploaded and remotely verified on 2026-09-04:

| Hugging Face dataset | Pinned final revision |
|---|---|
| `schneiderkamplab/dfm11-glaive-native-tool-use-repaired` | `270781c192980b2d32a492f92b2b1ba2d694a258` |
| `schneiderkamplab/dfm11-toolace-native-tool-use-repaired` | `2768a3ff3b65effb60d200042c8e09a10e07cc59` |
| `schneiderkamplab/dfm11-nemotron-agentic-tool-calling-repaired` | `ad3251630ba1c0435a559fb9737267554ab208ff` |
| `schneiderkamplab/dfm11-synthetic-native-tool-calling-repaired` | `aef80ae81d10b0bb9d9ca7e7760ba09297df4b56` |

Every expected remote file was present and every remote package manifest was
byte-identical to its local manifest. The verification receipt is
`logs/dfm11_tool_replacements_upload_receipts.json`.

The semantic audit used 64 concurrent requests **per GPU endpoint**, hence 256
aggregate requests across the four pre-existing Gemma 4 26B A4B servers. Two
initial Nemotron responses were truncated JSON; both exact rows were retried
with a larger response allowance. One was accepted and one was rejected, so
the final audit has no unresolved request errors. Semantic sampling is a
quality diagnostic and does not selectively mutate the exhaustively
structure-validated reservoirs.

The repaired sources and both Mathagentic packages were tokenized together
from the common `exports_dfm11/` root. This preserved package names in task
directories and produced 2,822,887 training samples and 924,048,714 tokens in
`data/tokenized_dfm11_additions`. The final run used 64 CPU workers and took
267.4 seconds. Running each package as a separate tokenizer
root is invalid because identically named `data/train-*` shards collide in the
output namespace. The invalid partial attempt is retained only as a diagnostic
under `logs/tokenized_dfm11_tool_replacements_invalid_namespace_20260904`.

An exhaustive scan of all 1,885,429 rows in the repaired English and Danish
OpenHermes packages found no legacy function-call tags, structured calls,
tool/function roles, or parse errors. No additional OpenHermes replacement is
needed for DFM11.

The reproducible preparation commands are:

```bash
python -m scripts.prepare_dfm11_tool_replacements build \
  --workers 128 --rows-per-shard 5000 --force

python -m scripts.prepare_dfm11_tool_replacements audit \
  --concurrency-per-endpoint 64 \
  --samples-per-dataset 2000 \
  --max-retries 3 \
  --output logs/dfm11_tool_replacement_audit_v3.jsonl \
  --force

python -m scripts.prepare_dfm11_tool_replacements record-audit \
  --audit logs/dfm11_tool_replacement_audit_v3.jsonl

python scripts/tokenize_chat_template.py exports_dfm11 \
  --tokenizer-path /work/mimir/brainsurgery/models/gemma4_31b/tokenizer.json \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  --output-dir data/tokenized_dfm11_additions \
  --workers 64 --max-seq-len 4096 --skip-bad-json --force
```

Build the final tokenized DFM11 union with:

```bash
python scripts/build_tokenized_dfm11_tree.py --force
```

This replaces only Glaive, ToolACE, Nemotron `tool_calling`, and DFM8 synthetic
native tool-calling tasks. In particular, inherited Nemotron interactive-agent
and search tasks remain. The command requires `data/tokenized_dfm10`; that base
token store is not present on the 2026-09-04 preparation node, so the union and
sampling must wait until it is restored or rebuilt. Do not sample DFM11 from
the additions-only store.

## Rebuild and validate

```bash
cd /work/mimir/HRM-Text
python scripts/prepare_dfm11_mathagentic_exports.py --force

python exports_dfm11/dfm11-mathagentic-tinygsm-python/validate_dataset.py
python exports_dfm11/dfm11-mathagentic-gsm8k-prolog/validate_dataset.py
```

The successful validation result is 367,749 TinyGSM rows and 7,473 Prolog
rows. To verify HF loader compatibility without uploading:

```bash
python - <<'PY'
from datasets import load_dataset

for name in (
    "dfm11-mathagentic-tinygsm-python",
    "dfm11-mathagentic-gsm8k-prolog",
):
    dataset = load_dataset(
        "json",
        data_files={"train": f"exports_dfm11/{name}/data/*.jsonl.gz"},
        split="train",
        streaming=True,
    )
    print(name, next(iter(dataset))["source_id"])
PY
```

Upload each package directory to its `intended_hf_id`; do not upload the
`exports_dfm11/` root as one combined dataset. Update `upload_performed` only
from a verified Hub receipt.

The existing uploader accepts this staging root:

```bash
HF_TOKEN="$HF_TOKEN" python scripts/upload_export_upload_to_hf.py \
  --root exports_dfm11 \
  --include-glob 'dfm11-mathagentic-*' \
  --large-folder \
  --workers 8 \
  --log logs/dfm11_mathagentic_upload.log
```
