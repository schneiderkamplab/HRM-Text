---
type: Runbook
title: DFM12 Accepted Identity Export
description: CPU-only accepted identity packages and strict preserved-source integration for the incremental exporter.
tags: [dfm12, identity, export, provenance]
status: stable
last_updated: 2026-09-29
confidence: high
---
# DFM12 Accepted Identity Export

## Separate XXL-wide Variant (2026-09-29)

**Latest owner policy, 2026-09-29:** supersedes the publication-only/no-integration
boundary below. Register all 21 XXL-wide packages alongside all 21 XL packages
in `dfm12/training_sources.json`, with explicit `identity_repeat: 0` for BOTH
profiles. This also supersedes reusable identity repeat 10 for the default DFM12
source config. Both Catalan variants are included locally (XL 2,000 rows,
XXL-wide 1,995), without waiting for HF. The pending XXL-wide Catalan publication
is an explicit `local_only_disabled_packages` entry: local accepted-only package
validation remains mandatory, and enabling it while this exception is present
raises an error. Other publication checks remain unchanged. Verified 42 identity
packages at repeat zero; ten builder tests pass. Existing sampled arrays,
training processes and their plans were not changed or resampled.

**Scope correction, 2026-09-29:** the nine-language publication below used
historical local exports and is superseded as the intended scope. The owner
requested all 21 languages. The adapter now reads the authoritative
`data/dfm12/identity21-export-20260929-v1` (42,000 conversations), verifies its
per-language source manifests and publication receipts, preserves original
admission categories (including curated corrected DA/EN), and re-audits all
converted rows plus 21 width/head Q&As. No source audit is reused as acceptance.
New work lives in `data/dfm12/identity-xxl-wide-21-20260929`; exports go to
`exports_dfm12/identity-xxl-wide-21`. Detached PID 3554874 launched with four
requests per shared endpoint, without changing servers or other clients.
The additional languages are de/fr/es/it/cs/pt_pt/fi/et/ca/el/ro/uk.

On completion, `dfm12.publish_identity_xxl_wide` updates only the nine owned
XXL-wide repositories (guarded by prior published revisions) and creates the
twelve missing XXL-wide repositories. Commits use parent revision guards and
verify every uploaded file by hash at its immutable commit. Original XL Hub
repositories and the training registry remain unchanged. Completion is recorded
in the new work root's `completion.json`; until that exists, this expansion is
in progress, not published. Five focused tests pass with all 21 language codes.

Explicit owner boundary: **export and publish only; do NOT integrate these
21-language XXL-wide packages into DFM12**. Training is controlled by another
thread and must not be started, stopped, modified, or otherwise interrupted here.
At the owner's request, detached shutdown watcher PID 3555714 waits for the
complete prepared audit queue to become terminal, then stops only the pinned
eight existing audit server process trees (API PIDs 4054202--4054209, with
creation-time and command-line checks). It never selects processes by GPU or
broad name matching. Its logs and eventual `servers-stopped.json` live in the
new work root. Export/publication remain CPU work after GPU release.

Concurrency update: owner explicitly requested 512 requests per server instead
of four. Only the identity client was restarted (PID 3597401); 30 interrupted
leases were returned to pending without charging a failed attempt. Completed
results were preserved. `identity_audit_async.py` uses bounded aiohttp requests
and a single executor-owned SQLite connection with claim/lease indexes, not
4,096 OS threads. Initial live observation: 339--348 running and 158--162
waiting requests per server, KV occupancy 97.9--99.7%. The 4,096 HTTP limit
includes waiting requests; it is not a guarantee of simultaneous GPU execution.
Five focused tests and a 512-concurrency local HTTP mock (20/20 jobs) passed.
Server processes, training, shutdown watcher and DFM12 integration were untouched.

Audit completed: 42,014 judged, 41,752 accepted, 262 rejected, seven exhausted
request failures. Shutdown receipt confirms all pinned audit processes exited,
with zero survivors. The deterministic export check additionally caught Finnish
record `9820a774a0472458a84441f24dedfcd91e5813e8e3cb3f21a82dbbf9a06a7c08`:
the glued text `VaikkaXL` evaded word-boundary conversion and passed the judge.
It is excluded, not silently edited or given a fabricated audit. This leaves
41,751 exportable conversations. `export-exclusions.json` records this extra
filter independently of the immutable original audit decisions. CPU publication
resumed as PID 3602347; no servers were restarted and no training was touched.

Publication status: 20/21 repositories verified (39,756 conversations), including
all nine replacements and eleven new languages. Catalan's 1,995-row package is
ready locally but repository creation failed with HF HTTP 429: the account's
300-repositories/day creation limit was reached. Its receipt remains `prepared`,
not `verified`; `completion.json` is absent. A direct Hub check confirmed the
Catalan repository does not yet exist. Resume publication after the creation
quota resets; existing verified uploads will be skipped. No audit rerun needed.

Owner-authorized one-shot retry scheduled for **2026-09-30 14:47:07 CEST**
(24 hours after launch), detached PID 3636196. The CPU-only
`scripts/retry_catalan_identity_upload.py` invokes the revision-guarded publisher
with only the Catalan package selected. Logs, status and exact launch identity:
`data/dfm12/identity-xxl-wide-21-20260929/catalan-upload-retry/`.
This process survives CLI disconnects, but not a machine reboot; its absolute
deadline is in `launch.json` for manual relaunch if required. It does not start
servers, access GPUs, modify training, or change the repeat-zero source policy.

The owner authorized adapting and publishing the nine identity packages as a
separate XXL-wide variant. `config/arch/size/XXL_wide.yaml` confirms 32 stored
layers (16 L/16 H), hidden size 2560, 20 heads of dimension 128, expansion 4.
The selected identity remains full-bp with two H cycles and three L cycles per
H cycle. These describe the chosen profile, not all historical training phases.
Training team, Mimir name, organization and historical v1 facts remain unchanged.

`python -m dfm12.identity_xxl_wide --publish --concurrency 4` reads the verified
nine published XL packages, converts profile references on CPU and adds one
width/head Q&A per language. It preserves original IDs, message hashes and
publication revisions in provenance. The inherited audit is evidence about the
original, not acceptance of the adaptation. Every adapted candidate is freshly
audited against the new profile on the existing Gemma 4 26B-A4B servers at
ports 8600--8607, with only four additional concurrent requests per endpoint.
No server restart or other-client change is performed. CPU inspection found
seven inherited unknown-dimension sentences (five English, one Bokmal, one
Swedish); some escaped the fresh automated audit. Exact reviewed replacements
now state the known width/head count without inventing total parameter counts
or numerical weight values. Only the changed rows were superseded and requeued;
completed unrelated judgments were retained. The original jobs are archived in
`superseded-*.json`. This is evidence that the model audit is not a guarantee of
factual completeness; deterministic checks supplement it. Rejected/unresolved
rows are not exported.

State/logs: `data/dfm12/identity-xxl-wide-20260929/`.
Target exports: `exports_dfm12/identity-xxl-wide/`.
Target public repositories: `schneiderkamplab/dfm12-identity-xxl-wide-full-bp-`
followed by `da`, `en`, `fo`, `is`, `nb`, `nn`, `nl`, `pl`, or `sv`.
The job validates accepted-only packages and then invokes the existing
receipt-based uploader. Read `completion.json` and upload receipts before
claiming completion. Five focused tests passed, including exact dimension-claim
repairs and preservation of historical/team text.

Completed on 2026-09-29: all 8,724 candidate audits finished with no unresolved
requests; 8,690 conversations were accepted and published. Rejections were 25
Icelandic and nine Faroese conversations. All nine new width/head Q&As passed.
Accepted rows by language: en 983, da 970, nb 965, nn 962, sv 980, nl 981,
pl 978, is 932, fo 939. All nine public repositories have verified revision
receipts in `exports_dfm12/identity-xxl-wide/metadata/upload-receipts.json`;
the local completion record is
`data/dfm12/identity-xxl-wide-20260929/completion.json`. Shared audit servers
and other clients were left running and unchanged.

Do not append these alongside the XL identity targets in a single training
mixture. They are an alternative identity selection for XXL-wide, retaining
repeat 10 as mixture policy. The current DFM12 registry, sampling, XL exports
and training remain unchanged by this publication job.

## Smoke Follow-up: Data Review and Recommendations

Read-only CPU inspection, 2026-09-26; **no dataset, training or pilot changes**.
The four flawed adapted answers are preserved verbatim in
`data/dfm12/identity-smoke-20260926-v1/responses.md` under `da-team`,
`da-architecture`, `en-architecture` and `en-namesake`. None approaches the
160-token output cap (82, 104, 77 and 21 retokenized tokens respectively).

### Evidence

- Accepted DA/EN identity data contains 969/982 conversations, all explicitly
  `xl-full-bp`; no generic-profile conversations were found in this slice.
  The registry separates generic architectural facts from the selected XL
  profile's 16 layers per L/H module. Generic-profile mixing is therefore not
  an established explanation for the disclaimer or omitted counts.
- Correct role distinctions are present. DA record
  `019155fdff78b8032a8246547bb867d2d1f8a3e847b4818084477f06871f31b9`
  attributes organizational leadership to both names, then says
  `Træningsteamet ledes af Peter Schneider-Kamp`. EN record
  `0e193a0aaa0e8a86ba5fa7e9368768681a2ea4a014ea1e1ce23127438e9be229`
  explicitly rejects the premise that Kristoffer leads the training team.
  Frequently putting both leader names in adjacent organizational/team sentences
  is a plausible conflation risk, not evidence that these targets are wrong.
- Both languages have 91 planned namesake-topic conversations. The first user
  question names Mimir in 82 DA and 76 EN records; 87/91 EN first questions mention
  Mimir or Norse. The four EN exceptions still include correct naming answers.
  Example `d67d85bfab9db44b3df1e99ff35b40395e97bf0a49bc894753faf6fc2a55a8c9`
  asks `Can you tell me about your name? Is it related to anything else?` and
  correctly explains the Norse metaphor. The smoke's English nonanswer is not
  an exact accepted assistant turn. Weak coverage of short, uncued question
  forms is a plausible generalization gap, not a proven causal attribution.
- Each language also has 91 planned architecture-topic conversations. First
  assistant turns explicitly contain `16`/`sixteen` in 51 DA and 44 EN cases.
  These are coverage counts, not error rates: many questions ask only about
  module interaction or passes. EN record
  `2f4fb1c740948a0f9253b13be5c306253d7a391cf51fed03ab352be47ebb8f1f`
  correctly explains cycles/passes but omits layer counts and adds a scoped
  unknown-hardware qualification.
- Generator `dfm12/identity.py` systematically combines topics with styles
  such as `acknowledge what is unspecified` (99 accepted records per language)
  and `clarify which release the question concerns` (99 DA / 97 EN). DA record
  `428ae921aaad8579922d703182e344a2512215eb3759046b47b20a72465fa762`
  starts with lack of access to workflow details and then supplies known XL
  architecture facts. Most inspected caveats are legitimately scoped; blending
  them into a blanket denial of known layer/cycle facts is a model error.
- Build receipt `data/sampled_dfm11_identity_da_en_1000steps/build-receipt.json`
  and source-row arrays show complete prepared coverage of 1,968 DA and 1,981
  EN assistant targets, each selected 15–16 times. Read-only decoding verified
  correct role/namesake text in actual tokenized targets (DA row 9, EN row 85),
  with raw training template and no identity-facts system message. These are
  prepared exposure counts, not a claim that every repeat preceded the exact
  1,000-step stopping boundary. This was not a scan of all broad DFM11 replay;
  conflicting identity targets in that 95% replay remain unmeasured.

### Proposed Amendments, Not Executed

1. Add a small, balanced, versioned correction slice with short uncued DA/EN
   questions and intent contrasts: name versus namesake versus creator;
   organization leaders versus training-team lead/members; cycles versus layers.
   Preserve accepted originals and audit/provenance, rather than editing targets
   in place or inserting the four smoke questions as the only repair set.
2. Put the requested fact first. For team-only questions, name Peter as training
   lead before listing members; mention organization leaders only when requested.
   For namesake-only questions, explain the Norse wisdom/knowledge metaphor,
   not an organizational introduction. Include follow-ups with genuine context
   and negative/contrast examples to test intent separation.
3. Make completeness and contradiction checks explicit: a layers-and-cycles
   question must cover 16 layers per L/H module and 2 H x 3 L cycles. Never deny
   access to these supplied facts and then state them. Limit unknown-detail
   caveats to genuinely unspecified hardware, parameter counts or deployment
   capabilities; do not apply uncertainty/which-version styles indiscriminately
   to stable names, organization or namesake facts. Keep historical-v1 versus
   current-XL distinctions intact.
4. Independently review role relations, requested-answer coverage and native
   wording, including Danish `et mytologisk væsen`. Audit sampled broad replay
   for first-person competing-model identities before any targeted exclusion;
   ordinary discussions of other models are not identity conflicts. No replay
   contamination finding is established by this inspection.
5. Do not default to more epochs or a higher identity fraction: this slice is
   already heavily repeated. After a reviewed data revision, compare bounded
   short continuations while initially retaining the existing low LR and broad
   replay mix. Use held-out paraphrase families, unprimed questions, multi-turn
   consistency and general-capability retention checks to choose the fewest
   useful updates. Do not tune and report on the same 16-question smoke alone.

## Unprimed Identity Smoke, 2026-09-26

**Supersedes the identity-probe-pending observation below for this small smoke.**
`scripts/smoke_dfm12_identity.py` completed 16 DA/EN questions on the adapted
`step_2878261` and the original XL `epoch_10`, sequentially on GPU 7. Both used
non-EMA weights, the raw training Gemma template, no system/identity priming,
greedy decoding, batch 1 and a 160-new-token cap. No W&B, scheduler, server,
training or pilot changes; all original eight training GPU processes remained
present afterward and GPU 7 returned to 46,108 MiB free.

Manual fact-registry assessment: adapted **12 pass / 3 partial / 1 fail**;
baseline **1 pass / 3 partial-inconclusive / 12 fail**. The baseline says
Munin/Chatbot and drifts to Alibaba/DeepSeek attribution; the adapted model
identifies Mimir, correctly attributes Danish Foundation Models and its leaders,
rejects the Gemma premise and distinguishes historical truncated versus current
XL full backpropagation. Residual adapted issues: Danish team-leader conflation,
Danish architecture's contradictory disclaimer, omitted English layer counts,
and an English namesake nonanswer repeating the organization attribution.
The Danish namesake meaning is correct but has minor agreement error
`en mytologisk væsen` instead of `et`; factual passes are not native-language gold.

Capped baseline architecture/backpropagation outputs are explicitly marked:
missing detail alone is not a failure. Wrong identities/module definitions
already emitted before truncation are assessed as observed. SimpleEngine returns
no finish reason; `censoring.json` conservatively flags retokenized near-cap text.
Three baseline outputs expose unrequested `<think>` text. No further experiments
were run; this does not establish general retention or multi-turn robustness.

Artifacts: `data/dfm12/identity-smoke-20260926-v1/` contains exact prompts,
rendered input, token IDs and responses in `responses.json` / `responses.md`,
manual judgments in `assessment.json` / `assessment.md`, and the detailed
adapted assessment. Checkpoint metadata, config, tokenizer/template and fact
registry hashes are retained. No accepted training data was modified.

## Completed XL Adaptation, 2026-09-26

The 1,000-update DA/EN identity interlude completed at step 2,878,261, with a
verified scheduler checkpoint-ready receipt at 08:43:18 Europe/Berlin. Output:
`checkpoints/dfm12/XL-identity-da-en-from-dfm11-epoch10`, tag `step_2878261`.
W&B run `DFM5/dfm12-xl-identity-da-en-1000` finished and logged a successful sync.
Final mixed-batch metrics: loss 0.759633, accuracy 0.810659, exact accuracy
0.346090. Raw W&B summary verifies base/embedding/head LR 1e-5, H 5e-6,
L 1.6666666667e-6 (terminal summary rounded tiny rates). Runtime was about
22 minutes after progress began. These are training metrics, not evidence of
identity recall or retention; identity-specific generation probes remain to do.
The subsequent multilingual calibration failed before generation, released its
servers, and XXL resumed automatically in the original run from 660500.

## Proposed XL Identity Adaptation, 2026-09-26

**Superseded specification, 2026-09-26:** the user changed the trial to 1,000
steps, ONLY Danish and English identity, 5% identity / 95% broad DFM11 by
rendered tokens. Keep the final XL epoch-10 base LR **1e-5 constant**, with
no warmup and no decay. With BP8 and lr_auto, H=5e-6, L=1.666667e-6,
embedding/head=1e-5. Clear inherited cooldown/piecewise/explicit module overrides.
At global batch 262,144 the nominal budget is 262,144,000 tokens: identity
13,107,200 and replay 249,036,800. DA+EN supply is 821,578 tokens (1,951
conversations), so identity exposure is about 15.95 passes, not repeat 10.
The implementation must verify packing yields at least 1,000 optimizer steps
and report the actual ratio after packing rather than promise exact token
occupancy from the nominal batch capacity. The earlier nine-language 500-step
and warmup/decay proposal below is retained only as historical context.

Prepared CPU-only corpus: `data/sampled_dfm11_identity_da_en_1000steps`,
Hydra data config `dfm11_identity_da_en`; builder
`python -m dfm12.build_identity_adaptation`. The completed build has
262,144,863 rendered tokens: DFM11 249,037,528, Danish identity 7,341,434,
English identity 5,765,901 (identity fraction 5.000035%). It draws 568,200
rows uniformly without replacement from the already weighted/shuffled DFM11
epoch-0 index, rather than taking a contiguous source-file prefix. All 3,949
DA/EN assistant targets occur, representing 1,951 accepted conversations.
Repeated targets share compact token spans; no inherited token store is copied
wholesale. The new backing store is about 1.00 GB.

CPU simulation of the actual multipack sampler with 8 ranks, GAS2, GBS262144
found 1,003 available optimizer steps. Stop at exactly 1,000 new steps, global
step 2,878,261, rather than exhausting the dataset. The first 1,000 consume
260,653,268 non-padding tokens, including 13,003,888 identity tokens (4.98896%).
Whole examples and batch packing account for the tiny deviation from 5%.
`epoch_10` aliases `epoch_0` for continuation into the eleventh data epoch.
Four focused tests passed. No training, scheduler, GPU or W&B changes were made.

### Authorized Launch After XXL 660500

User authorized running the identity stage, then continuing XXL. On 2026-09-26,
`scripts/schedule_xl_identity_interlude.py --arm` passed preflight and set the
existing scheduler's soft-stop. Detached handoff waits for complete
`ephemeral_step_660500` from XXL, preserves it under
`checkpoints/preserved/xxl-before-xl-identity-660500`, and stops only the verified
XXL process group after the payload/metadata completion gate.

Once GPUs are free, it inserts one all-GPU identity training row and a terminal
barrier into the EXISTING plan
`logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725`.
It resets only `dfm11-e3-train-700000` to resume from the preserved source
660500 checkpoint after that barrier. The scheduler is then restarted. The
barrier releases XXL after identity success OR failure; identity has zero
automatic retries to avoid replaying partial logged progress from epoch 10.
All later XXL training/evaluation rows remain unchanged. Neither the XL nor
XXL source checkpoint directories or historical W&B runs are overwritten.

- Identity checkpoint output: `checkpoints/dfm12/XL-identity-da-en-from-dfm11-epoch10`.
- W&B project/run: `DFM5/dfm12-xl-identity-da-en-1000`;
  display name `DFM12-XL identity DA-EN 5pct 1000steps`.
- Start/stop: 2,877,261 to 2,878,261; dataset epoch 11 uses index `epoch_10`.
- Constant LR 1e-5, lr_auto, BP8, GAS2, 262144 tokens, FSDP FP32 parameters,
  BF16 compute, no activation checkpointing, no LR warmup/decay/cooldown.
- Retains optimizer moments and EMA; evaluate non-EMA for adaptation effects.
- Regular checkpoints every 250 absolute steps, ephemeral every 100, plus a
  forced regular checkpoint at the exact final step.
- Identity log:
  `logs/training/dfm12_XL_identity_da_en_1000steps/xl/train_until_step_2878261.log`.
- Resumed XXL log:
  `logs/training/dfm12_XL_identity_da_en_1000steps/xxl-resume/train_until_step_700000.log`.
- Handoff/runner logs and receipts are in
  `logs/training/dfm12_XL_identity_da_en_1000steps/`.

Six focused tests pass (mixture/packing and scheduling including failure release).
Hydra and PretrainConfig validation passed; CPU resume resolution verified epoch
11, step 2,877,261, zero skipped batches, and the exact automatic module LRs.
Latest launch state was `waiting_checkpoint`, not yet active identity training.

Recommendation only; no training/sampling was launched or scheduled. Start from
the completed DFM11 XL `epoch_10` checkpoint (step 2,877,261), whose recorded
terminal base LR was 1e-5. This concerns the existing nine-language identity
corpus, NOT the new multilingual synthetic pilots.

Initial experiment: 500 optimizer steps at the existing 262,144-token global
batch, with 90% broadly sampled DFM11 replay and 10% accepted identity by
rendered training tokens. Total budget 131,072,000 tokens: 117,964,800 replay
and 13,107,200 identity, about 3.19 passes over the full 4,109,461-token identity
corpus (approximately 3.54 after a representative 10% token holdout). Do not
apply the broad DFM12 repeat=10 on top of this explicit mixture. Keep the
existing identity language proportions for the first trial; this is not a
general multilingual capability intervention. Audit held-out prompts in DA/EN
especially, with paraphrases and follow-ups not copied from training.

Suggested base LR: gently warm from 1e-5 to 2e-5 over 25 local adaptation
steps, then cosine-decay to 5e-6 by local step 500. Keep `lr_auto=true`, BP8,
the existing optimizer type, target-only loss, clipping and training template.
At peak this yields embedding/head 2e-5, H 1e-5, L about 3.333e-6. Clear old
absolute-step cooldown/piecewise settings when implementing this distinct
schedule; otherwise they can override the proposed local schedule.

Probe at 100, 250 and 500 steps; select the earliest satisfactory checkpoint.
Test factual identity, Mimir versus Gemma ancestry, historical versus current
training details, resistance to false premises, and no unsolicited identity
recitation in unrelated prompts. Compare a fixed capability regression suite.
At most extend to 1,000 steps if held-out identity improves without regressions.
This is an engineering starting point, not an empirically tuned optimum.

Evaluate non-EMA weights during this short intervention: with decay 0.9999,
after 500 updates approximately 95.1% of an existing EMA's weight remains on
its starting value. Do not interpret that lag as failed adaptation. A separate
faster/reset EMA is optional, not an instruction to overwrite the original EMA.
Replay motivation is supported by [InsCL](https://arxiv.org/abs/2403.11435);
the proposed numeric mixture and LR are local experimental recommendations.

## Authorization and Scope

**Superseded, 2026-09-25:** the historical `accepted_exports_allowed: false`
in the identity generation/bulk-audit receipts is no longer an export hold.
The user explicitly authorized accepted-only export and public upload including
identity. This helper performs local CPU export only; parent owns upload.
Historical receipts remain unchanged. Automated acceptance is not human or
native-speaker certification. See [identity generation](/pages/dfm12-identity-generation.md)
for the earlier operational scope and documented language-quality uncertainty.

Implementation is `dfm12/export_identity.py`; tests are
`tests/test_dfm12_export_identity.py`. The helper does not modify the source DB,
accepted originals, shared export modules, audit roots, servers, training or
evaluation. It does not sample, generate, retry failed jobs or upload.

## Completed Local Build

Root: `data/dfm12/identity-export-20260925-v1`.
Input: `data/dfm12/identity-9000-20260924-v1/jobs.sqlite`.
All 9,000 generation requests are terminal: 8,931 generated, 69 failed.
179 generated duplicates are excluded. All 8,752 unique audit decisions are
complete: **8,715 accepted, 37 rejected**. No failed generation enters training.

| Language | Accepted conversations | Rendered tokens |
| --- | ---: | ---: |
| da | 969 | 460,169 |
| en | 982 | 361,409 |
| fo | 947 | 465,860 |
| is | 956 | 545,069 |
| nb | 964 | 439,202 |
| nl | 980 | 446,867 |
| nn | 961 | 453,209 |
| pl | 977 | 488,930 |
| sv | 979 | 448,746 |
| Total | 8,715 | 4,109,461 |

Repeat **10** is mixture metadata only: 41,094,610 effective tokens per epoch,
not 87,150 physical rows. Each full native conversation remains one row,
including all turns. The current pinned Gemma 4 non-thinking renderer rerendered
every accepted conversation, enforcing its 4,096-token context limit and exact
agreement with stored rendered-token accounting. Counts are not final sampling.

Nine folders named `dfm12-identity-xl-full-bp-{language}` follow the existing
public-package layout: `data/train-00000.jsonl.gz`, metadata, dataset card and
standalone validator. No Hub repository was created or uploaded by this helper.
The total compressed training files occupy 2,929,314 bytes; full public-package
files occupy 18,890,703 bytes. The larger local SQLite snapshot is not public.

## Provenance and Gates

The exporter snapshots SQLite read-only and verifies generation IDs, generated
messages, exact identity/audit joins, audit payload IDs, bulk cohort hashes,
pilot review hashes, facts file and canonical registry hashes, profile/context,
duplicate lineage, valid keep decisions with all three scores at least four,
and student tokenizer/template pins. Snapshot/source hashes are distinct:

- Original database SHA-256: `23bdf7818f52dfa701f4f41e01dbdb9b48e8c6f11002174c42e4e8e75900a12d`.
- Snapshot SHA-256: `8c2c61b6658c4e3ceb8fb94370dc96a5cf7e42b50a9d4495eb873a64da6739e8`.
- Facts file SHA-256: `d81c94652a494d84e9937299964baad5519f150e96bea056ce197d5c95488a71`.

Accepted metadata preserves full fact context, source references and models,
raw accepted records/decisions, job IDs and canonical/raw source hashes.
None is appended to assistant messages. Facts, including historical-v1 versus
current-XL distinctions, are not rewritten. References are retained as supplied;
no new claim of independent report verification or blanket relicensing is made.
Rejected public metadata contains decisions/IDs only. Pilot review findings and
the full SQLite snapshot can contain excluded text and are not copied into
public package folders.

## Parent Integration Contract

```python
from dfm12.export_identity import export_identity, verify_identity_source

inventory = export_identity(run, new_output, repeat=10)
owned = verify_identity_source(
    new_output, inventory["identity_source_manifest"], inventory["packages"])
```

The final companion schema is **`dfm12-identity-source-v1`**, with fields
`schema`, `source`, `repeat`, `packages`, `owned_files`. It is NOT the alternate
`version: 1` / `scope` / `sources` proposal. The final companion lives at
`metadata/identity-source-manifest.json`, 24,897 bytes, SHA-256
`31bae28141d4db2dda3cf170609bc746f213cd0594c715a01934cb35a2de1f56`.

Parent copies the nine package folders and unchanged companion into the combined
export root, merges `packages` summaries, and retains the companion descriptor
under `identity_source_manifest` in the combined inventory. Keep the existing
five `audit_full` roots; there is no fictitious sixth root and no blanket bypass.
Poincare's incremental `validate_previous` must explicitly call
`verify_identity_source(root, companion, packages)`. It returns only the nine
owned identity component summaries after verifying the companion hash, exact
inventory entries, every owned file, no extra files, matching source/counts and
repeat, and independent accepted-only package validation. All nonidentity
source-plan checks remain in force. Read-only inspection now confirms that
Poincare's `validate_previous` and Harvey's `merge_identity` call the agreed
helper. The real isolated output also passes `validate_previous` with its
explicit companion; this helper did not launch the parent orchestrator.

Harvey handoff: `data/dfm12/identity-export-20260925-v1/handoff-harvey.json`.
Direct agent messaging was unavailable; API and schema were relayed via parent.
Parent owns central index/status/log changes. Public uploads must select named
package folders only, not the local root snapshot/manifest/handoff/companion.

## Reproduction and Tests

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.export_identity \
  --run data/dfm12/identity-9000-20260924-v1 \
  --output data/dfm12/identity-export-20260925-v1
```

The first-pass process exited successfully. That output now exists and is
immutable to the CLI; use a new isolated output path for reproduction.
The companion seal was added after the initial first pass; subsequent CLI
builds seal and validate it before publishing the local output directory.

Verification: **50 tests passed** across identity export/generation, the shared
incremental exporter, upload and orchestration modules (CPU tests only).
Coverage includes failed/duplicate
exclusion, native multi-turn preservation, repeat metadata, unchanged input,
fact/source/audit/render drift, missing joins, incomplete work, invalid scores,
and companion/inventory/file tampering. The incremental test requires explicit
identity ownership and rejects duplicate audit-root ownership. No shared export
code was edited. OKF validation reports one missing immediate-child index link
for this new page; parent owns that index update.
