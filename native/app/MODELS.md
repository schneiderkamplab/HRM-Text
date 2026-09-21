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

### Public Q8_0 spot check

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
branch on `raw.githubusercontent.com`, then caches the result for offline use.
Each entry carries HF repository, immutable revision, file path, exact size,
SHA-256 identity, qualification description, and a complete model-specific
memory/context/system-prompt profile. Publish catalog changes to that branch;
changing catalog hosting or schema requires a client change.

HF search results are listed separately and **never auto-enabled solely by name**.
A new generation becomes downloadable after its GGUF and profile enter the
catalog. Same supported architecture/quantization can therefore be delivered
without a new app release. A changed architecture, unsupported tensor type,
new template implementation, or runtime requirement needs an engine update first.
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
