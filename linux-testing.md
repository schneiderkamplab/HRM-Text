# PrefixLM Linux testing and CI hand-off

Updated 2026-09-18. Run from the repository root using Bash.

Linux execution results and the causal-mask performance fix are recorded in
[native/mimir/LINUX-TESTING-REPORT.md](native/mimir/LINUX-TESTING-REPORT.md).
The historical Mac-only status below is superseded by that report; unresolved
numerical and sanitizer findings remain explicit. For current source identity use
[linux-source-manifest.json](native/mimir/linux-source-manifest.json).
This is an execution plan, not a claim that Linux/CUDA tests have run.
The current development host is macOS. CUDA exists in llama.cpp; this PrefixLM
extension has not yet been qualified on it. On a Linux machine with a supported
NVIDIA GPU, driver and toolkit, run **both CPU and CUDA**, not just whichever
backend is fastest. Record unavailable hardware/tooling as untested, never passed.

## Objective and source identity

Qualify grammar/reasoning/backend sampler persistence, OpenAI parser continuation,
exact complete-prefix caching and the current working-tree implementation of control vectors, saved boundary
logits/samplers, server restart/resumption, mixed phases, shared input ownership,
dependency-safe bounded copies and shared physical KV capacity. Read [DECODER-RESUMPTION.md](native/mimir/DECODER-RESUMPTION.md), then [PERSISTENCE.md](native/mimir/PERSISTENCE.md), [SHARING.md](native/mimir/SHARING.md), [RESUMPTION.md](native/mimir/RESUMPTION.md) and the
[library contract](llama.cpp/docs/development/prefix-lm.md) first.

## Committed checkout for Linux

The parent uses `codex/prefixlm-linux-testing`; the Linux fix in llama.cpp is on
`codex/linux-causal-mask-fix` above the received feature stack.
The received Linux hand-off pinned llama.cpp commit `6f60f7472fead8da5289e06c9d79b47dd4763043`.
The current gitlink adds the Linux portability/performance fix. The original four commits separate
ggml, text codec, PrefixLM and generic persistence; see
[linux-handoff.json](native/mimir/linux-handoff.json) for exact identities.
Historical patches are reference artifacts, not steps to apply to this checkout.

After the testing branches have been published, obtain the source with:

```bash
git clone --branch codex/prefixlm-linux-testing https://github.com/schneiderkamplab/HRM-Text.git
cd HRM-Text
git submodule update --init llama.cpp mimir
git -C llama.cpp rev-parse HEAD
```

Use the recorded submodule commit, not a moving upstream branch. Do not transfer
Mac build directories or its virtual environment. Model weights and generated
fixtures are prepared below; they are not included in Git. The current source manifest is
`native/mimir/linux-source-manifest.json`; `decoder-results.json` preserves the
received Mac source and historical evidence. Final PR packaging/review remains after Linux
qualification.

Before modifying anything on Linux, verify its implementation hashes:

```bash
python3 - <<'PY'
from pathlib import Path
import hashlib, json
r = json.loads(Path('native/mimir/linux-source-manifest.json').read_text())
for name, expected in r['source_sha256'].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, name
print('Recorded implementation hashes match')
PY
```

Record the received source snapshot, not just the base commit. Preserve parent and
submodule status/diffs plus hashes of untracked source files. Fixes made during
qualification require a new source manifest and rerunning affected tests.

## Current scope and local reference results

Use [DECODER-RESUMPTION.md](native/mimir/DECODER-RESUMPTION.md) and
[LINUX-TESTING-REPORT.md](native/mimir/LINUX-TESTING-REPORT.md) for current Linux evidence/source identity;
[decoder-results.json](native/mimir/decoder-results.json) retains the Mac evidence.
The table below is the preceding ownership baseline, retained for context; use its source
manifest only for that historical revision. Use [SHARING.md](native/mimir/SHARING.md) as the current ownership/copy
contract. RESUMPTION.md records the preceding implementation; its single-owner and
full-sequence-only restrictions are superseded.

| Latest local evidence | Result to use as context, not a Linux pass |
| --- | --- |
| macOS release, CPU + Metal | 7/7 CTests; 4,264 engine assertions across HRM/Llama |
| macOS CPU UBSan | 7/7 CTests; 2,132 engine assertions |
| Q8 server, separate/unified plus restart/remapping | 104/104 checks |
| Independent CPU / CPU UBSan oracle | 31/31 steps each |
| Independent fused / unfused Metal oracle | 28/31 and 29/31; prior numerical failures unchanged |

The two new `shared-owners` oracle steps pass on both Metal modes. They must also
pass on Linux CPU and CUDA; previous Metal deviations are not permission to ignore
new CUDA failures. Latest server counts exclude the earlier extra fixed-control run;
the Linux matrix below still requests fixed-control qualification explicitly.

### Separate feature qualification

There are two logical feature patches: PrefixLM and generic generation persistence.
The first keeps exact full-prefix caching, custom-state parity and live child forks;
the second owns sampler snapshots and retained server generations. Apply the
[review drafts](native/mimir/patches/review-drafts/README.md) to separate clean
checkouts of the pinned base. Build main-only, standalone persistence and combined
configurations with `LLAMA_BUILD_TESTS=ON`, CPU and CUDA where available.

- Main-only: run HRM/Llama `test-llama-archs --prefix-lm`, the independent oracle,
  ordinary controls and the HTTP harness without `--resumption`. Add a separate
  `--cache-only` harness invocation for exact-cache hits/misses. It must not link
  sampler snapshot or server generation-resumption APIs.
- Standalone persistence: run `test-chat --parser-continuation`,
  `test-reasoning-budget` and `test-backend-sampler` with **both**
  `--test host_persistence` and `--test multi_output_dist_transaction`.
  Pass `--model .../hrm-false.gguf`; run the transaction test with `--device cpu`
  and `--device gpu`. Run the ordinary-decoder HTTP/restart matrix below.
- Combined: retain the full matrix in this hand-off. The host sampler tests were
  moved out of the PrefixLM engine test, so they must now be invoked explicitly.

Current Mac evidence is 118 ordinary-decoder HTTP checks in each of the combined
and standalone builds, 182 combined PrefixLM HTTP checks, and main-only 3,880
engine checks plus 72 HTTP/cache checks. These counts do not qualify Linux/CUDA.

### Ownership and copy acceptance matrix

The existing PrefixLM architecture suite exercises these cases. Preserve that
coverage in CPU release, CPU ASan/UBSan, CUDA release and CUDA memcheck lanes.
Do not replace it with the HTTP harness: server child forks alone do not exercise
multi-owner input rows or every bounded-copy API path.

| Case | Required behavior |
| --- | --- |
| Shared complete prefix and causal answer rows, unified KV | Match independent sequence/reference logits, advance every owner and retain each owner's boundary logits; reordered owner lists remain valid. |
| Shared input at requested context capacity | Count one physical KV cell per shared row; reject the next row beyond capacity before mutation. |
| Duplicate owner, different cached history or different future prefix dependencies | Reject before mutation and preserve every existing sequence. Equal lengths alone are insufficient. |
| Full-context save/restore of shared owners | Preserve physical ownership and permit a subsequent shared answer. |
| Copy `[0, end)` containing the entire prefix | Work on separate and unified KV; destination ends at `end`; subsequent answer logits match the source continuation. |
| Copy an answer-only `[begin, end)` range | Require matching prefix boundaries and physically shared history before `begin` (unified KV); discard the destination's later suffix. |
| Copy an incomplete prefix or incompatible dependency range | Reject without changing source/destination. Empty ranges and self-copy are no-ops. |
| Copy to an earlier boundary | Invalidate unavailable boundary logits; never reuse the source's later logit row. |

Shared input rows remain unsupported with separate KV streams, matching the existing
sequential splitter restriction. Use independent rows or evaluate and copy. A
separate-stream bounded copy currently transfers the full buffer then trims metadata;
correctness support does not imply reduced transfer volume. Independently recomputed
or separately restored histories do not establish physical sharing. Do not weaken
these admission rules to make an unsupported combination pass.

### Persistence and cache acceptance matrix

These are now implemented targets, superseding the earlier proposed-only list:

- Grammar stacks, partial UTF-8 and lazy trigger state; reasoning phase, delimiter
  matchers, remaining budget and forced-token position. Restore validates configuration.
- Graph-bound backend RNG/history restore, including speculative draw rollback and
  malformed-snapshot rejection. Run the existing `multi_output_dist_transaction` test
  explicitly on CPU and GPU; a missing backend must fail, not silently pass as CPU.
- Native, OpenAI Chat and Responses continuation, including saved parser text,
  reasoning/tool splits, stable tool IDs, fresh-process restore and destination remap.
  Nonstream OpenAI messages are cumulative; streaming emits continuation deltas.
- Exact full-prefix cache cold/hit/miss behavior, fresh sampling RNG and raw boundary
  probabilities. Cache-enabled requests use host sampling consistently; n>1 takes
  the existing normal prefill/fork path. Changed/extended prefixes must miss.

The HTTP harness `--resumption` writes `extended-reference.json` beside its output.
Preserve it for the subsequent `--resume-only` invocation on the restarted server,
using the same output directory and slot-save directory. The fixture includes grammar,
reasoning, backend, Chat and Responses saved generations in addition to native state.
Always use Mimir's checkpoint chat template for real-model inputs.

Arbitrary user-owned serialization and retained parent/child scheduler groups are not
provided by ordinary encoder/decoder slot persistence either. Existing clone/copy and
live child forks remain available; do not count absent generic group serialization as
a PrefixLM regression. Device-resident/partial-only snapshots, speculation, multimodal
and additional memory architectures still require separate qualification.

## Environment and fixtures

Use Python 3.12, CMake >=3.20, Ninja, a C/C++17 toolchain, Git and ordinary Linux
build dependencies. Install these through the machine's normal provisioning path.
For CUDA, use the installed toolkit's supported host compiler. Inspect the pinned
source's [build instructions](llama.cpp/docs/build.md) for platform requirements.
Reserve a GPU; do not contend with training or other benchmark jobs.

```bash
set -euo pipefail
export TEST_ROOT="$PWD/logs/linux-prefixlm"
export TEST_JOBS=4
mkdir -p "$TEST_ROOT"
uname -a > "$TEST_ROOT/uname.txt"
lscpu > "$TEST_ROOT/lscpu.txt"
cmake --version > "$TEST_ROOT/cmake-version.txt"
c++ --version > "$TEST_ROOT/compiler-version.txt"
git status --short > "$TEST_ROOT/root-status.txt"
git -C llama.cpp status --short > "$TEST_ROOT/llama-status.txt"
git -C llama.cpp diff --binary > "$TEST_ROOT/llama-tracked.diff"
python3.12 -m venv "$TEST_ROOT/venv"
export TEST_PY="$TEST_ROOT/venv/bin/python"
"$TEST_PY" -m pip install -r scripts/prefixlm_comparison/requirements.lock
"$TEST_PY" -m pip freeze > "$TEST_ROOT/python-freeze.txt"
export PYTHONPATH="$PWD/llama.cpp/gguf-py${PYTHONPATH:+:$PYTHONPATH}"
"$TEST_PY" scripts/prefixlm_comparison/fixture.py --output logs/prefixlm-comparison/fixture
"$TEST_PY" native/mimir/tests/long_reference.py --model logs/prefixlm-comparison/fixture/hf --output logs/mimir-runtime/long-fixture
"$TEST_PY" native/mimir/tests/prepare_text_ci.py
"$TEST_PY" llama.cpp/scripts/prefix-lm-reference.py --output "$TEST_ROOT/reference"
```

The lock pins Transformers to `ff2421c67f35cc83a0fbabbc2633c96734685918`.
If a pinned wheel/revision cannot be installed on Linux, report that dependency
blocker; do not silently upgrade and compare results as if the environment matched.
The tiny oracle is generated locally with a fixed seed, records versions/hashes,
and does not require Mimir weights. Text CI downloads only the pinned tokenizer.
`prepare_text_ci.py --source <local-checkpoint>` avoids that download when available.

Create backend-specific specifications without changing the tolerance:

```bash
"$TEST_PY" - <<'PY'
import json, os
from pathlib import Path
r = Path(os.environ['TEST_ROOT'])
spec = json.loads((r/'reference/reference.json').read_text())
assert sum(len(c['steps']) for c in spec['cases']) == 31, 'Unexpected oracle revision'
shared = next(c for c in spec['cases'] if c['name'] == 'shared-owners')
assert shared['kv_unified'] and len(shared['steps']) == 2
assert all(step['owners'] == [0, 1] for step in shared['steps'])
for name, layers, flash in [('cpu', 0, False), ('san', 0, False),
                            ('cuda-off', 999, False), ('cuda-on', 999, True)]:
    case = spec | {'n_gpu_layers': layers, 'flash': flash,
                   'report': str(r/f'reference-{name}-result.json')}
    (r/f'reference-{name}.json').write_text(json.dumps(case, indent=2))
PY
```

## CPU release and ASan/UBSan

Build separate release and instrumented trees. C/C++ sanitizer flags must be used
at both compilation and linking. CUDA is deliberately off in the CPU lane.

```bash
for mode in cpu san; do
    flags=()
    build_type=Release
    if [ "$mode" = san ]; then
        build_type=RelWithDebInfo
        flags+=("-DCMAKE_C_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer")
        flags+=("-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer")
        flags+=("-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined")
        flags+=("-DCMAKE_SHARED_LINKER_FLAGS=-fsanitize=address,undefined")
    fi
    cmake -S llama.cpp -B "$TEST_ROOT/$mode" -G Ninja \
      -DCMAKE_BUILD_TYPE="$build_type" -DGGML_NATIVE=OFF -DGGML_BLAS=OFF \
      -DGGML_CUDA=OFF -DGGML_METAL=OFF -DLLAMA_BUILD_TESTS=ON "${flags[@]}"
    cmake --build "$TEST_ROOT/$mode" --target test-llama-archs test-backend-sampler test-reasoning-budget test-chat llama-server llama-bench llama-quantize -j "$TEST_JOBS"
    cmake -S native/mimir -B "$TEST_ROOT/native-$mode" -G Ninja \
      -DCMAKE_BUILD_TYPE="$build_type" -DGGML_CUDA=OFF -DGGML_METAL=OFF \
      -DGGML_BLAS=OFF "${flags[@]}"
    cmake --build "$TEST_ROOT/native-$mode" -j "$TEST_JOBS"
done

export ASAN_OPTIONS=halt_on_error=1:detect_leaks=1
export UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1
for mode in cpu san; do
    ctest --test-dir "$TEST_ROOT/native-$mode" --output-on-failure 2>&1 | tee "$TEST_ROOT/ctest-$mode.log"
    "$TEST_ROOT/$mode/bin/test-chat" --parser-continuation > "$TEST_ROOT/parser-$mode.log" 2>&1
    "$TEST_ROOT/$mode/bin/test-backend-sampler" --device cpu \
      --model logs/prefixlm-comparison/fixture/hrm-false.gguf --test multi_output_dist_transaction \
      > "$TEST_ROOT/backend-sampler-$mode.log" 2>&1
    for arch in hrm_text llama; do
        "$TEST_ROOT/$mode/bin/test-llama-archs" -a "$arch" -s 42 > "$TEST_ROOT/ordinary-$mode-$arch.log" 2>&1
    done
    "$TEST_ROOT/$mode/bin/test-llama-archs" --prefix-reference "$TEST_ROOT/reference-$mode.json" > "$TEST_ROOT/oracle-$mode.log" 2>&1
    "$TEST_PY" native/mimir/tests/run_matrix.py --build "$TEST_ROOT/native-$mode" --output "$TEST_ROOT/matrix-$mode"
    "$TEST_PY" native/mimir/tests/text_parity.py --client "$TEST_ROOT/native-$mode/bin/mimir-chat" \
      --model logs/mimir-text-ci/vocab.gguf --reference logs/mimir-text-ci/reference.json \
      --output "$TEST_ROOT/text-$mode.json"
done
```

Expected bounded CPU integration suite: eight CTests (including reasoning persistence), including HRM/Llama PrefixLM
checks (currently 970 assertions per architecture with CPU only), text/template and
session tests. The independent oracle has 31 steps at maximum absolute error `1e-4`.
Assertion counts are a diagnostic, not a substitute for checking device logs and
exit status. Stop and preserve failures; after investigation, execute remaining
independent lanes as separate invocations so one failure does not erase coverage.
Do not treat a sanitizer startup failure as a successful application test.

ASan detects memory errors such as out-of-bounds access and use-after-free; UBSan
checks undefined operations such as invalid shifts, alignment and signed overflow.
These are runtime instruments, not exhaustive proofs and not numerical tolerances.
See [Clang ASan](https://clang.llvm.org/docs/AddressSanitizer.html) and
[Clang UBSan](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html).

## CUDA release and device-memory checks

Check `nvidia-smi` and `nvcc --version`; save their output. A CUDA build alone is
not proof of GPU execution. If either prerequisites or compatible hardware are
missing, complete the CPU lanes and mark CUDA untested with the reason.
Choose the allocated physical GPU ID below; do not assume GPU 0 is free.

```bash
export CUDA_VISIBLE_DEVICES="${TEST_GPU_ID:?Set TEST_GPU_ID to the allocated GPU ID}"
nvidia-smi -q > "$TEST_ROOT/nvidia-smi.txt"
nvcc --version > "$TEST_ROOT/nvcc-version.txt"
cmake -S llama.cpp -B "$TEST_ROOT/cuda" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=OFF -DGGML_BLAS=OFF \
  -DGGML_CUDA=ON -DGGML_METAL=OFF -DLLAMA_BUILD_TESTS=ON \
  -DCMAKE_CUDA_ARCHITECTURES=native
cmake --build "$TEST_ROOT/cuda" --target test-llama-archs test-backend-sampler test-reasoning-budget test-chat llama-server llama-bench llama-quantize -j "$TEST_JOBS"
ctest --test-dir "$TEST_ROOT/cuda" -R '^test-prefix-lm-' --output-on-failure 2>&1 | tee "$TEST_ROOT/ctest-cuda.log"
"$TEST_ROOT/cuda/bin/test-backend-sampler" --device gpu \
  --model logs/prefixlm-comparison/fixture/hrm-false.gguf --test multi_output_dist_transaction \
  > "$TEST_ROOT/backend-sampler-cuda.log" 2>&1
compute-sanitizer --tool memcheck --error-exitcode 1 \
  "$TEST_ROOT/cuda/bin/test-backend-sampler" --device gpu \
  --model logs/prefixlm-comparison/fixture/hrm-false.gguf --test multi_output_dist_transaction \
  > "$TEST_ROOT/backend-sampler-cuda-memcheck.log" 2>&1
for arch in hrm_text llama; do
    "$TEST_ROOT/cuda/bin/test-llama-archs" -a "$arch" -s 42 > "$TEST_ROOT/ordinary-cuda-$arch.log" 2>&1
done
for flash in off on; do
    "$TEST_ROOT/cuda/bin/test-llama-archs" --prefix-reference "$TEST_ROOT/reference-cuda-$flash.json" > "$TEST_ROOT/oracle-cuda-$flash.log" 2>&1
done
```

`CMAKE_CUDA_ARCHITECTURES=native` requires CMake >=3.24; with an older CMake,
set the explicit compute capability supported by the installed toolkit instead.
The PrefixLM architecture suite enumerates CPU plus every visible GPU and tests
flash on/off and split/unified memory, including shared ownership and bounded copies.
With one GPU, the current expected count is 1,940 assertions per architecture
(4,280 across HRM/Llama); with CPU only it is 1,070 per architecture. Counts may
change with a documented source revision. Confirm CUDA device identification, offloaded layers, actual
attention implementation and GPU activity in logs; a CPU fallback is not a CUDA pass.
The legacy native `run_matrix.py` has only CPU/Metal device choices: do not use its
`--metal` flag to claim CUDA coverage. Use the generic engine reader and stock server.

On an installed Compute Sanitizer toolkit, run the bounded engine suites under
memcheck. ASan/UBSan do not instrument CUDA kernel memory accesses.

```bash
for arch in hrm_text llama; do
    compute-sanitizer --tool memcheck --error-exitcode 99 \
      "$TEST_ROOT/cuda/bin/test-llama-archs" --prefix-lm -a "$arch" -s 42 \
      > "$TEST_ROOT/cuda-memcheck-$arch.log" 2>&1
done
```

If failures implicate shared memory or synchronization, add targeted `racecheck`
and `synccheck` runs. These GPU checks are distinct from CPU thread-race detection.
Record toolkit limitations rather than suppressing errors to make CI green.
[NVIDIA Compute Sanitizer documentation](https://docs.nvidia.com/compute-sanitizer/ComputeSanitizer/index.html).

## Real Mimir server: CPU and CUDA, restart and quantization

Transfer or regenerate the corrected GGUFs and pinned references:

- `logs/mimir-review/mimir-bf16.gguf`, `mimir-q8_0.gguf`, `mimir-q4_k_m.gguf`;
- `logs/mimir-chat/chat-reference.json` and `logs/prefixlm-comparison/real/prompts.json`;
- optional integration fixtures `logs/mimir-state/zero-lora.gguf` and
  `logs/mimir-resumption/zero-control.gguf`.

Record SHA-256 for every input. Do not use the old incorrectly tokenized
`logs/prefixlm-comparison/real/mimir-f32.gguf`. To regenerate weights, download the
BF16 checkpoint `danish-foundation-models/DFM-Mimir` at
`2844f0178e695d7d9ce182cb660671fd34c76ce5`, convert with this working-tree converter
using `--outtype bf16`, then use the built `llama-quantize` for `Q8_0` and `Q4_K_M`.
Use its tokenizer/chat template, including special-token parsing. Never test chats
with raw untemplated text. Synthetic engine fixtures are not chat experiments.

Use an unused port and a new save directory per backend/layout/model combination.
For example, the following is one CUDA/Q8/unified configuration. CPU uses the CPU
or sanitizer binary, `-ngl 0`, and `-fa off`. Do not use Metal in Linux commands.

```bash
mkdir -p "$TEST_ROOT/server-cuda-q8-unified"
"$TEST_ROOT/cuda/bin/llama-server" \
  -m logs/mimir-review/mimir-q8_0.gguf -ngl 999 -fa on \
  -c 512 -b 224 -ub 224 -np 2 --kv-unified \
  --host 127.0.0.1 --port 18181 \
  --slot-save-path "$TEST_ROOT/server-cuda-q8-unified" \
  > "$TEST_ROOT/server-cuda-q8-unified/server.log" 2>&1 &
TEST_SERVER_PID=$!
trap 'kill "$TEST_SERVER_PID" 2>/dev/null || true' EXIT
"$TEST_PY" native/mimir/tests/server_e2e.py --parallel --resumption \
  --url http://127.0.0.1:18181 --output "$TEST_ROOT/server-cuda-q8-unified/result.json"
kill "$TEST_SERVER_PID"
wait "$TEST_SERVER_PID" || true
trap - EXIT
```

Restart with **the identical command and save directory**, preserving the first
server log under a different filename, and run the harness with `--resume-only`
instead of `--resumption`. It restores into another slot ID and compares stochastic
continuation. Stop only the PID started by the test. The harness waits for readiness.
Never reuse a checkpoint across incompatible backend/KV layouts to establish parity.

For **ordinary decoder** qualification, repeat Q8 separate/unified release and
unified sanitizer runs with `--attention causal --cache-idle-slots --cache-ram 64`
on the combined server and add `--decoder` to both the initial `--resumption`
and fresh-process `--resume-only` harness calls. Use a new save directory per lane.
The standalone persistence server uses the baseline causal default and has no
`--attention` flag; omit only that flag there. Keep Mimir's real chat template.
These runs cover 45 initial + 14 restart checks per layout, including legacy
prompt/KV files, pending-token accounting and OpenAI parser continuation. Record
this as HRMText in ordinary causal mode, not qualification of every architecture.

Bounded matrix:

| Lane | Weights / layout | Required checks |
| --- | --- | --- |
| CPU release | Q8; separate and unified | Full harness + fresh-process restore each |
| CPU ASan/UBSan | Q8; unified | Full harness + fresh-process restore |
| CUDA release | Q8; separate and unified | Full harness + fresh-process restore each |
| CPU and CUDA release | BF16, Q4_K_M; unified | Template/greedy/lifecycle plus resumption parity, within each configuration |
| CUDA flash disabled | Q8; unified | One additional full harness run |
| CPU and CUDA release | Q8 + zero LoRA/vector; unified | One harness run with `--fixed-lora --resumption`; add `--lora` and `--control-vector` to server |

Nonzero vector/LoRA effects already have generic engine tests. Zero fixtures establish
server loading/signature integration, not adaptation quality. Compare interrupted and
uninterrupted stochastic runs within the same precision/backend; exact sampled output
across CPU/GPU or quantizations is not guaranteed. Keep existing HF comparisons in the
harness: any failure requires inspection, not deletion. If the CPU real-model lane is
slow, extend its timeout rather than silently skipping it or offloading to GPU.

For logit/NLL evidence, the existing four-case qualification references can be reused
with the generic reader on CPU and CUDA. Set `model`, `n_gpu_layers`, `flash`, `report`
and reference paths explicitly. `qualification.py evaluate/benchmark` contains
Mac-specific assumptions (including backend selection); do not run it unchanged and
label the result CUDA qualification. BF16/Q8/Q4 deviations from an FP32 oracle need
separate quantization analysis; `1e-4` is the tiny F32 semantic test, not a blanket
quantized-model acceptance threshold.

## Controlled performance testing

This measures the patch's cost, separately from correctness. Run **release binaries
only**, outside sanitizer instrumentation and on otherwise idle reserved resources.
Hold model bytes, compiler, build flags, CPU affinity/thread count, GPU, driver,
CUDA graphs, flash mode, KV precision, context/batch sizes and workloads constant.
Record memory usage and raw timing samples, not just a tokens/second headline.

Use a pristine worktree at the base revision for causal/bidirectional controls and
the received current tree for the candidate. Create/build a separate baseline tree
without resetting the candidate. If a required baseline build fix is necessary,
apply the identical fix to both trees and record it; do not add PrefixLM to baseline.
The current generic PrefixLM APIs have no pristine-base equivalent.

1. Generate identical synthetic HRM GGUFs with `hrm_text.attention.causal` set to
   true and false; ensure they do not default to PrefixLM. Both binaries consume the
   exact same files. The prior fixture was generated by ordinary `test-llama-archs`
   export; inspect its `--help`/`-o` output and preserve the model hashes.
2. For each backend (CPU `-ngl 0`, CUDA `-ngl 999`), measure causal prefill and
   generation, and bidirectional prefill. Use baseline/candidate/candidate/baseline
   order, at least 25 samples per invocation, discard the first five consistently.
   Keep flash and all other switches identical between binaries.
3. A representative invocation is `llama-bench -m <control.gguf> -ngl <layers>
   -t 4 -p 256 -n 16 -b 256 -ub 256 -r 25 -o json`; for bidirectional prefill use
   `-n 0`. Retain raw `samples_ns` and command lines. Synthetic random tokens here
   are engine controls, not chats. Repeat an entire ABBA block only if drift or a
   suspected regression needs resolution. Report medians, spread and per-round
   behavior; do not hide the first baseline's drift by pooling everything.
4. Separately time real **templated** PrefixLM requests on BF16/Q8/Q4: short and
   near-limit prompts, split/unified KV, and one mixed workload. Record prefill,
   decode, latency, peak RAM/VRAM, retained-logit memory and save/load time. These
   are candidate capability measurements, not a claim of parity with nonexistent
   baseline PrefixLM. To isolate a new feature's incremental cost, compare against
   an identified earlier PrefixLM implementation under the same protocol.
5. For the ownership/copy extension, record physical KV occupancy and peak memory
   for shared rows versus independent rows. Measure bounded-copy latency/transfer
   behavior on both layouts and shared-answer admission overhead as retained context
   grows. Separate-stream bounded copies still transfer full buffers; report that
   behavior rather than promising a partial-transfer speedup. Use a small fixed set
   of context lengths and owner counts, with the same logits requested in each variant.
6. A repeatable slowdown that exceeds run-to-run noise requires profiling or an
   explicitly justified tradeoff. No universal percentage threshold is currently
   approved. A noisy result is inconclusive, not a pass. The earlier Mac causal
   decode aggregate was +11.6%, but baseline drift prevented attributing it to code.

`native/mimir/tests/qualification.py controls` shows the earlier protocol, but its
model/baseline paths and CPU-only selection are hard-coded. Adapt those paths and
backend switches explicitly or invoke both bench binaries directly as above.
Do not let hosted CI runner timing decide performance acceptance.

## CI hand-off

The [workflow](.github/workflows/mimir-runtime.yml) now has CPU release/sanitizer
lanes, a graph-bound sampler persistence check and an explicitly requested trusted
self-hosted CUDA lane with Compute Sanitizer. It verifies the current source manifest
instead of applying stale patches. The committed submodule now reproduces that
manifest. Passing this preflight establishes source identity, not a successful
GitHub CI or Linux run. Linux qualification still comes before final patch
packaging and review. The real-model HTTP/restart matrix remains required beyond
the small generated-fixture CI lanes.

Required CI job design:

| Job | Runner | Scope |
| --- | --- | --- |
| `cpu-release` | Linux hosted runner | Generated fixtures, eight integration tests, parser/backend persistence, 31-step oracle, ordinary controls, text parity |
| `cpu-sanitizers` | Linux hosted runner | Same bounded suite with ASan/UBSan and fatal errors |
| `cuda-release` | Maintained NVIDIA runner | CPU+GPU engine suite including ownership/copies, 31-step CUDA oracle flash on/off, actual offload verification |
| `cuda-memcheck` | NVIDIA runner with Compute Sanitizer | Bounded HRM/Llama memcheck, fatal nonzero error exit |
| `server-qualification` | Reserved CPU/NVIDIA runner with pinned model cache | Matrix above, including process restarts and current Mimir template |
| `performance` | Dedicated stable CPU/NVIDIA hardware, manual/scheduled | ABBA controls and candidate request timings; retain raw evidence |

For a self-hosted CUDA job use your provisioned labels, e.g.
`runs-on: [self-hosted, linux, x64, cuda]`; `cuda` is a custom label, not hardware
provisioning. Do not execute untrusted fork PR code on a privileged runner. Gate this
lane to trusted revisions/manual dispatch or isolated ephemeral infrastructure.
Add concurrency/resource reservation so performance and correctness jobs do not
share a GPU at the same time.

Use `strategy.fail-fast: false` for independent matrix lanes and
`actions/upload-artifact` with `if: always()`. Upload CMake caches, compiler/toolkit
versions, source/input manifests, CTest logs, oracle JSON/logits, sanitizer logs,
server logs/results and raw benchmark samples. Preserve meaningful exit codes with
`set -o pipefail`; do not mask failures with `continue-on-error`. The latest
checkpoint artifacts need restricted storage if testing with non-public prompts.
Routine CI needs no large weight download: keep generated-fixture lanes separate
from the cached real-model qualification lane.

## Acceptance and report back

Produce `logs/linux-prefixlm/REPORT.md` plus machine-readable results containing:

- exact source identity, environment and hardware; tested vs skipped lanes;
- test counts/exit status, CPU and actual CUDA execution, sanitizer findings;
- oracle max-absolute/RMS errors and top-token agreement by backend/flash/precision;
- BF16/Q8/Q4 template and continuation evidence; save/restart/remap results;
- ownership/copy acceptance matrix results by backend/layout, including atomic rejection
  and shared physical capacity; retain the two `shared-owners` oracle rows explicitly;
- baseline/candidate timings and uncertainty, with raw sample links;
- every unresolved failure and an explicit recommendation on PR readiness.

Do not relax numerical tolerance just to turn a result green. Current Mac F32
weights/F32 KV oracle findings are in RESUMPTION.md: mixed-phase Metal max error
~6.88e-4–7.23e-4; same-shaped causal ~7.29e-4–7.40e-4; previous fused causal miss
1.0558963e-4 against 1e-4. All relevant top choices matched. CUDA results may differ
and must be measured. Storage/output FP32 is not proof of all-FP32 internal arithmetic.

Sanitizer and performance tests **do not have to wait for Linux testing**: they are
parts of that testing and can run independently on separate resources. They can also
run on macOS; UBSan already did. Linux is needed for Linux-specific coverage, CUDA,
and a usable ASan run after the Mac startup blocker. A quieter Linux machine is useful
for performance control, but Linux itself does not guarantee stable timings.
**Packaging and final PR readiness**, rather than the tests themselves, wait for this
evidence, following the agreed order. Source inspection and documentation can proceed
now. This hand-off does not itself establish that all remaining PR gates are satisfied.
