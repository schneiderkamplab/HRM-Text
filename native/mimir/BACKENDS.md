# Mimir backend qualification

2026-09-20. The PrefixLM implementation already builds on ggml's backend-neutral
operations. The remaining CPU/Metal-only restriction was in our Mimir model loader,
not a llama.cpp kernel whitelist. The loader now accepts every registered ggml
backend or device name. No new kernel implementations or changes to the four
llama.cpp patch scopes are needed for this selection change.

`mimir-chat --list-devices` lists compiled/available devices. `--device auto`
selects the first GPU/IGPU, otherwise CPU; `cpu` explicitly uses CPU. `metal` remains
the human-readable alias for ggml's `MTL`. Other names are case-insensitive,
including exact device identifiers such as `Vulkan0`, `CUDA0` or `SYCL0` when
reported by that build. Explicit unavailable selections fail, rather than silently
choosing CPU. Normal ggml per-operation CPU fallback remains possible: accepting a
device is not proof that every operation is accelerated.

## Evidence and limits

Pinned llama.cpp: `8f4f4ef8f3139d7d262763936f1f34e48ad46d9c`.
This Mac: Apple M2 Max, 96 GiB, macOS 27.0 (26A428), Xcode 16.3.
Model: Q4_K_M, SHA256
`3cf8906f4dd1349c965e7dd873e3995419d34bf846a657840a393c32c89849a5`.
All real chats use the GGUF's Mimir chat template.

| Backend | Status | Evidence / limitation |
| --- | --- | --- |
| CPU | Passed on this Mac | 73 native text checks |
| Metal / MTL | Passed on this Mac | 73 native text checks; shared runtime/compaction tests |
| BLAS / Accelerate | Passed on this Mac | 73 native text checks; a CPU acceleration path, not another GPU |
| Vulkan / MoltenVK | Passed on this Mac | 73 native text checks, MoltenVK 1.4.2; this does not qualify Android or Linux Vulkan drivers |
| CUDA | Previously tested on Linux B200 | [Linux report](LINUX-TESTING-REPORT.md), [qualification policy](FINAL-QUALIFICATION.md); accepted numerical differences and pending final policy-runner validation remain documented there |
| OpenCL | Build blocked on this Mac | With Khronos headers, Apple's runtime cannot link `clCreateBufferWithProperties` and `clGetKernelSubGroupInfo`; no runtime claim |
| WebGPU | Not runtime-tested | Configure requires Dawn, not installed here |
| HIP, SYCL, OpenVINO, CANN, MUSA, Hexagon, zDNN, ZenDNN, ET, VirtGPU, RPC | Untested for this Mimir integration | Selectable if registered by a suitable build; require their own dependencies, operators and hardware qualification |

These are bounded functional checks, not BF16/Q8/Q4 numerical-equivalence or
controlled-performance qualification for newly enabled backends. No claim that all
backends in llama.cpp can execute all Mimir operations is implied. The broader
existing CPU/Metal/CUDA evidence remains in the previous reports.

Raw local logs: `logs/multiplatform-{cpu,metal,vulkan,blas}.log`,
`logs/multiplatform-devices.jsonl`, `logs/multiplatform-unavailable.log`, and
`logs/multiplatform-{opencl,webgpu}-*.log`. Logs/build artifacts are not committed.

## Reproduce on this Mac

Install CMake, Vulkan loader, MoltenVK, shaderc, SPIRV headers and SPIRV tools.

```sh
cmake -S native/mimir -B logs/mimir-multiplatform \
  -DCMAKE_BUILD_TYPE=Release -DGGML_METAL=ON -DGGML_VULKAN=ON \
  -DMIMIR_BUILD_TESTS=ON
cmake --build logs/mimir-multiplatform --target mimir-chat mimir-text-tests -j6
logs/mimir-multiplatform/bin/mimir-chat --list-devices
# Run separately for cpu, metal, Vulkan0, and BLAS:
logs/mimir-multiplatform/bin/mimir-text-tests logs/mimir-review/mimir-q4_k_m.gguf cpu
```

## Additional Linux testing

Prioritize an allocated, idle GPU and compare the same model bytes and templated
inputs against CPU. Build the matching ggml option, enumerate actual device IDs,
then run `mimir-text-tests MODEL DEVICE` and the existing PrefixLM regression,
numerical and sanitizer procedures in [linux-testing.md](linux-testing.md).

1. **NVIDIA:** repeat CUDA qualification and try Vulkan on a driver supporting it.
2. **AMD:** HIP/ROCm and Vulkan on supported Radeon/Instinct hardware.
3. **Intel:** SYCL/oneAPI, Vulkan, and optionally OpenVINO on supported hardware.
4. **Any server:** CPU; BLAS with a supported library. ZenDNN needs its supported
   environment. RPC can be exercised with a local/remote backend server, but it is
   transport rather than a new accelerator and is not the offline app default.
5. **With additional SDKs:** WebGPU/Dawn, including Vulkan-backed implementations.
   OpenCL needs a compatible runtime (the ggml backend includes Adreno-specific
   paths). Android Vulkan/OpenCL/Hexagon need device-specific qualification;
   a normal x86 Linux server cannot stand in for a Snapdragon phone.
6. **Specialist hardware:** CANN (Ascend), MUSA (Moore Threads), Hexagon
   (Qualcomm), zDNN (IBM Z), ET and virtualized VirtGPU require appropriate hardware/runtime.

Test BF16, Q8_0 and Q4_K_M where supported; report unsupported format/operator
combinations explicitly. Build availability alone is never the pass criterion.
