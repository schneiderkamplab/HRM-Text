# Prepared native-thinking inventory

Confirmed DFM15 repair/addition and DFM16 decision-source inventory, 2026-10-28.
Counts are prepared training targets before sampling/repetition, not deduplicated
conversations or per-epoch exposure. Tokens include prompt, thought, final answer
and template overhead, not just reasoning tokens. Array-based counts are exact
for these identified sources. This is not a full token scan of every inherited
source or pending DFM16 expansion.

| Source | Thinking targets | Tokens |
|---|---:|---:|
| allenai/big-reasoning-traces | 419,579 | 746,817,501 |
| allenai/open_math_2_50k_r1-original | 46,041 | 56,435,385 |
| allenai/verifiable-reasoning-filtered-gpt-41 | 236,232 | 407,396,651 |
| allenai/verifiable-reasoning-filtered-o4-mini | 168,219 | 80,469,512 |
| nvidia/Nemotron-Terminal-Corpus, native repaired route | 2,049,818 | 5,839,788,317 |
| danish-foundation-models/multilingual-gsm-symbolic, English synthetic train | 3,799 | 682,844 |
| **DFM15 identified pool subtotal** | **2,923,688** | **7,131,590,210** |
| nvidia/OpenScienceReasoning-2 | 1,600,026 | 9,755,179,239 |
| AgentGym/AgentTraj-L, thinking targets only | 111,656 | 162,407,901 |
| **Combined identified pool** | **4,635,370** | **17,049,177,350** |

Qualification: DFM15 repaired arrays have `valid == 2` for enabled reasoning;
DFM16 mode-specific arrays were tokenized with `--enable-thinking`. A decoded
target from each of these eight sources confirms `<|think|>` in the prompt,
`<|channel>thought` in the response and closing `<channel|>`. This is a
representative rendering check, not a new exhaustive syntactic audit.

The Norwegian Magpie repair route has zero retained enabled-thinking targets.
Older Nemotron Agentic thought-channel targets without enabled-thinking prompts
are deliberately not counted. Direct solutions and literal XML `<think>` text
do not qualify. Pending expansion candidates, including OpenThoughts and
UltraData, are not silently added to this prepared inventory.

Length matters: OpenScience has 789,624 targets / 1,976,109,234 tokens at
strict total length <=4096. Historical sampling actually admits <=4097 and its
receipt records 789,889 / 1,977,194,939 before any new mixture changes. Do not
interpret its full 9.755B source-token pool as per-epoch training exposure.

Reproduce: `python -m scripts.report_native_thinking_inventory`.
Evidence: `data/dfm15/native-reasoning-v2/repairs.json`, per-part length/mode
arrays, `config/dfm15_sources.json`, and
`data/dfm16/decisions-v1/preparation_summary.json` with mode-specific arrays.
