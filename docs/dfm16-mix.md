# DFM15 to DFM16 sampled mix

Three epochs; unchanged inherited exposure; complete rows only (4097 token index limit).

| Measure | DFM15 | DFM16 |
|---|---:|---:|
| Mean tokens/epoch | 134,516,139,170 | 138,082,851,704 |
| Epoch-zero examples | 408,412,700 | 412,970,846 |

| New source | Repeat | Eligible examples | Tokens/epoch | Excluded long/empty examples |
|---|---:|---:|---:|---:|
| nvidia/Nemotron-RL-knowledge-mcqa | 2 | 122,198 | 76,224,098 | 1 |
| nvidia/OpenScienceReasoning-2 | 1 | 789,889 | 1,977,194,939 | 810,137 |
| Lexmount/WebJev | 1 | 29,811 | 77,741,136 | 34,311 |
| osunlp/Mind2Web | 1 | 23 | 75,406 | 7,124 |
| AgentGym/AgentTraj-L | 2 | 111,549 | 323,854,046 | 118 |
| tasksource/nli4ct | 3 | 1,700 | 2,732,094 | 0 |
| copenlu/fever_gold_evidence | 3 | 228,274 | 85,415,985 | 3 |
| LocalLLaMA/typed-decisions | 3 | 3,000 | 3,047,505 | 0 |
| ZefanCai/Open-Jev | 1 | 266,186 | 153,152,203 | 0 |
| ZefanCai/Open-Jev-v1.1 | 1 | 112,765 | 31,858,446 | 0 |
| bigcode/commitpackft | 2 | 534,735 | 549,670,862 | 1 |
| emozilla/quality | 3 | 453 | 4,242,864 | 1,444 |
| qiaojin/PubMedQA | 2 | 212,258 | 162,877,858 | 0 |
| local/executable-curriculum | 3 | 85,935 | 99,510,942 | 4,185 |
| schneiderkamplab/synth-kg-text-hetionet | 1 | 439,906 | 19,114,150 | 0 |

Source-domain categories are provenance routing labels, not semantic or language judgments.
The math/code/tool-agentic category includes the new OpenScience science-reasoning examples.

| Epoch-zero domain | DFM15 tokens | DFM16 tokens | DFM15 share | DFM16 share |
|---|---:|---:|---:|---:|
| Neutral/general knowledge/uncertain | 72,041,676,157 | 72,576,098,496 | 53.56% | 52.56% |
| Math/code/tool-agentic | 26,338,898,009 | 29,366,945,340 | 19.58% | 21.27% |
| Language/chat/summarization/translation | 36,136,056,568 | 36,140,299,432 | 26.86% | 26.17% |

All inherited rows retain their original order after filtering out the interleaved additions.
New examples are shuffled independently per epoch, with full integer repeats.
Length-excluded examples remain in the tokenized source stores for future longer-context sampling.
No comprehensive inherited-versus-new semantic overlap audit was performed.
