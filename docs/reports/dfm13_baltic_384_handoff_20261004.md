# Baltic 384/Server Runtime Handoff

User-authorized isolated successor `dfm12.baltic_concurrency384` changes only
the private runner concurrency guard. Existing frozen dependencies, candidate
contracts, recovery adapter, sources and ledger rows remain unchanged.

Old runtime2936091 received verified SIGTERM and drained to98,642 accepted,
zero active. Watcher2936761 was already absent; no other watcher was found.
No unrelated process was signalled. Migration and launch receipts:
`data/dfm13/baltic/concurrency384-migration-20261004-v1`.

New detached PID3051744, command:
`python -u -m dfm12.baltic_concurrency384 run --root data/dfm13/baltic/synthetic-compact-26b-20261004-v1`.
Log: `logs/dfm13/baltic-concurrency384-20261004-v1.log`.
Live runtime confirms384/server,3072 maximum HTTP requests across eight endpoints,
unchanged0.90 KV guard and admission throttling. First check98,644 accepted/99 active.
This is a concurrency ceiling, not a claim that3072 requests are continuously active.
26 focused/recovery/shared-review tests passed.

## Watcher Owner Action

Harvey/parent must re-arm with manifest SHA256
`6a22dc6981f35114b8688e1414304290a67f7b30dbc92732b7a8fc724612a4a8`
and recognize manifest `runtime_module=dfm12.baltic_concurrency384` as the owned
client. Preserve recovery-aware completion proofs; do not change W4 concurrency.
No duplicate watcher was launched here. Old manifest/seal archived in migration
root. Base successor policy remains128; the explicitly pinned runtime override
is384 and its verifier requires that exact setting.
