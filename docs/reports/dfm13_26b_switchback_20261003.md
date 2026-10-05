# 26B switch-back after bounded31B measurement

Prepared commands only; not executed by this review.26B remains the default bulk
model. The bounded31B comparisons have not established a production advantage.
Measurement-v1 completed300 seconds plus72.47 seconds drain:1666 plateau and
1730 total completions, zero request errors/OOM/preemptions, maximum sampled
KV30.38%, per-server plateau p95 range25.05-31.40 seconds. Six completions ended
at length. Evidence complete; capacity/admission/publication approval false.
The stale progress.json final203/204 on8807 is superseded by measurement.json
(204 completed there), its seal and captured log evidence. No further ramp.

## Owner-executed release

First confirm no new clients were started after measurement. The command below
checks the exact recorded supervisor and writes only this lifecycle's stop
request. It waits for owned cleanup, never signals unrelated processes or
escalates. Timeout is a blocker requiring inspection, not permission to kill.

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
"$PY" - <<'PY'
import time
from pathlib import Path
from dfm12.io import load
from dfm12.diagnostic_server import identity
root = Path('logs/dfm13/gemma31-capacity-ramp-cacheisolated-20261003-v1')
expected = load(root / 'endpoints.json')['supervisor']
assert expected['pid'] == 2669751
assert expected['start_ticks'] == '247738605'
current = identity(expected['pid'])
assert all(current[k] == expected[k] for k in ('start_ticks', 'session_id', 'cmdline'))
(root / 'stop.request').touch(exist_ok=True)
deadline = time.monotonic() + 180
while not (root / 'stopped.json').exists():
    if time.monotonic() >= deadline:
        raise SystemExit('Owned cleanup timeout: inspect; no escalation')
    time.sleep(2)
receipt = load(root / 'stopped.json')
assert receipt.get('only_owned_cleanup') is True
assert receipt.get('cleanup_survivors') == []
print('Owned cleanup receipt verified; check free GPUs/ports before launch')
PY
```

Only after that command succeeds and GPUs/ports are free, run the established
26B replicas mode, NOT its training-interlude `run` mode. Choose a never-used
root; the launcher independently refuses occupied GPUs/ports or existing
ownership. A launch refusal does not authorize stopping another workload.

```bash
ROOT26=logs/dfm13/gemma26-compiled-switchback-20261003-v1
test ! -e "$ROOT26" || { echo 'Choose a fresh server root'; exit 1; }
setsid "$PY" -u scripts/dfm13_repo_bulk_interlude.py replicas \
  --server-root "$ROOT26" > "${ROOT26}.log" 2>&1 < /dev/null &
```

This is the prior compiled setup: eight TP1 servers,32K context, max-seqs1024,
prefill16384, memory.95, native Gemma tool/reasoning parsers and aliases
dfm13-gemma4/google/gemma-4-26B-A4B-it. Compilation/graphs are enabled (the launcher
removes enforce-eager). Require fresh all-eight health and the expected26B model
before any bulk client. This is server capacity, not a command to dispatch1024
requests/server. Preserve all31B roots/caches/evidence and unrelated HF
publishers/CPU tokenizers. No training resume, cache deletion or automatic bulk
admission is part of this procedure.
