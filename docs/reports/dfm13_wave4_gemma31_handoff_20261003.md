# Wave4 31B comparison handoff

## Current freeze coordination

**Resolved, later 2026-10-03:** the user relayed Epicurus's final transition
freeze confirmation. This confirmation is recorded explicitly in
`data/dfm13/wave4/transition-frozen.json`; it is not a server-transition approval.
CPU waiter2394992 completed and exited. The authoritative successor receipt is
now `phase=ready`. Independent fresh-runner verification returned30 and12 for
`data/dfm13/wave4/gemma31-fresh-comparison30-v4` and
`data/dfm13/baltic/gemma31-fresh-comparison12-v2`, respectively. All42 original
specifications and requests are unchanged. Maximum prompt plus output reserve
is5850/5505 tokens. Both production-v2 roots also verify (770000/140000 targets),
but remain unapproved. No GPU requests or server changes occurred.

The pending-freeze account below is historical and superseded by this receipt.

The transition closing fix invalidated the pinned implementation in fresh30-v3
and Balticfresh12. Preserve both; do NOT repin or run them. Epicurus owns further
deferred-queue transition edits. CPU-only waiterPID2394992 is waiting at most
1800seconds for `data/dfm13/wave4/transition-frozen.json`, containing `frozen:true`,
`path:dfm12/wave4_gemma31_transition.py`, and its final `sha256`.

It will create NEW `data/dfm13/wave4/gemma31-fresh-comparison30-v4` and
`data/dfm13/baltic/gemma31-fresh-comparison12-v2`, compare every original spec and
request for exact equality, rerun actual31B tokenizer preflight, verify all pins
and recheck both production-v2 roots. It does not launch GPU clients/servers.
Authoritative completion/current-root receipt:
`data/dfm13/wave4/fresh42-successor-status.json`; use successors ONLY when
`phase=ready` and their own verify succeeds. Log:
`logs/dfm13/fresh42-after-freeze.log`. Poincare's234unexposed cases are separate.
Until freeze/completion, there are no newly verified launchable42successor roots.
Both production-v2 roots currently verify without drift; they remain unapproved.

After receipt readiness, explicitly pass `--root` to the fresh runner; its
historical default in the recipe below is superseded. If the bounded waiter
times out, run `python scripts/refresh_wave31_fresh_after_freeze.py` after freeze;
it refuses to overwrite any existing successor root. Never copy hashes into old
manifests to conceal drift.

Prepared only; no current process was stopped and no GPU calls were made.
No further speculative 26B variants. Stronger-teacher comparison is the next
experiment, not automatic admission of the full synthetic target.

## Inventory and scope

Actual root: `data/dfm13/wave4/gemma31-quality-comparison` (not the concatenated
`gemma31-quality-comparison76jobs`). All76 jobs, candidate hashes, control hash,
and requested model names passed CPU inspection. These are reviews of existing
full candidates, NOT76 fresh 31B generations. Assess disagreement against the
independent42 and literal-probe findings before running a separate, full-target
generation comparison; good judge scores alone cannot authorize production.

Current supervisor1856648, start_ticks243291566, owns all eight8800..8807 APIs.
It runs `scripts/dfm13_repo_bulk_interlude.py replicas` and the proven shared
launcher. Stopping individual API children would trigger coupled cleanup.
Use only the pinned supervisor identity after drain. The new module uses pidfd
and rechecks starttime/session/command; it never kills by name/port or escalates.

Superseded later2026-10-03: Local31B cache had only `refs`; `/work/mimir/brainsurgery/models/gemma4_31b`
contains only tokenizer files. Complete authenticated31B-it weight preparation
was a blocker BEFORE any26B release. The subsequent authorized download below
resolved the weight blocker without any gate bypass.
The operator must verify upstream model/revision identity; a served alias alone
is not model provenance. The code checks config/index/tokenizer and every indexed
weight shard is present/nonempty, not that all tensor bytes match upstream hashes.

## Exact readiness contract

Write a handoff JSON only once the inventory is exhaustive, using process
identities captured with `dfm12.diagnostic_server.identity` and SHA256 receipts:

```json
{
  "cpu_preparation_complete": true,
  "producers_frozen": true,
  "model": "google/gemma-4-31B-it",
  "model_files": {"ABSOLUTE_CONFIG_INDEX_TOKENIZER_CONFIG_PATHS": "SHA256_FOR_EACH"},
  "supervisor": {"pid": 1856648, "start_ticks": "243291566", "create_time": 1791015442.66, "session_id": 1856648, "cmdline": ["COPY EXACT endpoints.json supervisor cmdline"]},
  "completion_receipts": {"PATH_TO_FINAL_CPU_AND_CAMPAIGN_RECEIPT": "SHA256"},
  "databases": ["PATH_TO_EVERY_SOURCE_AUDIT_REPAIR_PRIVACY_QUEUE"],
  "clients_and_producers": [{"pid": 0, "start_ticks": "REPLACE", "session_id": 0, "cmdline": []}]
}
```

The example is deliberately not executable authorization. Required predicates:

1. All source CPU preparation complete, final receipts hash-bound, no producers
   or schedulers able to append work. Include wave4 instructions, transforms,
   parallel/OPUS and both Baltic/wave4 campaign/repair/translation/privacy work.
2. Every queue has only `done`/`failed`; zero pending/running, including repair
   generation AND re-audit. Failed outcomes are retained, not retried/reset.
3. Every endpoint consumer/producer is drained and exited, including Baltic
   synthetic production and monitor-spawned clients. Queue emptiness alone is
   insufficient. Coordinate producer freeze with owners; do not kill workers
   during CPU preparation. No automated client-killing is implemented.
4. Complete verified31B-it snapshot is local. The current supervisor identity
   still matches. Recheck inventory immediately before explicit transition.
5. After supervisor TERM, wait at most180s, then require all GPUs free. If cleanup
   fails or foreign GPU use remains, abort without escalation or overlap.

The contract is an operator attestation of complete inventory, not automatic
discovery of all consumers. Do not create a partial manifest just to pass gates.

## Commands

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
$PY -m dfm12.wave4_gemma31_transition inspect
$PY -m dfm12.wave4_gemma31_transition check --contract HANDOFF.json --model-path VERIFIED_31B_SNAPSHOT
# Only after check succeeds and owners confirm complete inventory:
setsid $PY -u -m dfm12.wave4_gemma31_transition transition --contract HANDOFF.json --model-path VERIFIED_31B_SNAPSHOT > logs/dfm13/gemma31-transition.log 2>&1 < /dev/null &
```

Default output `logs/dfm13/wave4-gemma31-comparison`; exclusive transition lock.
The dedicated supervisor reuses existing launcher/environment/cleanup, eight
parallel TP1 launches, utilization.95, context32768, prefill16384, unique internal
ports32000+100*GPU, max sequences8. It advertises ONLY31B, no26B alias.
This is a candidate31B configuration, not yet live-proven memory/startup behavior.
Wait at most two hours for all eight model identities before client submission.
Client uses existing `european_stage`,8/server maximum, existing persistent76-job
DB, no target truncation or rewriting. Logs, ownership and terminal receipts stay
local. No automatic fallback, export, production approval or training actions.

If interrupted after release/launch, inspect receipts and owned server state
before recovery; do not rerun transition blindly. The comparison queue itself
uses the existing restartable leased client. Operators may rerun the recorded
`client-command.json` after verifying the eight31B endpoints.

## Completion decision

Do not leave an indefinite model-quality hold: finish current source/repair
drain, prepare authenticated weights in parallel, execute this explicit handoff,
review76 outcomes semantically, then compare fresh full-target generation on
the known failure families and untouched controls. Keep failures and native
language uncertainty visible; no automatic production approval at either step.

## Verified download and fresh generation preparation

Authorized CPU/network downloader `dfm12.wave4_gemma31_download`, PID2320976,
completed successfully and exited. Existing HF credentials passed gated
`config.json` retrieval. Disk check recorded ample free space, with a conservative
two-snapshot plus5GiB margin. No credential was printed or stored in receipts.
Log: `logs/dfm13/gemma31-download.log`; status/ready/revision/disk receipts:
`data/dfm13/wave4/gemma31-download/`.

Exact upstream revision `842da3794eaa0b77d5f08bae87a17459d91ff475`.
All12 upstream files verified,62,578,686,256 bytes. LFS files matched upstream
SHA256; regular files matched upstream git blob IDs, with localSHA256 retained.
The two weight SHA256 values are:

* `eeef8791537bc04f110967c513149e037d2a9ae97d49add7291ebfa62806bbfa`
* `018912220f559f7025d60333e0996183cd538aa77ad6f4988a89ce47be681f10`

`ready.json` is atomically published only after complete verification and contains
the snapshot and `model_files` needed by the handoff contract. Receipt snapshot:
`/home/ucloud/.cache/huggingface/hub/models--google--gemma-4-31B-it/snapshots/842da3794eaa0b77d5f08bae87a17459d91ff475`
(same cache visible under `/work/mimir/.home/.cache/huggingface`).

Fresh generation runner: `dfm12.wave4_gemma31_fresh`; prepared sealed root:
`data/dfm13/wave4/gemma31-fresh-comparison30-v3`. Earlier unlaunched30/v2
preparations are superseded and preserved; do not run or repin those roots.
Fourteen exposed weak cases plus
sixteen controls, spanning all11 wave4 languages and all six families. This is
a matched historical comparison, not randomized heldout performance. It reuses
the original complete requests and CPU schemas, replacing ONLY teacher model;
no speculative literal-probe suffix. Full original specs, sources, references,
targets and baseline candidate hashes remain pinned. No automatic publication.

Actual31B tokenizer CPU preflight passed30/30, largest prompt+output reserve5850
tokens, well within32768. Student assembly/rendering/semantic validators remain
unchanged. Live endpoints must advertise exclusively31B,32K context and the
verified snapshot path. No GPU requests have been made for this comparison.

After the documented drain and31B startup (and after76-job review client if
running, to respect combined8/server), launch:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.wave4_gemma31_fresh verify
setsid /home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.wave4_gemma31_fresh run --concurrency-per-server 2 > logs/dfm13/gemma31-fresh30.log 2>&1 < /dev/null &
```

Each fresh generation gets strict automated31B review, explicitly NOT independent
certification. `independent-review-queue.json` lists every full candidate with its
hash and source/reference location, withholding automatic verdicts from the
review queue. Independent readers must inspect every target for native prose,
grounding and instruction compliance before any readiness conclusion. Same-model
keeps alone never admit rows. SIGTERM drains inflight work; no server ownership.

Following the reported graceful Baltic production drain, a second sealed root
`data/dfm13/baltic/gemma31-fresh-comparison12` prepares all six families for both
LT/LV from the prior coherence probe, including failed generation slots with no
baseline candidate. Those pairs explicitly record a null baseline candidate and
original status, not a fabricated baseline answer. Full original requests/specs
remain available. Run sequentially after the wave4 comparison, sharing no more
than8 concurrent requests/server across clients:

```bash
setsid /home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.wave4_gemma31_fresh run --root data/dfm13/baltic/gemma31-fresh-comparison12 --concurrency-per-server 2 > logs/dfm13/gemma31-baltic-fresh12.log 2>&1 < /dev/null &
```

Both roots preserve all production targets; no production config is changed.
Focused downloader/endpoint/handoff tests:8passed. Fresh preflight uses no GPU.
The reported newLV fidelity recall1/5 is additional user-supplied motivation for
the stronger teacher, not independently remeasured by this task.
