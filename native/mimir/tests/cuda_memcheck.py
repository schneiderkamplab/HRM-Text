#!/usr/bin/env python3
"""Run memcheck with a narrow policy for llama.cpp's handled graph-update fallback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

__all__ = []

_API = re.compile(
    r'^Program hit cudaErrorGraphExecUpdateFailure \(error 910\)(?: due to .*?)? '
    r'on CUDA API call to (cudaGraphExecUpdate|cudaGetLastError)\.?$'
)
_SUMMARY = re.compile(r'^ERROR SUMMARY: (\d+) errors?$')


def _classify(log, application_returncode, allow_graph_fallback):
    """Unknown formats fail closed; no suppression of device or unrelated API errors."""
    blocks = []
    current = []
    for line in log.splitlines():
        if not line.strip():
            continue
        if not line.startswith('========='):
            return {'pass': False, 'reason': 'unrecognized sanitizer output', 'line': line}
        text = line[len('========='):].strip()
        if not text:
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(text)
    if current:
        blocks.append(current)
    errors = []
    counts = []
    seen_banner = False
    for block in blocks:
        # Banner and summary may be adjacent in a zero-error log.
        while block and block[0] == 'COMPUTE-SANITIZER':
            seen_banner = True
            block = block[1:]
        if not block:
            continue
        if len(block) == 1 and _SUMMARY.fullmatch(block[0]):
            counts.append(int(_SUMMARY.fullmatch(block[0])[1]))
            continue
        if block == ['LEAK SUMMARY: 0 bytes leaked in 0 allocations']:
            continue
        match = _API.fullmatch(block[0])
        if not match:
            return {'pass': False, 'reason': 'unexpected sanitizer diagnostic', 'diagnostic': block[0]}
        # Only stack frames may follow an accepted API diagnostic. A memory error
        # cannot hide in the same block by omitting its normal blank separator.
        if any(not re.match(r'^(Saved host backtrace|Host Frame:|at )', line) for line in block[1:]):
            return {'pass': False, 'reason': 'unexpected diagnostic detail', 'diagnostic': block}
        errors.append(match[1])
    valid = (application_returncode == 0 and seen_banner and len(counts) == 1
             and counts[0] == len(errors))
    if errors:
        valid = valid and allow_graph_fallback and len(errors) % 2 == 0 and all(
            errors[i:i + 2] == ['cudaGraphExecUpdate', 'cudaGetLastError']
            for i in range(0, len(errors), 2)
        )
    return {
        'pass': bool(valid), 'application_returncode': application_returncode,
        'reported_errors': counts, 'accepted_graph_fallbacks': len(errors) // 2 if valid else 0,
        'reason': 'clean or explicitly handled graph fallback' if valid else 'exit, summary or fallback pairing mismatch',
    }


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='fresh directory; contains logs, JSON and isolated cwd')
    parser.add_argument('--expect', required=True, help='required successful-test marker in application output')
    parser.add_argument('--allow-graph-fallback', action='store_true')
    parser.add_argument('--sanitizer', default='compute-sanitizer')
    parser.add_argument('command', nargs=argparse.REMAINDER, help='-- absolute-binary [args with absolute file paths]')
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or not Path(command[0]).is_absolute():
        parser.error('provide an absolute test executable after --')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    work = out / 'work'
    work.mkdir()
    sanitizer_log = out / 'sanitizer.log'
    app_log = out / 'application.log'
    invocation = [args.sanitizer, '--tool', 'memcheck', '--report-api-errors', 'all',
                  '--error-exitcode', '0', '--leak-check', 'full',
                  '--log-file', str(sanitizer_log), *command]
    # error-exitcode=0 preserves application failures. This classifier, not the
    # raw sanitizer status, supplies the mandatory nonzero CI result for findings.
    with app_log.open('w') as stream:
        process = subprocess.run(invocation, cwd=work, stdout=stream, stderr=subprocess.STDOUT)
    text = sanitizer_log.read_text() if sanitizer_log.exists() else ''
    result = _classify(text, process.returncode, args.allow_graph_fallback)
    result['test_completed'] = args.expect in app_log.read_text()
    result['pass'] = result['pass'] and result['test_completed']
    result['command'] = invocation
    result['graphs_disabled'] = os.environ.get('GGML_CUDA_DISABLE_GRAPHS')
    result['allow_graph_fallback'] = args.allow_graph_fallback
    result['logs_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (app_log, sanitizer_log) if p.exists()}
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if result['pass'] else 1


if __name__ == '__main__':
    sys.exit(_main())
