# DFM11-post: review of large contributors

2026-09-08. Scope: every source family with at least 2% of the initial post mix.
Koolbardi was reviewed separately (ten full conversations per language). This
directory contains ten reproducible eligible assistant-target samples for each
of the other sixteen families, including their actual tokenized prompt and
response. These are training-target spot-checks, not a fresh automated audit,
exhaustive source validation, or verified measurements of population defect
rates. Long examples were initially screened using prompt/answer excerpts;
relevant full context was checked before classifying key failures. No sampled
code was executed, and specialist factual assertions were not independently
validated. Do not equate a keep decision with a clean bill of health.

Sampling: fixed per-family seed; file probability proportional to current
selected target count times repeat, then uniform eligible target ordinal in
that file. This approximates the epoch's target distribution, not a uniform
distribution of original conversations or token positions. Production
eligibility uses 4097 total tokens (4096 plus AR shift), minimum original
response length two, and inherited drop/truncate mode. JSON files retain
original and retained response lengths and exact task/row identities.

| Family | Initial B tokens/epoch | Decision | Sample evidence and limitations |
|---|---:|---|---|
| Koolbardi DA / EN | 2.704 / 2.611 | Approximately half the conversations | Separate 20-conversation review found fluent but overly agreeable prose, technical/factual errors and serialization debris. Select whole conversations, stratified by topic, mode, complexity and length across each language. |
| Nemotron Agentic | 4.138 | Half eligible targets; drop overlength answers | Initial draw dominated by interactive customer-service identity verification. One target was only the beginning of a sentence after context truncation. Correct native tool syntax and policy conditioning are useful, but 11.6% of the whole mix is disproportionate. |
| Nemotron Instruction Following | 1.603 | Half eligible targets | Mixed useful extraction, cooking, creative writing and math; excessive praise/verbosity, confident technical references needing verification, repeated boxed answer and inconsistent/contradictory prompt constraints. Broadly useful, not premium verified instruction supervision. |
| Scientific summaries repaired | 1.198 | Keep repeat 1 | Consistent structured-note grounding, complete responses, suitable summary synthesis. Same prompt pattern repeated, and scientific truth is not established by this check; no sufficiently strong evidence for a new cut. |
| OpenStax open chats | 1.157 | Keep repeat 1 | Short grounded tutoring across math, physiology, literature, economics and civics. Useful follow-up continuity; some jurisdictional/generalization caveats, but stronger grounding than generic synthetic advice. |
| Synthetic native tool calling repaired | 1.026 | Repeat 2 -> 1 | Seven of ten examples center on weather; others include bookings and non-tool answers. Good clarification/tool-result use, but narrow scenario diversity does not warrant double exposure. This is a sample observation, not a measured corpus topic percentage. |
| Nemotron SWE repaired | 1.021 | Anchor allocation weight x0.5 | Useful native shell/editor calls, but sample includes optimistic commentary attached after calls and heavy repository-trace context. Reduce concentration without discarding coding breadth. Not a claim that sampled patches were tested. |
| FLAN factual | 0.898 | Anchor allocation weight x0.5 | Garbled reading passage and apparently contradictory yes/no target for a passage about overcoming difficulties. Many useful QA examples remain. |
| DOLCI tool use repaired | 0.872 | Keep repeat 1 | Diverse native function calls, argument extraction, parallel calls and tool-result summaries. One nested schema has an empty type and merits later repair; does not justify a blanket source reduction from ten samples. |
| FLAN | 0.826 | Anchor allocation weight x0.5 | Mixed arbitrary labels, foreign-language translation and few-shot boilerplate; stop-sign question has inconsistent choice names and target. Some clean arithmetic/string tasks. |
| Nemotron Terminal native | 0.807 | Anchor allocation weight x0.25 | Actual targets retain literal think tags and JSON command protocols; sample includes parse-error recovery. This is not uniformly Gemma-native tool-call supervision despite the name. Retain a small code/terminal anchor until format repair. |
| Synthetic summary/rewrite controls | 0.792 | Keep repeat 2 | Useful explicit sentence counts, register shifts and grounded compression; sampled constraints generally satisfied. Some inherited technical source content warrants specialist review; rewriting fidelity does not establish source truth. |
| SYNTH | 0.739 | Anchor allocation weight x0.5 | Broad but often under-grounded assertions and ambiguous prompts (e.g. unnamed king/new laws). Useful breadth, lower confidence than grounded behavior data. |
| FineInstructions EN controlled | 0.738 | Half eligible targets | Intrinsically incomplete answers ending mid-sentence, malformed HTML/Markdown, title request answered with title plus paragraph, and a response that promises a decision framework without supplying it. These are present before sampler truncation. |
| Synthetic multi-turn DA/EN chat | 0.733 | Repeat 2 -> 1 | Good probability, topology, Laplace and correction turns mixed with questionable factual premises and exaggerated persona style. Condescending example is explicitly system-conditioned roleplay, NOT evidence of default assistant behavior. Retain diversity without doubling. |
| Natural Instructions | 0.724 | Keep repeat 1 | Broad concise instruction/classification/extraction supervision. Some ambiguous gold labels, but not enough evidence for further reduction at current weight. |
| DFM Dyna Instruct | 0.719 | Anchor allocation weight x0.5 | Mixed languages and relevance. One unbounded multivariate inequality is answered as a different bounded univariate polynomial problem; a list-rotation solution misses the empty-list case. |

## Budget mechanics

Behavior cuts reduce total size. Other good behavior sources are not increased
to restore the old 35.708B target. Broad anchors remain 33% of the FINAL mix.
Their square-root-capacity allocation additionally uses the above quality
weights, with one-pass saturation. A weight x0.5 is not a claim that exactly
half the previous anchor tokens will remain: allocation is renormalized to
the new, smaller 33% budget. Realized values belong in the completed sampling
receipt.

Koolbardi selections are fixed whole-conversation pools for this build, not
rotating conversation pools per epoch. This deliberately differs from the
earlier suggested rotating pool: it preserves all targets of selected
conversations without modifying the sampler's epoch permutation semantics.
Resampling within the selected pool still shuffles across epochs. Larger
independent review or repair should precede re-expanding exposure.

No raw sources, full DFM11 sampling policy, or running training are changed.
Overlength dropping here is specific to the Nemotron Agentic post slice.
Other known format/data defects are recorded, not silently claimed repaired.
