import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:mimir_api/native_engine.dart';
import 'package:mimir_api/api/server.dart';

import 'widget_test.dart' show FakeEngine, fixture;

class ApiEngine implements InferenceEngine {
  final calls = <Json>[];
  Completer<void>? hold;
  Cancellation? current;
  bool waitForCancellation = false;
  @override
  Future<List<Json>> command(
    Json command, {
    void Function(Json)? onEvent,
    Cancellation? cancellation,
  }) async {
    calls.add(command);
    current = cancellation;
    while (waitForCancellation && cancellation?.cancelled != true) {
      await Future<void>.delayed(const Duration(milliseconds: 5));
    }
    if (hold != null) await hold!.future;
    if (cancellation?.cancelled == true) throw StateError('Request cancelled');
    onEvent?.call({'type': 'prepared', 'tokens': 12});
    onEvent?.call({'type': 'token', 'text': 'Blåbær 🍓'});
    return [
      {
        'type': 'reply',
        'text': 'Blåbær 🍓',
        'limited': false,
        'cancelled': false,
        'completionTokens': 4,
      },
    ];
  }

  @override
  void cancel() {}
  @override
  Future<void> close() async {}
}

void main() {
  late ApiEngine engine;
  late LocalApiServer server;
  late HttpClient client;
  Json body({bool stream = false}) => {
    'model': 'dfm-mimir',
    'messages': [
      {'role': 'system', 'content': 'Svar på dansk'},
      {'role': 'user', 'content': 'Hej'},
    ],
    'stream': stream,
  };
  Future<(int, String)> send(
    Json input, {
    String? key = 'test-key',
    String? origin,
  }) async {
    final request = await client.postUrl(
      Uri.parse('${server.address}/chat/completions'),
    );
    if (key != null) request.headers.set('authorization', 'Bearer $key');
    if (origin != null) request.headers.set('origin', origin);
    request.headers.contentType = ContentType.json;
    request.write(jsonEncode(input));
    final response = await request.close();
    return (response.statusCode, await utf8.decoder.bind(response).join());
  }

  setUp(() async {
    engine = ApiEngine();
    client = HttpClient();
    server = LocalApiServer(
      engine: engine,
      ready: () => true,
      context: () => 1024,
      budget: () => 512,
      apiKey: 'test-key',
      maxPending: 1,
    );
    await server.start(port: 0);
  });
  tearDown(() async {
    engine.hold?.complete();
    await server.stop();
    client.close(force: true);
  });

  test(
    'API generation blocks UI send and never edits its conversation',
    () async {
      final directory = await Directory.systemTemp.createTemp(
        'mimir-api-store-',
      );
      final engine = FakeEngine();
      final store = fixture(engine, directory);
      final started = Completer<void>(), finish = Completer<void>();
      engine.handler = (command, onEvent) async {
        expect(command['op'], 'completion');
        started.complete();
        await finish.future;
        onEvent?.call({'type': 'prepared', 'tokens': 4});
        return [
          {
            'type': 'reply',
            'text': 'API answer',
            'limited': false,
            'cancelled': false,
            'completionTokens': 2,
          },
        ];
      };
      final client = HttpClient();
      try {
        store.updateDraft('Unsent UI draft');
        final selected = store.selected;
        await store.setApiEnabled(true, port: 0);
        final request = await client.postUrl(
          Uri.parse('${store.apiServer!.address}/chat/completions'),
        );
        request.write(
          jsonEncode({
            'model': 'dfm-mimir',
            'messages': [
              {'role': 'user', 'content': 'Independent API request'},
            ],
          }),
        );
        final response = request.close();
        await started.future;
        expect(store.apiBusy, true);
        expect(store.canSend, false);
        finish.complete();
        expect((await response).statusCode, 200);
        await Future<void>.delayed(const Duration(milliseconds: 20));
        expect(store.apiBusy, false);
        expect(store.canSend, true);
        expect(store.selected, selected);
        expect(store.messages, isEmpty);
        expect(store.draft, 'Unsent UI draft');
      } finally {
        if (!finish.isCompleted) finish.complete();
        await store.shutdown();
        client.close(force: true);
        await directory.delete(recursive: true);
      }
    },
  );
  test('models and completion schema, system prompt and sampling', () async {
    final req = await client.getUrl(Uri.parse('${server.address}/models'));
    req.headers.set('authorization', 'Bearer test-key');
    final models = jsonDecode(
      await utf8.decoder.bind(await req.close()).join(),
    );
    expect(models['data'][0]['id'], 'dfm-mimir');
    final (status, text) = await send({
      ...body(),
      'temperature': .7,
      'top_p': .9,
      'seed': 42,
      'max_tokens': 32,
    });
    final value = jsonDecode(text);
    expect(status, 200);
    expect(value['choices'][0]['message']['content'], 'Blåbær 🍓');
    expect(value['usage']['total_tokens'], 16);
    expect(engine.calls.single['system'], 'Svar på dansk');
    expect(engine.calls.single['temperature'], .7);
    expect(engine.calls.single['history'], isEmpty);
  });
  test('SSE has role, UTF-8 content, finish, usage and DONE', () async {
    final (status, text) = await send({
      ...body(stream: true),
      'stream_options': {'include_usage': true},
    });
    expect(status, 200);
    final data = text
        .split('\n')
        .where((line) => line.startsWith('data: '))
        .map((line) => line.substring(6))
        .toList();
    expect(data.last, '[DONE]');
    expect(jsonDecode(data[0])['choices'][0]['delta']['role'], 'assistant');
    expect(jsonDecode(data[1])['choices'][0]['delta']['content'], 'Blåbær 🍓');
    expect(jsonDecode(data[2])['choices'][0]['finish_reason'], 'stop');
    expect(jsonDecode(data[3])['usage']['prompt_tokens'], 12);
  });
  test(
    'unsupported fields and malformed histories rejected before inference',
    () async {
      for (final input in [
        {...body(), 'tools': []},
        {...body(), 'temperature': 'hot'},
        {...body(), 'max_tokens': 1024},
        {...body(), 'model': 'other'},
        {
          ...body(),
          'messages': [
            {'role': 'assistant', 'content': 'oops'},
          ],
        },
      ]) {
        final (status, _) = await send(input);
        expect(status, anyOf(400, 404));
      }
      expect(engine.calls, isEmpty);
    },
  );
  test('deadline cancels generation and returns HTTP 408', () async {
    await server.stop();
    server = LocalApiServer(
      engine: engine,
      ready: () => true,
      context: () => 1024,
      budget: () => 512,
      apiKey: 'test-key',
      requestTimeout: const Duration(milliseconds: 20),
    );
    await server.start(port: 0);
    engine.waitForCancellation = true;
    expect((await send(body())).$1, 408);
    expect(engine.current!.cancelled, true);
  });
  test('authentication and browser origin rejected', () async {
    expect((await send(body(), key: null)).$1, 401);
    expect((await send(body(), origin: 'http://untrusted.example')).$1, 403);
    expect(engine.calls, isEmpty);
  });
  test('bounded queue and stop cancel only owned request', () async {
    engine.hold = Completer<void>();
    final pending = send(body()).catchError((_) => (0, 'disconnected'));
    while (engine.calls.isEmpty) {
      await Future<void>.delayed(const Duration(milliseconds: 5));
    }
    expect((await send(body())).$1, 429);
    expect(engine.current!.cancelled, false);
    await server.stop();
    expect(engine.current!.cancelled, true);
    engine.hold!.complete();
    engine.hold = null;
    await pending;
  });
}
