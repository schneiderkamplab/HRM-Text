# RepoQA: eight fresh passed-answer reviews (2026-10-01)

## Outcome and scope

**3 retain, 3 confirmed localized repairs, 2 grounding/wording repairs.**
All eight remain original `quality_pass=true` artifacts; this report changes no
labels, admission decisions, source files, or running jobs. No repository code
was executed. These are independent manual answer reviews, not model rejudging.

Population: `data/dfm13/repochat-qa-next-20261001-v1/eligible-74`, with 65 passes
and nine failed trajectories. Select two lowest SHA256(seed + `|` + ID) in each
of four strata: broad/specific prompt crossed with <=4/>4 tool responses.
Seed: `repoqa-pass-manual8-20261001-v1`. Selection was frozen before inspecting
selected final answers; no swaps based on content. Eight distinct repositories.
Prior source-eligibility work exposed prompts/repositories, not these answers.
Pass labels select the population; original judge rationales were not used in
manual adjudication. This small stratified sample is not a precision estimate
for all 65 passes.

Read all eight complete prompts, 41 actual tool responses, and final answers.
Additional source reads below are distinguished from evidence the model saw.
Full inputs and exact hash pins are preserved in the packet and selection files.

## Findings

1. **Agnaistic: localized repair (high confidence).**
   ID `9ee8ac3930641f2f02f485fe7ba6ebe948e4209d80f232c9148cfffff69e91a6`.
   The multi-tier architecture is broadly supported. The model only listed the
   Python files and mislabels `model/server.py` as the entrypoint. Additional
   inspection: that file only creates the Flask app; `model/app.py:40` starts
   it, and `package.json:52-53` launches `model/app.py`. Correct that specific
   claim and add line citations; do not reject the whole architecture summary.

2. **IDSHV-router: localized repair (high confidence).**
   ID `ad34e86b79d4a07cfb78fc2ee67810c52aa0406c0724c85fc103f2acbb4df43e`.
   Purpose and API parameter descriptions match the fully retrieved server.
   The answer calls both algorithms BFS. `server.js:140` sorts by transfer cost:
   least-transfer routing is cost-prioritized/Dijkstra-like, unlike station-count
   FIFO BFS. OpenAPI compliance is asserted by a comment, not validated by this
   review. The Minecraft interpretation is explicitly qualified, not a fabricated
   definite claim.

3. **Counter: retain (high confidence).**
   ID `e6ceaa083a7fd2d13439ccc7985475ae8e63ab26df5971257f3931ccd47796f5`.
   Full `index.html`, `counter.html`, and `style.css` support the dedication,
   timer, navigation, font, gradient and hover description. The answer properly
   limits knowledge of the unread poem. Appearance is source-inferred, not a
   browser rendering. Month/year counters use calendar-field differences; the
   answer does not explicitly claim completed-duration arithmetic.

4. **CoinCalc: retain (high confidence).**
   ID `35204577fe281f09280684afe41ebe84bfa944af472abb6816152869bb196c63`.
   The short purpose answer directly attributes Event Coincidence Analysis and
   six functions to `README.md:1-3`. No invented function names or implementation
   details. This establishes documented purpose, not package executability.

5. **wifi-heatmapper: retain (high confidence).**
   ID `59b8257cffd8d8ed1039d68187446f976caae34021b155b6638b2fbcf111779a`.
   The full `src/app/webGL/shaders/heatmapFragmentShader.ts` supports IDW,
   inverse-distance power, normalization, radius and LUT rendering. Optional
   completeness caveat: near-coincident points return the measured value and
   no-neighbor pixels are discarded (lines 45-65). No shader was executed.

6. **OS_32Bit: grounding repair (medium confidence).**
   ID `7867d01ba009a335c3051502eab08adaa8bfc47e8190f8ec09282febb747aeb0`.
   README/bootloader documentation supports the boot flow and listed components.
   The retrieved kernel guide is empty. The answer nevertheless promises memory
   isolation. Additional reads of `paging.c:18-47`, `PCB.c:7-42` and
   `tasksw.asm:57-93` establish shared paging setup/kernel-task switching, not
   per-process isolation. Say virtual addressing/paging, without that guarantee.
   This is not an exhaustive proof that every protection mechanism is absent.

7. **OneCode: localized repair (high confidence).**
   ID `22a16cd68850d6d48f9d905e7dbfcf77405c4281724eecea65ff637ed1169e31`.
   Correct files, initialization and room events. However, the answer endorses
   `src/socket.js:5-6` malformed options as effective settings. The v4 API uses
   `forceNew` and `reconnectionAttempts`, not `force new connection true` and
   singular `reconnectionAttempt`. Infinite retries are already the default;
   do not infer finite retries from the typo. External verification:
   [Socket.IO v4 client options](https://socket.io/docs/v4/client-options/).

8. **DINOv2: wording/grounding repair (medium confidence).**
   ID `bcd854c5307ccc805a9fe1933189a0e7e58c3098ec753bb48bc5137a328a9174`.
   Two meanings of register and 4/0-token configuration are correctly identified.
   Retrieved evidence only contains configuration and search snippets, not the
   mechanism explanation. Additional `vision_transformer.py:216-264` inspection
   shows extra registers and patch tokens traversing the same blocks. Replace
   ambiguous "without affecting the spatial tokens" with "additional non-patch
   tokens, rather than replacement patch positions"; no promise of unchanged
   patch features. This does not invalidate the whole conceptual explanation.

## Handoff and checks

Artifacts for Harvey/parent, under
`data/dfm13/repoqa-pass-manual8-20261001-v1/`:

- `selection.json`: deterministic sample, full IDs, source paths and SHA256 pins.
- `packet.jsonl`: full original messages, including tool calls/results and answer,
  without judge rationales.
- `manual-review.json`: per-ID findings, confidence, retrieved versus additional
  evidence and bounded recommendations; explicitly `admission=false`.

All eight IDs, eight pass flags and 16 trajectory/outcome hashes were checked.
No corrective answers were generated; these recommendations require a separate
authorized repair/review step. No active outputs, runtime code or GPUs changed.
