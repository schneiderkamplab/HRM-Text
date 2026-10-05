# Repair25 Launch Coordination

## Terminal Result (2026-10-03)

V3 PID2695189 has exited; report.json records25/25 terminal and3 provisional
keeps. There are37 persisted raw HTTP responses. Six cases reached review;
18 failed protected-content validation (13 code/JSON,5 numerical answer), and
one repair failed with repeated_text_loop without retry. These are observed
validator outcomes, not independently confirmed semantic defects. Per-case
receipts are in outcomes/. Admission, production approval and publication
remain false. Post-run verify returns25. The later main-launched v2 attempt
failed its implementation pin before inference. No repair client remains live;
no further launch is needed.55 focused tests passed before freezing v3.
Independent semantic inspection remains pending.

## Launched

Owner switchback status `logs/dfm13/gemma26-compiled-switchback-20261003-v1/status.json`
reported all eight ready. All endpoints independently passed exact26B snapshot
and32K checks. Detached client PID2695189 launched with eight workers.
Root: `data/dfm13/gemma26-repair25-20261003-v3`.
Log: `logs/dfm13/gemma26-repair25-20261003-v3.log`.
Receipt: root `launch.json`;55tests passed. V3 adds only recognition of the known
`dfm13-gemma4` alias when canonical ID is present and every alias resolves to the
same selected snapshot/context. V2 remains preserved, not repinned.
Do not launch a duplicate client. All candidates remain nonadmitting.

## Superseded Prelaunch Status

Main authorizes this agent to launch the bounded25 repair/blind-re-audit client
after Epicurus confirms26B ready. Current local process inspection still shows
31B servers on8800..8807; no repair client has been launched.

Epicurus/main: please record the26B readiness/ownership handoff path here or send
it through main. Required identity: `google/gemma-4-26B-A4B-it`, snapshot
`4d7ae4984b7db7de8f8457170b3f1a419ee76d52`, all8800..8807,32K context.
No server lifecycle action will be taken by this client owner.

Prepared root: `data/dfm13/gemma26-repair25-20261003-v2`.
Supersedes unlaunched sequential v1 after explicit all-eight parallel request.
Eight workers, one case/request per endpoint;54tests pass, including actual
eight-way mocked overlap and raw writer uniqueness. No bulk/high concurrency.
Capacity measurement is terminal/sealed with final queues drained.
Client command is in `dfm13_repair25_cpu_handoff_20261003.md`.
No parallel repair25 launch, please; this agent owns the single client and
casewise outcome report. All results remain nonadmitting.
