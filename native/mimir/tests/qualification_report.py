"""Render the bounded qualification evidence as Markdown without hiding failed gates."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics

import numpy as np

__all__ = []


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('logs/mimir-qualification'))
    parser.add_argument('--output', type=Path, default=Path('native/mimir/QUALIFICATION.md'))
    args = parser.parse_args()
    root = args.input.resolve()
    cases = json.loads((root / 'cases.json').read_text())
    text = ['# PrefixLM bounded qualification — 2026-09-17', '',
        'Status: Apple qualification evidence collected; Linux release/ASan/UBSan remains a prerequisite to packaging and review. Remind the user at that hold point. No patch packaging or PR review was performed in this round.', '',
        '## Method and scope', '',
        'Apple M2 Max, 96 GB unified memory, macOS 26.4.1. Pinned llama.cpp base: `c9a5eeeb34ab8f794ea7510ca52d25da13728a5b`; local PrefixLM implementation is the rollback snapshot described in `followup-results.json`. Core code was unchanged for this experiment.', '',
        'Reference: `danish-foundation-models/DFM-Mimir` revision `2844f0178e695d7d9ce182cb660671fd34c76ce5`, loaded as F32 with eager attention. Transformers revision `ff2421c67f35cc83a0fbabbc2633c96734685918`. Every chat prefix uses that checkpoint’s tokenizer and chat template with `enable_thinking=False` and the generation header. Server-rendered tokens are checked against HF before timing.', '',
        'Four cases only. Answers are fixed teacher-forced targets, including EOS, not a quality benchmark or a claim that the model freely generates those answers. Independent HF full-forward mixed-prefix/answer attention supplies the reference. llama.cpp runs the answer both one token at a time and in a chunk. The extra final logit row after EOS checks execution consistency; answer-only NLL excludes that unused row.', '',
        '| Case | Prefix tokens | Target tokens including EOS | Coverage |', '|---|---:|---:|---|']
    coverage = ['Danish, capitalization, æ/ø/å', 'English, two-part instruction', 'Retained assistant turn and user facts', 'Retrieval across a full physical prefix batch']
    for c, description in zip(cases, coverage, strict=True):
        text.append(f"| {c['name']} | {len(c['prompt_tokens'])} | {len(c['answer_tokens'])} | {description} |")
    text += ['', 'Context: 512, prefix physical batch: 480. The long case fills that batch exactly, but this is a boundary test of the configured capacity—not a test of the model’s maximum trained context. Evaluation uses F32 KV, four CPU threads, all layers on Metal, flash attention on/off. BF16/Q8_0/Q4_K_M are fresh conversions of the same original checkpoint; F32 is the exact-weight control.', '',
        '## Numerical and conditional-likelihood results', '',
        'All vocabulary logits are compared. The old absolute threshold 0.03 is retained as a diagnostic, including failures; it is not a justified quantized-model quality gate. NLL is in nats per target token, weighted across the 40 target tokens. Top-1 agreement covers 44 positions per configuration, separately for single/chunk execution.', '',
        '| Weights / attention | HF max abs, single / chunk | Chunk–single max abs | HF top-1 matches, single / chunk | Answer NLL / HF | Strict steps passing |',
        '|---|---:|---:|---:|---:|---:|']
    rows = []
    for weight in ['f32', 'bf16', 'q8_0', 'q4_k_m']:
        for mode in ['unfused', 'flash']:
            label = f'{weight}-{mode}'
            result = json.loads((root / f'{label}.json').read_text())
            hf_nll = got_nll = count = 0
            max_single = max_chunk = max_difference = 0
            top_single = top_chunk = positions = 0
            for case in cases:
                n = len(case['prompt_tokens'])
                targets = case['answer_tokens']
                expected = np.concatenate([np.fromfile(case['reference'], np.float32)[None, :],
                    np.fromfile(case['answer_reference'], np.float32).reshape(len(targets), -1)])
                single = np.stack([np.fromfile(root / label / f"{case['name']}-single-{p}.f32", np.float32)
                                   for p in [0, *range(n, n + len(targets))]])
                chunk = np.concatenate([np.fromfile(root / label / f"{case['name']}-chunk-0.f32", np.float32)[None, :],
                    np.fromfile(root / label / f"{case['name']}-chunk-{n}.f32", np.float32).reshape(len(targets), -1)])
                assert np.isfinite(single).all() and np.isfinite(chunk).all()
                def nll(values):
                    values = values[:-1].astype(np.float64)
                    maxima = values.max(-1)
                    return float(np.sum(maxima + np.log(np.exp(values - maxima[:, None]).sum(-1))
                                        - values[np.arange(len(targets)), targets]))
                hf_nll += nll(expected)
                got_nll += nll(single)
                count += len(targets)
                max_single = max(max_single, float(np.max(np.abs(single - expected))))
                max_chunk = max(max_chunk, float(np.max(np.abs(chunk - expected))))
                max_difference = max(max_difference, float(np.max(np.abs(single - chunk))))
                top_single += int(np.sum(single.argmax(-1) == expected.argmax(-1)))
                top_chunk += int(np.sum(chunk.argmax(-1) == expected.argmax(-1)))
                positions += len(expected)
                rows.append({'configuration': label, 'case': case['name'], 'single_nll': nll(single) / len(targets),
                             'chunk_nll': nll(chunk) / len(targets), 'hf_nll': nll(expected) / len(targets)})
            passed = sum(s['pass'] for s in result['steps'])
            text.append(f'| {label} | {max_single:.6f} / {max_chunk:.6f} | {max_difference:.6f} | '
                        f'{top_single}/{positions} / {top_chunk}/{positions} | {got_nll/count:.6f} / {hf_nll/count:.6f} | {passed}/{len(result["steps"])} |')
    (root / 'conditional-likelihood.json').write_text(json.dumps(rows, indent=2) + '\n')
    text += ['', 'Interpretation: F32 passes all 104 strict steps across both attention modes. BF16 and Q8 preserve all tested top choices; Q4 changes one of 44 in both modes. BF16/Q8/Q4 exceed the old absolute-logit threshold, and those failures remain visible. Q4’s lower average target NLL on this tiny chosen set is not evidence of better general quality. Chunk/single differences also occur in exact-weight F32, so the data are consistent with numerical execution differences; they do not isolate a particular kernel as the cause.', '', '## Templated request performance and memory', '',
        'Stock llama-server, one active slot, full Metal offload, flash attention, default F16 KV, four CPU threads, context 512, batch/ubatch 480. One warmup per length is excluded, then three measured rounds; the middle round reverses length order. Formats run serially. Every request recomputes its entire prefix (`cache_n=0`). Fixed 16-token greedy continuations ignore EOS solely to measure throughput; these continuations are not quality scores. Decode rate is the server’s reported `predicted_per_second` (its timing excludes the first sampled token).', '',
        'Median [minimum–maximum] across three runs. End-to-end includes HTTP and sampling; prefill/decode are engine timings. This is a workstation measurement, not an isolated laboratory performance guarantee.', '',
        '| Weights | Prefix tokens | Prefill ms | Decode tokens/s | End-to-end s |', '|---|---:|---:|---:|---:|']
    bench = json.loads((root / 'benchmark.json').read_text())
    def interval(values):
        return f'{statistics.median(values):.2f} [{min(values):.2f}–{max(values):.2f}]'
    for weight in ['bf16', 'q8_0', 'q4_k_m']:
        for case in [cases[0], cases[2], cases[3]]:
            group = [r for r in bench if r['weight'] == weight and r['case'] == case['name'] and not r['warmup']]
            assert len(group) == 3
            repeated = [r for r in bench if r['weight'] == weight and r['case'] == case['name']]
            assert len(repeated) == 4 and len({tuple(r['tokens']) for r in repeated}) == 1
            text.append(f"| {weight} | {len(case['prompt_tokens'])} | {interval([r['timings']['prompt_ms'] for r in group])} | {interval([r['timings']['predicted_per_second'] for r in group])} | {interval([r['elapsed_s'] for r in group])} |")
    text += ['', 'All four repeated continuations (warmup included) were identical within each weight/length group. Latency still varies by several-fold in some groups; do not rank formats by these medians or claim stable production throughput. Controlled performance validation remains open.', '', '| Weights | Peak process RSS, GiB |', '|---|---:|']
    for weight in ['bf16', 'q8_0', 'q4_k_m']:
        log = (root / f'benchmark-{weight}.log').read_text()
        match = re.search(r'(\d+)\s+maximum resident set size', log)
        text.append(f'| {weight} | {int(match[1]) / 2**30:.3f} |' if match else f'| {weight} | unavailable |')
    text += ['', 'RSS is the macOS `/usr/bin/time -l` high-water mark over model loading, warmup and all request lengths. It is not a measurement of total GPU allocation or total system unified-memory pressure. Other user applications were left running; no unrelated processes were stopped.', '',
        '## Unchanged-mode performance controls', '',
        'A tiny deterministic HRM fixture (not Mimir chat) is copied with causal/bidirectional metadata. CPU-only prompt processing uses 256 tokens; causal decoding also measures 16 tokens. Baseline/patched/patched/baseline order, 25 samples per invocation, with the first five discarded consistently. Synthetic random tokens are appropriate here only because this is an engine control, not a chat experiment.', '',
        '| Mode / work | Baseline median ns | Patched median ns | Patched / baseline |', '|---|---:|---:|---:|']
    controls = json.loads((root / 'controls.json').read_text())
    control_note = ''
    for mode, work in [('causal', 'prefill'), ('causal', 'decode'), ('bidirectional', 'prefill')]:
        groups = {}
        for build in ['baseline', 'patched']:
            values = [v for run in controls if run['mode'] == mode and run['build'] == build
                      for row in run['results'] if (row['n_prompt'] > 0) == (work == 'prefill')
                      for v in row['samples_ns'][5:]]
            groups[build] = statistics.median(values)
        if mode == 'causal' and work == 'decode':
            medians = [statistics.median(row['samples_ns'][5:]) / 1e6
                       for run in controls if run['mode'] == 'causal'
                       for row in run['results'] if row['n_gen'] > 0]
            control_note = (f"The aggregate causal decode time changes by {100 * (groups['patched']/groups['baseline'] - 1):+.1f}%. "
                            f"Baseline round medians are {medians[0]:.2f} and {medians[3]:.2f} ms; patched rounds are {medians[1]:.2f} and {medians[2]:.2f} ms. ")
        text.append(f"| {mode} / {work} | {groups['baseline']:.0f} | {groups['patched']:.0f} | {groups['patched']/groups['baseline']:.3f} |")
    text += ['', control_note + 'This run does not distinguish a patch regression from time-dependent workstation effects. Repeat this bounded control on the Linux test machine before claiming no regression. These small CPU controls do not establish absence of performance regressions at production model sizes or on other backends. Raw samples and command lines remain in `controls.json`.', '',
        '## Prior regression evidence and remaining gates', '',
        '- Existing core tests: 724 CPU/Metal checks and 362 CPU UBSan checks; seven release and seven UBSan CTests passed. Existing causal and bidirectional functional controls remain covered. See `followup-results.json`.',
        '- Previous independent tiny reference: 18/18 CPU, CPU UBSan and unfused Metal; 17/18 fused Metal, retaining the unchanged causal-control difference 0.00010559 against 0.0001. No tolerance was changed here.',
        '- Previous templated chat lifecycle tests: 72 checks across BF16/Q8/Q4 and flash on/off; 23 stock-server checks, including isolation, cancellation, rejection and recovery. This round adds four varied teacher-forced cases instead of multiplying lifecycle tests.',
        '- Linux CPU release plus ASan/UBSan must run before packaging/review. Apple ASan has not supplied usable execution evidence. CUDA, other GPUs, multi-sequence scheduling and persistence are not qualified.', '',
        '## Reproduction and raw evidence', '',
        'Run from the repository root with the existing pinned Python environment and built binaries. Required local model paths and overrides are documented by `--help`. The controls phase requires the existing deterministic fixture and pristine baseline build.', '',
        '```sh',
        'PY=logs/prefixlm-comparison/venv/bin/python',
        '$PY native/mimir/tests/qualification.py prepare',
        '$PY native/mimir/tests/qualification.py evaluate',
        '$PY native/mimir/tests/qualification.py evaluate --weights f32',
        '$PY native/mimir/tests/qualification.py benchmark',
        'PYTHONPATH=llama.cpp/gguf-py $PY native/mimir/tests/qualification.py controls',
        '$PY native/mimir/tests/qualification_report.py', '```', '',
        'Raw evidence: `logs/mimir-qualification/` contains template-rendered cases, HF logits, each engine specification/report, dumped logits, likelihoods, server timings/logs, controls, and provenance. Strict failures are retained. This harness still belongs to the consuming project; moving the essential evidence into the upstream submission is part of later packaging, after Linux tests.']
    args.output.write_text('\n'.join(text) + '\n')
    files = [p for p in root.iterdir() if p.is_file() and p.suffix in ['.json', '.f32'] and p.name != 'provenance.json']
    manifest = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    manifest['report'] = hashlib.sha256(args.output.read_bytes()).hexdigest()
    (root / 'provenance.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    _main()
