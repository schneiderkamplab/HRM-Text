# Desktop local API and headless server

Linux, Windows and macOS support an opt-in **text Chat Completions subset** of the
OpenAI API. The API is off by default. It runs locally and uses the loaded Mimir
model's own GGUF chat template. No cloud account is needed.

## While using the app

Open **Model and settings**, choose a port (default `8080`), and enable
**OpenAI-compatible local API**. The base URL is `http://127.0.0.1:8080/v1`.
Enable it again after restarting the app. API requests share the UI's loaded
model and execute serially with UI work; they do not create or alter saved chats.
Model/settings changes and new UI generation are disabled while API work is
pending. Turning the API off cancels its requests. Closing the app stops it.

The API uses exact PrefixLM requests without automatic compaction or cross-request
MixedLM cache reuse. API activity invalidates the UI's reusable inference cache,
but does not change its MixedLM setting or transcript. Oversized requests return
an error; clients own their conversation history and summarization.

## Headless start

The desktop packages include a standalone `dfm-mimir-server` executable
(`dfm-mimir-server.exe` on Windows). It loads the same native libraries and bundled
weights but needs no Flutter window or display server. Keep the package together.

```sh
# Linux, from the extracted package:
./dfm-mimir-server --port 8080
# macOS, from the installed app:
"/Applications/DFM Mimir.app/Contents/MacOS/dfm-mimir-server" --port 8080
# Windows PowerShell, from the extracted package:
.\dfm-mimir-server.exe --port 8080
```

Optional flags: `--model FILE.gguf`, `--profile FILE.json`, `--device auto|cpu|DEVICE`,
`--context TOKENS`, `--max-tokens TOKENS`, `--port PORT`, and `--library FILE` for
runtime development. `--help` prints usage without loading the model. Automatic
memory-dependent context sizing is the default; default reply budget is 512.
The bundled profile is used unless explicitly replaced. Stop with Ctrl-C; Linux
and macOS also handle SIGTERM and drain native work before exiting. Each separately
started process loads its own model; running GUI and headless processes together
can therefore consume additional memory.

The listener binds **only to 127.0.0.1**. Optionally set `MIMIR_API_KEY` before
launch to require `Authorization: Bearer YOUR_KEY` in both GUI and headless modes.
Without that variable, local callers need no key (SDKs that insist on one may use
any placeholder). Browser-origin requests are rejected; CORS and LAN listening
are not enabled in this version.

## Requests

```sh
curl http://127.0.0.1:8080/v1/models
curl http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"dfm-mimir","messages":[{"role":"user","content":"Hej Mimir!"}],"max_tokens":64}'
```

Supported endpoints:

- `GET /v1/models`: the loaded model is exposed under the stable alias `dfm-mimir`.
- `POST /v1/chat/completions`: JSON replies or SSE with `"stream":true`.
  Streams contain role/content deltas, a finish chunk and `data: [DONE]`.
  `"stream_options":{"include_usage":true}` adds a final usage chunk.

Supported fields: `model`, `messages`, `stream`, `stream_options`, `max_tokens`
or `max_completion_tokens` (one budget, not both), `temperature` (0–2, default 0),
`top_p` (0 < p ≤ 1, default 1), `seed` (0–4294967294, default 0), and `n:1`.
Temperature zero is greedy; a fixed seed with nonzero temperature enables
repeatable sampling within the same backend/runtime configuration. Sampling
settings and an optional initial system message apply only to that request.
If omitted, the system message comes from the loaded model profile.

Messages must be text: optional initial `system`, followed by alternating `user`
and `assistant` turns, ending with `user`. Responses include prompt/completion/
total token counts and `stop` or `length` finish reasons. Completion token usage
includes the end token when one is sampled.

Tools, images/audio, developer-role messages, stop strings, response formats,
logprobs, penalties, multiple candidates and the Responses API are unsupported.
Unsupported fields return an explicit error rather than being silently ignored.
This is not full OpenAI API parity.

At most eight API requests may be pending. Excess requests return HTTP 429;
there is a ten-minute request deadline including queue time and a 2 MiB body
limit. Disconnects cancel that request, including queued requests, without
cancelling another caller's work. SSE keepalives help detect disconnects during
prefill. Model-loading errors return 503, invalid requests/context overflow 400,
and unsupported model IDs 404. Errors after streaming begins use an SSE error
object followed by `[DONE]` (the HTTP status has already been sent).

## Development checks

The plain Dart package is `packages/mimir_api`; it depends only on Dart/FFI/path,
not Flutter. Desktop packaging compiles its `bin/server.dart` ahead of time.

Run `flutter test` for API protocol/validation/authentication/queue/deadline and
UI regression checks. With a real headless server running, run
`python tool/smoke_api.py --url http://127.0.0.1:8080/v1` for generation, SSE,
seeded sampling, concurrent requests, context overflow and disconnect recovery.
The smoke tool assumes authentication is disabled. Native regression tests
continue to cover chat-template rendering, PrefixLM and persistence.
