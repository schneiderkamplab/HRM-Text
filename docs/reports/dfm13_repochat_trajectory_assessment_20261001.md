# RepoChat v3: independent eight-pass trajectory assessment

Date: 2026-10-01. CPU-only, agent-authored manual assessment. No model calls,
repository code execution, compilation, GPU work, or dataset modifications.

## Scope and Decision

Root: `data/dfm13/repochat-calibration-100-20261001-v3`.
The saved summary reports 100 selected, 91 reviewed, 83 quality passes and
9 failed trajectories; admission remains false. I purposively selected eight
passes across implementation (2), build integration (1), API migration (1),
repository navigation/QA (3), and project explanation (1). None is one of the
four IDs in `review-controls/`. This is a stratified diagnostic sample, not a
random estimate of precision or a certification of all 83 passes.

Sample result: **2 clear false accepts on instruction/completeness grounds,
3 additional repair/verification targets, 3 broadly supported answers with
bounded caveats.** These categories concern suitability as finished targets,
not whether every sentence in an answer is wrong. Continued generation with
revisitable audit outputs is reasonable; automatic admission of all quality
passes as verified working code is not supported by this sample.

I read original user requests, final answers, and saved tool observations before
comparing the reviewer explanations. All eight have matching, ordered tool-call
IDs and tool responses (35 calls total); no unmatched calls were found. This
checks saved sequence integrity, not live re-execution or the server's rendered
prompt. No answer in this sample claims that tests were executed.

## Clear False Accepts

### Invoice editing: explicit style constraint violated

ID: `09580602128a59fe8c1c2be78479ee7d97c188884b17889c28b6c2c2557ebba2`.
Repository: `AdithyaSenthilkumar/reactapp`.

The user requests parsing line items from the data JSON and maintaining styles.
The retrieved `reactzip/frontend/invoice-extraction/src/components/InvoiceEdit.js`
already parses `data.data` at lines 49-51 and renders `parsedData.line_items` at
157-158. The response presents this as a new correction, and its full replacement
changes unrelated styling: outer `p-6` added (original line 110), PDF
`overflow-hidden` added (114), products spacing changed (148-150), and row
`border-b pb-2` removed (159). The reviewer explicitly says styles were maintained.
That assertion is contradicted by the supplied evidence.

Repair: acknowledge the pinned code already uses JSON-derived items; supply a
minimal immutable item-update patch and retain existing JSX/classes. The claim
that calculating `updatedParsedData` first generally fixes stale closures is
also too strong: it still reads the current render's `parsedData`. No runtime
failure is claimed here; the decisive failure is the explicit preservation
constraint and incorrect description of the existing implementation.

### OpenVINO Bazel: incomplete dependency translation passed as complete

ID: `ef7ba0d5783760ad92a866fc69ec6699e45ecee6faa8a2bd3f1af9e43dde66b3`.
Repository: `openvinotoolkit/openvino`.

The user asks for a proper build file for `samples/cpp/hello_query_device`.
The answer openly supplies a placeholder `@openvino//:openvino_runtime`, but the
reviewer nevertheless certifies a complete, actionable build. More concretely,
retrieved `samples/cpp/common/utils/CMakeLists.txt:30` links both OpenVINO and
`${GFLAGS_TARGET}`; the proposed utility target globs the utility sources but
lists only OpenVINO. It also gives no cross-package visibility in that target
and does not establish any existing Bazel package default. The platform-specific
header at CMake line 14 is outside its flat header globs.

Repair: inspect utility source dependencies and actual workspace conventions,
provide dependency/visibility/platform handling, and resolve runtime labels or
clearly label the result an integration sketch rather than a complete build.
The omitted declared dependency is visible in the evidence; actual compile/link
failure and platform coverage were not tested. Honest placeholder disclosure is
good, but does not establish completeness.

## Additional Repair or Verification Targets

### Playwright attribute polling: useful approach, over-certified implementation

ID: `02b63f9e755785a696a09147a38e4b6d08aafe04620c8268a35944463e5aeafa`.
Repository: `microsoft/playwright`.

The Node-side polling approach respects the central no-evaluate requirement.
However, only `locator.ts:1-240` was retrieved: the actual `getAttribute`
signature/timeout logic is not among the observations. The helper checks its
deadline only after awaiting an unbounded-by-this-helper `getAttribute` call;
its advertised maximum therefore is not enforced by its own control flow.
It also imports unused `expect` from `@playwright/test`, despite the request
to avoid test functions. An unused import is not itself a test-function call,
so that alone is not a decisive rejection.

Repair: retrieve the method contract, bound each read by remaining time, remove
the test-framework import, and distinguish waiting for a specified value from
detecting any change from an initial value. Require a stable locator whose
selector is not the changing test ID. The saved review's unconditional
"correct and working" claim exceeds the evidence; no execution occurred.

### Redis file QA: correct hits, incomplete search coverage

ID: `46a411963b747bd0c0a871ee67313c106110069767ae60c5f04bcc58e1b09e29`.
Repository: `lucas6028/daily-song`.

The two listed files and line references are supported. But the only search
result explicitly has `limited: true`; lockfile matches consume most of its
30 results. The answer does not disclose that boundary, and the reviewer marks
completeness true. This does not prove another functional Redis consumer exists.

Repair: narrow searches by source directories and inspect dependency manifests,
or say "the retrieved matches show" rather than treating this as complete file
coverage. Do not invent missing files to justify rejection.

### Telegraf migration: plausible core answer, missing API evidence

ID: `1413dd4a4255800c9b8aeb34f436d38eb356e891d4f1d3ce93693a16ac097ef0`.
Repository: `feathers-studio/telegraf-docs`.

The user supplies the deprecation notice. Retrieved examples support the old
`on("text", ...)` usage, but the deprecation search is empty and no filter
implementation/signature is retrieved. The response introduces `message('text')`
and several additional replacements, including `message()`, without establishing
their contracts from this snapshot. The reviewer treats all as API-grounded.

Repair: obtain pinned dependency/filter documentation or narrow the answer to
the supported migration with an explicit verification limitation. This review
does not independently declare the proposed core migration incorrect; the
defect is unsupported API certification and extra unverified guidance.

## Broadly Supported Answers

- **Path integrator QA**, ID
  `7eef0e44d2222a9ea730545cf3de208d872fd7a7ffac0bae8b4fd15ae9041e70`,
  `DaWelter/ToyTrace`: standard-path file contains `ForwardPathTracer` at
  lines 59-70 and BDPT allocation at 50-53; guided file declares
  `PathTracingAlgo2` at line 63. Useful navigation answer. Caveat: it should
  distinguish wrapper/allocation from core integration logic; the standard file
  delegates to `RandomWalk::PathTracingWorker`. It does not establish which
  integrator is selected by default. No definite wrong-file finding from the
  inspected evidence.
- **Music generator QA**, ID
  `7720bdffbb504f7631b82a9d9043f997da6ae6c14e85c6dd89a32265e3a8eff4`,
  `Francesco149/TempleOSGit`: `Adam/ASnd.HC` search hits support the named music
  functions; listing supports `Apps/Psalmody/` and its examples. The answer
  explicitly qualifies the entry point as "likely". It is a useful directory
  pointer, not proof of the exact music-generation algorithm; search was limited
  and no implementation was read.
- **Project overview**, ID
  `20070d6d9e5605e610127bb9d78661bd8a8083c4499774acf6666ba09e1dd751`,
  `infiniflow/ragflow`: README lines 70-120 support RAG/agents, chunking,
  compilation and thinking-mode claims; the root listing supports Go server,
  web, model configuration and Docker observations. Broadly faithful summary.
  Promotional performance wording is README positioning, not measured quality.

## Priority Fixes Before Treating Passes as Finished Targets

1. Review explicit user constraints against actual before/after content,
   especially style preservation and complete implementation requests.
2. Separate correctness, completeness and evidence coverage. A qualified sketch
   may be useful without qualifying as a verified complete implementation.
3. For build/code tasks, compare declared dependencies and retrieve used API
   signatures; do not infer successful compilation from plausible-looking code.
4. Treat `limited: true` and unread continuations as coverage boundaries, not
   as evidence of absence. Allow scoped answers without demanding whole-repo
   scans for simple navigation questions.
5. Preserve these original trajectories and audit decisions. Proposed repairs
   require a new review; this report does not automatically admit repaired text.

## Reproducibility

Each ID above resolves to `ROOT/trajectories/ID/trajectory.json` and its
`outcome.json`; quoted repository line numbers come from embedded tool results.
The sample was chosen by task type from the pass inventory, not by reviewer
explanation. Trajectory SHA-256 values, in report order:

| ID prefix | SHA-256 |
| --- | --- |
| 09580602128a | `5558e6b8eab9d3bcc8e7f76d3249068d73934a76abb1eadb6ef131b17a30525d` |
| ef7ba0d57837 | `b19af70778f399646e07f171ed4f70c84fad5f811713f17934225e32910a2aaa` |
| 02b63f9e7557 | `41fc68491a010147da6d94694faa028334f70c5e90004d694edc2b5bc7432f0e` |
| 46a411963b74 | `cfc089ee8b6f6487b7b15fef75316fda99da6c9bdecfb546fc06f44e74d8f585` |
| 1413dd4a4255 | `a79a767f9609bc68afa105d5c7bcf2ef4b0bb1923e27abbfe69e506958a4f0f6` |
| 7eef0e44d222 | `55d783805a290f9605cad4dd6fafff3e6678fdbec507192096e6ca3c7c3a7c5f` |
| 7720bdffbb50 | `798425696413e7d597de5e0f52daa4c5268333a9a779d237583d03e25efb40f7` |
| 20070d6d9e56 | `279dcfd94afc5b2873187c64a529d241f214acb4bfb35131ff1b8f90a3d7da53` |
