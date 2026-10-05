# Baltic I/O Runtime Handoff

New private modules `dfm12.baltic_async_io` and `dfm12.baltic_io_runtime`.
Single owner executor constructs/uses source provider, SQLite ledger and budget;
durable writes remain awaited and unchanged. Fingerprint check+insert is one
owner operation. Cancellation waits for pending durable operation completion.
Existing unknown-request no-replay policy retained. No shared dependencies edited.

Transport:2-second client keepalive (server reported5),5-second cooldown
set once per circuit instead of extended by concurrent failures. User-approved
spacing0.01s/poll0.01s/waiting<=128/KV<=0.90 with mandatory health probes.

## Harvey Watcher Coordination

New actual client module: `dfm12.baltic_io_runtime`.
Manifest retains base `runtime_module=dfm12.baltic_concurrency384` and adds
`io_runtime_module=dfm12.baltic_io_runtime`. Explicitly recognize that combination
in the watcher and use `baltic_io_runtime.controller()` for completion verification.
Reject unknown combinations. Re-arm/reseal W4 only after migrated manifest and
new live runtime receipt; W4 generation concurrency/other contracts unchanged.
Owner paused only watcher3052704 and drained Baltic3051744 before
authorized migration; no other clients/servers touched.

Migration receipt root:
`data/dfm13/baltic/io-runtime-migration-20261004-v1`.
Run command: `python -u -m dfm12.baltic_io_runtime run --root data/dfm13/baltic/synthetic-compact-26b-20261004-v1`.

## Applied and Live

Old runtime drained at107,880 accepted/zero active. New detached PID3070664;
log `logs/dfm13/baltic-io-runtime-20261004-v1.log`. First live receipt107,894
accepted (+14 after restart)/495 active. Runtime confirms384/server,0.01s
spacing,128 waiting limit,5s cooldown. Manifest hash:
`3ef2ccd2be689a4523963f72b2d2bdd93a0c2b6a0743ea29972b960abf1a66e9`.
Exact pre/post and runtime contract: migration root `live-progress-proof.json`.
33 tests passed, including mocked HTTP through execute/generation/review/raw
capture/acceptance, SQLite and raw-writer owner-thread checks, cancellation
durability, atomic fingerprint claims and unknown-request no-replay. AST sites
are counted fail-closed; the full pipeline test caught and fixed incorrect
source introspection of the dynamically compiled previous runner before launch.
Harvey/parent still owns recovery-aware W4 whitelist/reseal/re-arm.

## Zero Spacing Successor

Later user authorization supersedes fixed0.01s spacing only. New isolated module
`dfm12.baltic_zero_spacing` leaves both I/O dependency files unchanged. Old
PID3070664 drained at109,163 accepted; new PID3074327 first reported109,164
accepted/434 active with runtime spacing0,384/server.34 tests pass.
Receipts: `data/dfm13/baltic/zero-spacing-migration-20261004-v1`.
Manifest SHA256: `777d016c1028b76130267a319c9aec870009afa286a68cd6d2a4fe30f712769e`.
Harvey: explicitly recognize `zero_spacing_runtime_module=dfm12.baltic_zero_spacing`
and use its `controller()` for completion verification; no other policy changes.
