# Uploaded DFM13 Arena: Manual Quality Review

Date: 2026-10-01. This assistant inspected three deterministically selected
examples from each of the four published exports, including preceding context.
These 12 examples expose failure modes; they do not estimate corpus-wide defect
rates. No export or training source was modified.

## Reproduction And Provenance

Run `python scripts/sample_uploaded_dfm13_arena.py`. It selects the three
smallest SHA256 ranks of `20261001:<export-name>:<example-id>` per export,
verifies each local payload against its export manifest, and writes:

- `logs/arena_review/20261001/uploaded_quality_samples.jsonl`: full conversations,
  target indices, provenance, source line numbers and sampling ranks.
- `logs/arena_review/20261001/uploaded_sampling.json`: counts and file hashes.

All four local SHA256 values were also checked against the live HF
`data/train.jsonl` LFS hashes and matched. The review covers what was actually
uploaded, not a separately reselected upstream sample.

| Repository under schneiderkamplab/ | Rows | SHA256 |
| --- | ---: | --- |
| dfm13-ai-arenaen-preferred | 2602 | c943d1f75116eb51289373bd023b91a9d3064055ee0bd1b687e7ee5411b27d3b |
| dfm13-arena-human-preference-100k-preferred | 64939 | 96ad78e9785b7e02ddd58d610f0f4a1e4b6597b56109f3b0abceb1c8d0a76b3f |
| dfm13-arena-human-preference-140k-preferred | 98230 | 4a3c048120d37035c850811eebea114485a66ecd74a63613cb80cabc2a34ff02 |
| dfm13-arena-human-preference-55k-preferred | 39471 | cbd5db0b4a63afd47bfba1e1470e127a421c247d088fe59fca8f105aa37780e1 |
| Total | 205242 | |

## Individual Verdicts

IDs for international sources omit the common `arena_human_preference_<size>:`
prefix below. These are target-quality verdicts, not parser failures.

| Dataset / ID | Request and answer | Verdict | Reason / required action |
| --- | --- | --- | --- |
| AI-Arenaen `5422691d-5e50-44a8-909e-6f4b884bd5fd:a` | Expand a bureaucratic municipal message into understandable Danish for an 80-year-old. | Usable with minor editorial caveats | Explains individual assessment clearly and preserves the main message. Adds an invitation to contact the municipality and assumes the citizen mentioned the law, although the supplied text only cites it. Treat as a draft, not verified legal advice. Avoid adding unsupplied facts in a strict rewriting task. |
| AI-Arenaen `c90616aa-93fb-41dc-b526-7ca86fadc635:b` | Draft an information-security logging policy. | Repair | Comprehensive and relevant structure, explicit placeholders, but the injunction against minimal logging needs reconciliation with data minimization. Add explicit exclusion/redaction of passwords, tokens and sensitive payloads. Minor Danish agreement and English calques also need editing. Not a claim that the draft violates a particular law. |
| AI-Arenaen `308f5e6d-79a2-4097-a3ce-7f979e5c642c:b` | Multi-turn discussion of Danish regional humor and whether English reasoning distorts it. | Reject current target; regenerate if retained | Final answer claims it searches its training data at inference time and confidently explains an English internal pipeline that the conversation does not establish. It flatters and ratifies the user's premise rather than separating visible text from unknowable implementation details. Earlier context reinforces the same invented explanation. This is particularly bad identity/epistemic training. |
| 100K `58a859437dfd4e41aad1567f5ac2c133:b` | Avoid busy waiting in Java socket communication. | Repair with code validation | Blocking reads and selectors are appropriate concepts. The selector example assumes `socket.getChannel()` is non-null, does not construct a SocketChannel, and cancels registration after every event. The CompletableFuture example merely moves blocking work to another thread. Keep the idea but replace and execute the examples. |
| 100K `9fa8a86875584778823e3eca66cb8bf2:b` | Russian question asking South Africa's capital. | Usable | Correctly distinguishes Pretoria, Cape Town and Bloemfontein with their functions, consistent with South African government material. Concise, relevant Russian. |
| 100K `53597585763d42758db829e019475abc:b` | Chinese request for comfort and encouragement when feeling low. | Usable, low-to-moderate value | Warm and responsive in Chinese. Generic reassurance is a style limitation, not a correctness failure. Could avoid guaranteeing that feelings are temporary and the future will improve, and invite the user to share what happened. No crisis is stated in the prompt. |
| 140K `a6460f5f-36f0-45b5-946c-22b2c7eeed8a:b` | Russian question about which tray an HP E60055 uses for bulk printing. | Reject current target; grounded repair possible | Invents a model equivalence and describes two 500-sheet trays. HP specifies a 100-sheet multipurpose feeder and 550-sheet input feeder. The UI and default-priority instructions are not substantiated. Retrieve the actual manual before repairing. |
| 140K `05a06fbd-71be-4c59-b2f1-a784850b003c:a` | Best phone below GBP400. | Needs dated verification | Structured trade-offs and acknowledges changing prices. Nonetheless the recommendations depend on historical availability and price, neither supplied as evidence. Not declared false merely because the devices are older. Keep only with a meaningful time anchor and checks, or regenerate using current evidence and label it as new. |
| 140K `0d10d661-9ba2-45b2-ac06-2b732be70ef9:a` | Word puzzle: backwards is forwards, table is chair; what is car? | Repair | Correctly notices ambiguity, then gives an unsupported supposedly most-likely boxed answer, reversing letters. No such transformation rule follows from the examples. State underdetermination and ask for the rule instead. |
| 55K `1365787044:a` | Difference between data governance and master data management. | Usable | Coherent standard distinction between organizational policies/roles and management of core data entities. Some repetition, but a useful explanatory target. |
| 55K `2310055574:a` | Are you Clippy? | Usable, low value | Correctly denies that identity and gives a generic assistant description. Does not import a conflicting specific provider identity. Low information density but not a reason to reject on correctness grounds. |
| 55K `3641017749:b` | User challenges a previous assertion that carbon steel cannot use induction. | Repair | Acknowledges the mistake but only partially corrects it, then makes an unsupported claim that stainless steel is more universally induction-compatible. Magnetic construction matters; carbon steel is normally ferromagnetic, while stainless grades/base constructions vary. Replace the correction rather than training this face-saving rationalization. |

Primary factual checks:

- [Oracle Socket.getChannel](https://docs.oracle.com/en/java/javase/18/docs/api/java.base/java/net/Socket.html): sockets not created for channels can return null.
- [South African government](https://www.gov.za/about-sa/south-africas-provinces): capital roles and Supreme Court of Appeal location.
- [HP E60055 specifications](https://support.hp.com/us-en/product/product-specs/hp-laserjet-managed-e60055-series/9364921): feeder capacities.
- [De Buyer material guide](https://www.debuyer.com/en/content/27-guide-to-materials) and [steel cookware](https://www.debuyer.com/en/619-steel-frying-pans): material/induction compatibility.

The 12 targets were structurally well formed in this inspection. The main risk
is semantic quality: preference filtering did its intended job but was never
an absolute correctness audit. Do not relabel the published files as audited.

## Recommended Audit Before Training

Audit all 205242 selected targets, after a 400-example stratified calibration
(100 per export; cover languages, length, multi-turn, code, factual and creative
requests). Do not launch the full run until sampled false accepts/rejects have
been manually checked. These are proposed counts, not completed work.

1. Deterministic checks: valid target index/roles, full context, no truncation,
   no missing attachment/tool result, duplicate detection, explicit format and
   count constraints, Gemma template validation and actual token length.
2. Task-aware review of the selected target in context: correctness,
   instruction following, unsupported premise acceptance, unsupported claims
   about actions/identity/internal mechanics, language fluency, usefulness,
   and whether evidence is sufficient to judge. Fictional premises and explicit
   hypotheticals are not factual hallucinations. A short correct direct answer
   must not fail for lacking a derivation.
3. Dispositions: `keep`, `repair`, `reject`, `needs_verification`. Unknown is not
   correct or false. Give issue spans, severity, evidence and confidence rather
   than only an overall numeric score. Hide winner/model labels from the judge
   to reduce authority/preference bias.
4. Verify code/math/constraints with deterministic tools where possible. Use
   retrieved primary evidence for obscure or time-dependent facts. An LLM-only
   audit is triage, not factual certification. Run untrusted code only in an
   isolated environment without credentials or network access.
5. Repair only when the instruction and supporting evidence are sufficient.
   Keep the original target, repaired target, issue list and source hash.
   Independently re-audit repairs and sample clean accepts as well as rejects.
   Do not rewrite everything into a single teacher style. When earlier context
   is false, the final answer should explicitly correct it; rewriting the whole
   branch creates a separately labeled synthetic conversation.
6. Store source/row/target/content-hash keys, rubric/model versions, evidence,
   attempts and terminal verdicts. One owner per shard, atomic completion and a
   deterministic merge prevent races. Infrastructure/schema failures are not
   semantic rejections and must remain visible for retry.

The existing DFM10 audit taught us not to score an intermediate tool call as
an incomplete final answer. Preserve that lesson when sharing this rubric
with tool-use datasets. Start with a capable, calibrated reviewer; compare
cheaper reviewers on the same held-out calibration before choosing by cost.

Published exports should remain reproducible raw preference-selected inputs.
Produce an explicitly audited derivative/revision with a repair ledger, then
point DFM13 assembly to it after validation. Do not silently mutate current
uploads, voting labels, training mixtures or sampling rules.

## RepoChat: Synthetic Calls Are Possible, Guessed History Is Not Needed

Two practical approaches are available:

- **Cheaper synthetic tool-response consumption:** parse the provided file blocks
  into a read-only snapshot and expose `read_files(paths)` with actual stored
  contents. Supply available file names in the user-visible context, execute a
  valid call, record its exact output and have a teacher answer the original
  query from that output. This teaches tool syntax and evidence use. Mark the
  call as reconstructed/synthetic, never as an observed original action. Merely
  wrapping all oracle-selected files in a call teaches little search selection.
- **Stronger retrieval behavior:** create a pinned repository snapshot, expose
  `list_files`, `search_code` and `read_file`, and collect fresh teacher rollouts.
  The agent sees the question and repository tools, not the old answer or the
  oracle file list. Execute every call; regenerate the final answer. Check that
  cited symbols exist and that claimed behavior is supported; test patches in
  isolation. Preserve snapshot hashes, licenses and retrieval budgets.

An embedded-file snapshot need not equal the whole historical repository. It
is still a valid *new* environment if its limitations are explicit. Redaction,
missing files and unavailable revisions can make a row unsuitable. Do not
silently fetch a modern repository and pretend it was the historical input.
If retaining an old answer, re-verify it against the exact available evidence.

Both approaches render OpenAI-shaped tool definitions/calls/results through
our Gemma4 native template and supervise valid assistant calls plus the final
answer, not tool-result tokens. Pilot around 100 tasks before scaling. These
are proposals; no generated calls or GPU jobs were started here.

## SearchArena: A Complement To DeepDive

Our existing DeepDive addition contains 858 successful SFT trajectories with
actual search calls/results, yielding 9070 assistant targets in the documented
conversion. SearchArena contains more natural user requests, but its public
traces generally provide citation URLs instead of actual retrieval actions
and results. Adding plausible calls around an old answer is not equivalent.

Proposed augmentation:

1. Deduplicate and screen prompts for missing uploads/context, stale dates,
   privacy and suitability for retrieval. Preserve complete needed dialogue.
2. Classify answerability: timeless QA, explicitly time-anchored QA, current
   questions, multi-source synthesis, and non-search requests. Do not force
   needless searches. Retain original dates for historically anchored tasks;
   inaccessible historical evidence means exclusion or an explicitly new task.
3. Provide real `search` and `open_page` tools. Execute calls and save query,
   ranked result snippets, page text, URLs, retrieval timestamps and hashes.
   Untrusted page text stays data, never system instructions. Restrict fetches
   to public destinations; block private addresses and unsafe redirects.
4. Have the teacher solve from the question and tools, without seeing the old
   preferred answer. Old citation URLs may seed an offline evidence cache or a
   separately labeled evidence-conditioned variant, not serve as hidden oracle
   actions in a supposedly autonomous rollout.
5. Independently verify answer claims against saved passages, citation
   entailment, instruction compliance, and whether each tool step is useful.
   Keep real recovery from weak results where it occurred. Do not manufacture
   extra hops or fabricated tool failures to look like deep research.
6. Render accepted trajectories in native Gemma4 form. Retain larger raw
   contexts and separately enforce the training window without orphaning calls
   or discarding required evidence. Deduplicate by prompt/document family and
   hold out those families together to avoid leakage.

Start with 300-500 real rollouts across task types; evaluate answer groundedness,
tool validity, search efficiency and held-out downstream performance before
scaling. Multi-hop difficulty can be added by constructing new questions from
several verified documents, but these are new synthetic tasks, not original
Arena questions. An augmented SearchArena could be as valuable for practical
search and synthesis, but matching DeepDive's deep-search reasoning value is
an empirical claim, not something a schema conversion guarantees.

[DeepDive card](https://huggingface.co/datasets/zai-org/DeepDive) describes its
QA and successful-trajectory splits. The local integration is recorded in
`wiki/pages/dfm10-plan.md` and `wiki/pages/dfm10-final-source-reconciliation.md`.

## Additional PDF

`docs/reports/multilingual_epoch10_2950k.pdf` was generated with the unchanged
`scripts/multilingual_family_report.py` and new manifest
`config/multilingual_family_report_epoch10_2950k.json`. Eight pages each contain
a family table and change bar chart. Reading comprehension is omitted because
only 10 languages have complete matched task populations, below the original
18-language threshold. No missing values were filled with zeros or older scores.
