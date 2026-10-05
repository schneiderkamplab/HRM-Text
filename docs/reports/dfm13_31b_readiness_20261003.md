# Read-only31B handoff readiness

Snapshot ended2026-10-03T15:30:19.662533Z. Counts are exact per-database snapshots,
not a cross-database transaction; live work continues changing them. Raw counts,
per-DB timestamps and exact process start identities are in
`data/dfm13/wave4/handoff-readiness-20261003.json`. No processes signalled.

## Queue state

| Queue/stage | Done | Failed | Pending | Running |
| --- | ---: | ---: | ---: | ---: |
| Wave4 source audit | 3,816,751 | 5,270 | 3,611,550 | 3,128 |
| Wave4 repair generation | 75,540 | 46 | 18,421 | 257 |
| Wave4 repair audit | 37,061 | 34 | 0 | 0 |
| Baltic source audit | 5,187,548 | 6,469 | 0 | 0 |
| Baltic repair generation | 28,683 | 57 | 0 | 0 |
| Baltic repair audit | 17,636 | 1,453 | 0 | 0 |
| Baltic LT-summary privacy audit | 1,946 | 0 | 0 | 0 |

Pending wave4 repairs can create further re-audits; zero present repair-audit
pending is not final completion. CPU producers can also add source audits.
Terminal failed outcomes remain preserved, not reset or silently retried.

The staged76-job31B review queue is intentionally pending, excluded from26B drain.
Wave4 language-review76 and second-review57 are done. Earlier unused synthetic
queues are empty. Baltic productionPID2192702 has exited: ledger12,392 terminal
attempts,7,626 automated accepts,3,447valid nonaccepts,430invalid generation,
657invalid review,67abort-status-unknown and165review-abort-status-unknown.
Its progress says `drained`, active0. Those automated accepts remain under the
semantic quality hold, not independently accepted supply. The stale runtime PID
does not mean that producer is live. No generation target was reduced.

## CPU and producer blockers

* Direct/parallel controller2103630 remains alive, child2103633 with eight worker
  PIDs2103650..2103657. `parallel-preparation.json` and `parallel-stage.json`
  are absent. Controller still must finish direct work, its institutional stage,
  English pivots and enqueue before publishing the final marker. Current receipt
  inventory:203 direct,21institutional component receipts,0pivot receipts.
  Existing receipts alone do not prove successful/complete coverage.
* Wave4 Wikipedia CPU transformation receipts exist for all11languages. Native
  instruction receipts exist for18components. Their original preparation workers
  are no longer in the current process snapshot. This does not finish their
  audits, repairs, accepted selection or publication.
* Instruction advancer2365731 is live and may enqueue repairs/re-audits.
  Its latest summary has13uploaded/integrated,1empty, two pending repair groups
  (`parsinlu_comp`:68; `persian_qa`:87), plus two explicit source-fidelity holds
  (`pn_sum`, `wiki_sum`). These component summaries are not global queue totals.
* Transform advancer2355940 is live. Its receipts include pending audit retries;
  it remains a potential queue writer until finalized/frozen by its owner.
* Monitor2111503 automatically respawns audit/repair clients. It must be stopped
  by exact identity after work completion, otherwise an empty client list is not
  a stable drain condition. Current clients2032197/2111441 serve wave4 audits;
  2140598 serves repair generation.
* Wave4 selection2143812 waits for final parallel preparation. Translation
  publication2143813 and Baltic selection2131994/publication2121810 remain alive.
  These are primarily CPU consumers, not proof of GPU demand, but must be included
  in the final producer inventory rather than assumed finished.
* Baltic selections:41ready/published pairs, `en-lt` and `en-lv` still
  `awaiting_reviews` despite main queues terminal. Reconcile selector-specific
  completion against failed/exhausted outcomes; do not invent remaining live
  jobs or mark those pair selections complete from global queue counts alone.
* Matina/TLPC remain gated; bounded local plans are blocked on missing files,
  with zero prepared/queued rows. Their full sources are NOT complete. Record
  explicit access deferral in the handoff scope rather than claiming success or
  waiting indefinitely for an external permission change. Future preparation
  must not append work during the31B comparison without coordination.

## Ready pieces and decision

31B weights verified at revision842da3794eaa0b77d5f08bae87a17459d91ff475;
all12files/62.58GB verified. Fresh30wave4 and12Baltic prompts CPU-preflighted;
76review decisions queued separately. These do not authorize a switch now.

**NOT READY:** ongoing source production,3,611,550 pending audits,18,421pending
repair generations and active requests block release. Supervisor1856648 and its
eight26B servers remain untouched. After preparation/followup queues finish,
owners must freeze producers, resolve/explicitly defer quality/access holds,
capture fresh exact process identities and terminal queue counts, and only then
execute the documented31B transition. Do not reuse this stale snapshot as an
execution authorization.
