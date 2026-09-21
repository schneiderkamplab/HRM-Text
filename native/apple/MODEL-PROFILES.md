# Model deployment profiles

DFM Mimir v1 permits 1,024–32,768 context tokens. Its GGUF reports a training
context of 4,096, shown in settings regardless of the selected context. Longer
contexts are allowed; training length is informative, not an allocation limit.
Explicit context choices bypass memory estimates. Automatic defaults consider
1,024, 2,048, 4,096, 8,192, 16,384 and 32,768 and choose a tier using the profile's
memory policy. Large manual allocations can fail or exhaust device memory.

## Adding a compatible Mimir model

1. Copy [DFM-Mimir-v1.profile.json](Resources/DFM-Mimir-v1.profile.json), change its
   name and measured deployment parameters. All fields are required, with version 1.
2. Bundle the GGUF and profile using the optional third build argument:

   ```bash
   native/apple/build.sh macos /absolute/path/new-mimir.gguf /absolute/path/new-mimir.profile.json
   native/apple/build.sh ios /absolute/path/new-mimir.gguf /absolute/path/new-mimir.profile.json
   ```

   Direct CMake users can set `MIMIR_MODEL_PROFILE`. Omitting it uses the v1 policy.
3. Alternatively import the GGUF in the app, then use **Import model profile…** in
   settings. The JSON is validated, copied into the saved model descriptor and
   reapplied on restart. A load failure still leaves the model selectable for a
   corrected profile. Changing a profile recalculates automatic defaults.
4. Check allocation, speed and answer quality on the target devices. Update the
   bundled license/provenance when distributing different weights.

Profiles configure the following in one place (`ModelProfile.swift` supplies the
v1 defaults; the example JSON is checked against them by tests):

| Fields | Meaning |
| --- | --- |
| `minimumContext`, `maximumContext`, `contextTiers` | Allowed context range and ascending, unique automatic tiers including both endpoints |
| `minimumReply`, `maximumDefaultReply`, `replyContextDivisor` | Automatic reply budget, bounded by context minus prompt reserve |
| `promptReserve` | Minimum prompt space when validating custom reply budgets |
| `memoryFraction` | Fraction of available memory used by automatic selection |
| `fixedMemoryBytes`, `memoryBytesPerToken` | Estimated fixed and linear runtime allocation, excluding GGUF file size |
| `cpuAttentionBytesPerTokenSquared` | Additional CPU quadratic attention workspace coefficient |
| `threads` | CPU worker threads |
| `systemPrompt` | App system instruction, supplied through the model's own chat template |

Weight size comes from the selected file. Training context, tokenizer and chat
template come from GGUF; there is no duplicated training-length constant to update.
Quantizations can share a profile where their non-weight allocations are comparable,
or use separate profiles when measurements differ. Model IDs remain SHA-256 weight
identities. Profiles do not change those identities. A replacement bundled model
uses the new bundle's identity; saved profile overrides apply only to matching
weights. Switching weights resets custom limits to automatic defaults.

This configures deployment of models supported by the existing HRMText/PrefixLM
runtime. A new architecture or unsupported GGUF format still requires runtime
support; JSON cannot supply kernels. Sampling remains greedy and KV remains F16.
Those are runtime choices rather than model identity metadata.

## Evidence — 2026-09-19

Mac, unsigned iOS and Simulator Release builds pass. The Mac build exercised the
profile-file build argument. Swift tests cover 32,768 acceptance, out-of-range
rejection, a hypothetical 65,536-context profile with different memory and reply
parameters, JSON import/restart persistence, malformed policy and example/default
agreement. The real Q4_K_M Metal bridge test passes with profile-selected automatic
context and verifies the GGUF training-context result, generation, history restore,
cancellation and recovery.

No full 32,768-token generation or physical iOS memory qualification is claimed.
The earlier [8,192 allocation / 4,530 prompt execution test](CONTEXT-REPORT.md)
remains the real-model extended-position evidence. The former 8,192 automatic-tier
ceiling and manual memory-admission policy are superseded by this change.
