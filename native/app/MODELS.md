# Models and downloads

## Current package

The 0.1.1 packages bundle our **Q4_K_M GGUF**, 1,167,417,504 bytes (1.17 GB).
Its source is [`danish-foundation-models/DFM-Mimir`](https://huggingface.co/danish-foundation-models/DFM-Mimir),
revision `2844f0178e695d7d9ce182cb660671fd34c76ce5`.
It was converted locally with our patched converter/tokenizer; it is **not**
the noctrex export. GGUF SHA-256:
`3cf8906f4dd1349c965e7dd873e3995419d34bf846a657840a393c32c89849a5`.
Original BF16 safetensors SHA-256:
`8a83c8a0e6ad25b73c089c9c6f8b01969f1c6bd7db76a71ff85de861a95311a0`.
The trained context is 4096; the app allows experimental contexts up to 32768.

## Public Hugging Face inventory, 2026-09-21

Sizes below are decimal GB for primary weights, excluding tokenizer/config files.
They are not memory requirements. The public HF search for `DFM-Mimir` returned
these seven repositories; no distinct newer model generation appeared in that search.

| HF repository | Format and primary weight sizes | Current app use |
|---|---|---|
| [danish-foundation-models/DFM-Mimir](https://huggingface.co/danish-foundation-models/DFM-Mimir) | Original BF16 safetensors, 3.57 GB | Source for our tested GGUF exports |
| [noctrex/DFM-Mimir](https://huggingface.co/noctrex/DFM-Mimir) | BF16/F16 GGUF, 3.59 GB each; Q8_0 GGUF, 1.91 GB | Downloadable experimental exports; see tokenizer caveat below |
| [schneiderkamplab/DFM-Mimir-FP8](https://huggingface.co/schneiderkamplab/DFM-Mimir-FP8) | FP8 E4M3 per-channel weights, dynamic per-token activations; 2.59 GB | Requires conversion; not a native FP8 GGUF download |
| [liodon-ai/DFM-Mimir-FP8](https://huggingface.co/liodon-ai/DFM-Mimir-FP8) | FP8 compressed-tensors variant, 2.59 GB | Requires conversion |
| [schneiderkamplab/DFM-Mimir-AWQ-FP4](https://huggingface.co/schneiderkamplab/DFM-Mimir-AWQ-FP4) | AWQ integer 4-bit grouped weights, compressed-tensors, 2.12 GB | Convert to dense GGUF and requantize; not floating-point FP4 |
| [schneiderkamplab/DFM-Mimir-FP4-MLX](https://huggingface.co/schneiderkamplab/DFM-Mimir-FP4-MLX) | MLX affine integer 4-bit, group size 64, 2.16 GB | Requires conversion or an additional MLX runtime; current Apple app also uses llama.cpp |
| [duarteocarmo/DFM-Mimir-ONNX](https://huggingface.co/duarteocarmo/DFM-Mimir-ONNX) | INT8 ONNX, approximately 2.21 GB including external tensor data | Requires an ONNX runtime integration; not drop-in GGUF |

Existing [qualification evidence](../mimir/REVIEW.md) covers our BF16, Q8_0,
Q4_K_M and FP8 conversion paths. GGUF Q8_0 and Q4_K_M are integer quantizations;
they are not interchangeable names for FP8/FP4. Converting FP8 to Q8 does not
preserve the original dynamic activation quantization.

### Training-reference correction (2026-09-21)

**The earlier conclusion below that noctrex's pre-tokenization was wrong is
superseded.** Tracing the local training path shows `scripts/tokenize_chat_template.py`
loads `tokenizers.Tokenizer.from_file(tokenizer.json)` and encodes the rendered
chat directly, without Transformers' `fix_mistral_regex` transformation.
`dataset_new.py` consumes those stored token IDs. The HF exporter subsequently
adds `fix_mistral_regex=true` in `conversion/convert_to_hf.py`; this flag is not
evidence of the training-time pre-tokenizer.

Direct execution of the training loader against the original HF tokenizer JSON
matches noctrex Q8_0 on **19/19** templated cases, and our bundled GGUF on **15/19**.
On the original four cases, the corresponding counts are **4/4** and **2/4**.
The local `dfm67_1150k/tokenizer.json` is byte-identical to the pinned original HF
JSON (SHA-256 `12bac982b793c44b03d52a250a9f0d0b666813da566b910c24a6da0695fd11e6`).
The historical external Gemma tokenizer path and production tokenized corpus are
not present on this Mac; this audit reproduces the local training loader using
that exported tokenizer, not a replay of the complete original corpus.

[Audit evidence](../mimir/training-tokenizer-audit.json) records all rendered
prompts, expected/actual IDs, versions and hashes. Cases include Danish,
multi-turn/system messages, punctuation, spacing, combining marks, multiple
scripts, emoji, rare code points and literal byte-token text. All comparisons
use Mimir's embedded chat template. This is tokenization evidence, not a complete
quality or decoder/byte-fallback qualification. The `gemma4` pre-tokenizer matches
the training path; our `spm-bpe-mistral` choice instead tracked post-export HF
behavior. Bundled weights and runtime have **not** been changed by this audit.
Correcting the export/reference pipeline and regenerating/requalifying the
bundled GGUF remains necessary.

### Public Q8_0 spot check (historical; interpretation corrected above)

Pinned noctrex revision `837955affd3eb783df325f977d0125da61e07411`, artifact
`DFM-Mimir-Q8_0.gguf`, SHA-256
`d7dddfc14a1f8f35b96ae6ca630d9ca3dbe6611cc5991e45b626d953b58ee201`:

- Download size and SHA-256 verified.
- Native macOS Metal, context/batch 1024, greedy budget 32, Mimir chat template:
  `Hvad hedder Danmarks hovedstad?` → `Danmarks hovedstad hedder København.`,
  EOS completion, status 0.
- Four chat-template/tokenization comparisons with our qualified bundled export:
  template text matches 4/4, token IDs match only 2/4. Differences include ` ø`
  and ` Hvad` in a multi-turn conversation. This is **not** equivalent tokenization.
- Follow-up metadata inspection identifies the cause: our export declares
  `tokenizer.ggml.pre = spm-bpe-mistral` and marks 256 byte-fallback tokens;
  this noctrex Q8_0 declares `gemma4` and marks zero byte-fallback tokens.
  The original checkpoint's tokenizer config has `fix_mistral_regex=true`.
  This is a tokenizer/conversion mismatch, not a consequence of Q8 quantization.
- The other two noctrex precisions were not independently downloaded/qualified.
  They remain experimental. This spot check is not quality or cross-device qualification.

The initial catalog makes the third-party files available with an explicit
experimental notice; it does not promote them to recommended defaults. To offer
recommended alternative precisions, publish our qualified GGUF artifacts to HF
and add their pinned metadata and test evidence to the catalog.

## Selector behavior

Open **Model and settings → Choose or download a model…**. The page shows the
selected model, bundled model, installed imports, catalog download sizes, progress,
missing files and experimental status. Downloading never changes the selection.
Select an installed model explicitly; on Android this does **not** load it or
initialize a GPU driver. Choose backend/context and press Load in settings.
Models in existing conversations remain identified by weight SHA-256; selecting
another model does not silently rewrite old conversations.

Downloaded/imported files are stored under the app's `models/<sha256>.gguf`.
Unselected app-owned models can be removed. The selected model and bundled asset
cannot be deleted by the selector. Imports retain a copy; removing one never
removes the original source file.

**Allow model downloads and discovery** is separate from feedback permission,
off by default, and grants no chat uploads. No catalog request occurs at startup.
Enabling the switch alone performs no request. **Check for newer models** fetches
the catalog and searches public HF model metadata; Download fetches only the
chosen artifact. Requests use HTTPS, including redirects to HF's CDN. Turning
the switch off cancels active requests. Offline selection/inference still work.

Downloads stream to disk, check advertised size, SHA-256 and GGUF magic, then
install atomically. Interrupted/cancelled/failed transfers remove partial files;
retry starts from the beginning. Downloads are foreground app operations, not
OS-managed background transfers. OS termination can leave an unregistered `.part`
file; retry overwrites it. No remote model code is downloaded or executed.

## Adding models without rebuilding the app

`assets/models.json` is the version-1 embedded catalog and the published catalog
source. The client refreshes it from this repository's `codex/mimir-apple-mvp`
branch on `raw.githubusercontent.com`, then caches the merged result for offline use.
Each entry carries HF repository, immutable revision, file path, exact size,
SHA-256 identity, qualification description, and a complete model-specific
memory/context/system-prompt profile. Publish catalog changes to that branch;
changing catalog hosting or schema requires a client change.

**Updated 2026-09-21:** the earlier policy of listing HF discoveries only as
repository references is superseded for the official organization. Refresh now
merges the curated catalog with **all GGUF files** in public repositories owned by
`danish-foundation-models` whose repository name contains **both `mimir` and `gguf`**, case-insensitively.
Repository and recursive file pagination are followed; matching does not depend
on HF search casing. Each discovered file is pinned to the current commit, byte
size and LFS SHA-256. Curated entries win for duplicate hashes or the same
repository/file, preserving their model profiles and qualification descriptions.

No catalog edit is needed to expose a new single-file GGUF in a matching official
repository: upload it to HF, then press **Check for newer models** in the app.
Auto-discovered files are marked unqualified and use the existing Mimir v1 profile
as an explicit fallback. Selection starts with automatic sizing off, 1024 context
and 512 reply tokens; import a model-specific profile when necessary. Model names
do not establish engine compatibility. A new architecture still requires an engine
update. Split/sharded GGUFs and files lacking SHA-256/size metadata are listed with
size and a reason, but cannot yet be downloaded through the verified single-file
loader. No checkpoint or shard is silently treated as an independently usable model.

The curated catalog follows the same official-owner and two-name-term restriction.
This supersedes the earlier policy allowing any publisher (2026-09-21). To update it:

```sh
# Edit native/app/assets/models.json: add/remove entries or adjust profiles.
git add native/app/assets/models.json
git commit -m "Update Mimir model catalog"
git push origin HEAD:codex/mimir-apple-mvp
```

Run those commands from the intended catalog branch; they publish that branch's
commits. Users enable model networking and press **Check for newer models**;
existing compatible clients need no rebuild. Each entry requires `id` (file
SHA-256), `name`, `repo`, immutable `revision`, `file`, exact `bytes`, `profile`,
and a clear `qualification` description. The embedded JSON is the offline starting
point; refreshed entries are saved locally. Either catalog or HF failure preserves
that source's cached entries and reports the failure while refreshing the other.

**Historical check, superseded by the publication below:** the official organization had one matching
repository (`DFM-Mimir`) and no GGUF files, so the merged downloadable list still
contains the three curated noctrex entries. Future official GGUF uploads will be
picked up automatically on refresh.

All five portable targets — macOS, iOS, Android, Linux, Windows — share this flow.
Acceleration remains whatever the installed package supports; weights do not add
new backend libraries. The separate native SwiftUI UI and headless CLI do not gain
this selector; the CLI can load the downloaded GGUF by path.

Maintainer checklist:

1. Convert with the reviewed converter and preserve the actual model chat template.
2. Validate tokens/template and representative generation, record device/backend evidence.
3. Publish the GGUF; pin the HF commit, file hash and byte count.
4. Supply a profile based on this model's context, architecture and memory measurements.
5. Label qualification accurately, update the catalog, and refresh in the app.
6. Test model switching, interrupted downloads and low-memory startup before recommending it.

Validation for this implementation: static analysis clean, 37 Flutter tests pass,
including 10 library/selector tests (network opt-in, discovery separation,
streaming/verification, rejection, cancellation, persistence, deletion, Android
startup and UI). macOS release and iOS simulator builds pass. These are source
builds; no replacement release packages were published for this feature.

Official discovery extension validation: static analysis clean; 41 app tests pass.
Tests cover mixed-case names, publisher filtering, pagination, immutable revisions,
curated precedence, cached-source recovery and visible unsupported shards.

Corrected local BF16, Q8_0 and Q4_K_M artifacts have now been prepared and tested.
See [preparation and results](../mimir/CORRECTED-GGUFS.md). Existing published
packages still contain the old bundled artifact until explicitly rebuilt.


## Official GGUF publication, 2026-09-21

The earlier statements that the official organization has no GGUFs and that our
corrected artifacts are local-only are **superseded**. The public repository is
[danish-foundation-models/DFM-Mimir-GGUF](https://huggingface.co/danish-foundation-models/DFM-Mimir-GGUF),
revision `4364aaa61279c187b7cd202375915ea962b79afb`, containing our corrected BF16,
Q8_0 and Q4_K_M exports. All three remote sizes/LFS SHA-256 hashes were verified
without authentication. The repository includes a model card, original Apache
license, checksums, provenance and validation results.

The curated catalog now lists these official artifacts first, with the validated
Mimir v1 profile and pinned revision. The earlier retention of three third-party
entries is **superseded** by the official-only policy (2026-09-21): those entries
have been removed. Embedded, remote and cached catalogs all use the same filter
as HF discovery; stale cached discovery listings are filtered on startup too.
Already installed models and manual imports remain usable.
Official automatic discovery also finds the new repository; curated metadata wins
for duplicate files. Refresh the catalog with model networking enabled to see them.
Existing preview packages have not been rebuilt, and their bundled weights remain
unchanged. Manual GGUF import can use the new files in those packages.
