import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import '../native_engine.dart';
import 'request.dart';

/// Text Chat Completions subset. NativeEngine serializes API and UI commands.
class LocalApiServer {
  final InferenceEngine engine;
  final bool Function() ready;
  final int Function() context;
  final int Function() budget;
  final void Function(bool)? onBusy;
  final String model;
  final String? apiKey;
  final Duration requestTimeout;
  final int maxPending;
  final _requests = <Cancellation>{};
  HttpServer? _server;
  bool _closing = false;
  LocalApiServer({
    required this.engine,
    required this.ready,
    required this.context,
    required this.budget,
    this.onBusy,
    this.model = 'dfm-mimir',
    this.apiKey,
    this.requestTimeout = const Duration(minutes: 10),
    this.maxPending = 8,
  });
  int? get port => _server?.port;
  String? get address => port == null ? null : 'http://127.0.0.1:$port/v1';

  Future<void> start({int port = 8080}) async {
    if (_server != null) throw StateError('API already running');
    _closing = false;
    _server = await HttpServer.bind(InternetAddress.loopbackIPv4, port);
    _server!.listen((request) {
      unawaited(_handle(request));
    });
  }

  Future<void> stop() async {
    _closing = true;
    for (final request in _requests) {
      request.cancel();
    }
    final server = _server;
    _server = null;
    await server?.close(force: true);
  }

  void _json(HttpResponse response, int status, Json value) {
    response.statusCode = status;
    response.headers.contentType = ContentType.json;
    response.write(jsonEncode(value));
  }

  Future<void> _handle(HttpRequest request) async {
    final response = request.response;
    Cancellation? cancellation;
    Timer? timeout, heartbeat;
    var streaming = false, disconnected = false, timedOut = false;
    void data(Object value) {
      if (!disconnected) {
        response.write(
          'data: ${value is String ? value : jsonEncode(value)}\n\n',
        );
      }
    }

    try {
      // Browser origins are deliberately not enabled for this local SDK endpoint.
      if (request.headers.value('origin') != null) {
        throw ApiError(403, 'Browser origins are not enabled');
      }
      if (apiKey != null &&
          request.headers.value('authorization') != 'Bearer $apiKey') {
        throw ApiError(401, 'Invalid API key');
      }
      if (_closing) throw ApiError(503, 'API stopping');
      if (request.method == 'GET' && request.uri.path == '/v1/models') {
        _json(response, 200, {
          'object': 'list',
          'data': ready()
              ? [
                  {
                    'id': model,
                    'object': 'model',
                    'created': 0,
                    'owned_by': 'local',
                  },
                ]
              : [],
        });
        return;
      }
      if (request.uri.path != '/v1/chat/completions') {
        throw ApiError(404, 'Unknown endpoint');
      }
      if (request.method != 'POST') throw ApiError(405, 'Use POST');
      if (!ready()) throw ApiError(503, 'Model not ready');
      if (_requests.length >= maxPending) {
        throw ApiError(429, 'Request queue is full');
      }
      final bytes = <int>[];
      await for (final chunk in request.timeout(const Duration(seconds: 15))) {
        if (bytes.length + chunk.length > 2 * 1024 * 1024) {
          throw ApiError(413, 'Request exceeds 2 MiB');
        }
        bytes.addAll(chunk);
      }
      final decoded = jsonDecode(utf8.decode(bytes));
      if (decoded is! Map<String, dynamic>) {
        throw ApiError(400, 'Expected a JSON object');
      }
      final command = completionCommand(decoded, model, context(), budget());
      // Recheck after asynchronously reading the body.
      if (_closing || !ready()) throw ApiError(503, 'Model not ready');
      if (_requests.length >= maxPending) {
        throw ApiError(429, 'Request queue is full');
      }
      final token = Cancellation();
      cancellation = token;
      _requests.add(token);
      onBusy?.call(true);
      response.done.then(
        (_) {},
        onError: (Object _) {
          disconnected = true;
          token.cancel();
        },
      );
      timeout = Timer(requestTimeout, () {
        timedOut = true;
        token.cancel();
      });
      final id =
          'chatcmpl-${DateTime.now().microsecondsSinceEpoch}-${Random.secure().nextInt(1 << 30)}';
      final created = DateTime.now().millisecondsSinceEpoch ~/ 1000;
      Json chunk(Json delta, String? finish) => {
        'id': id,
        'object': 'chat.completion.chunk',
        'created': created,
        'model': model,
        'choices': [
          {'index': 0, 'delta': delta, 'finish_reason': finish},
        ],
      };
      streaming = decoded['stream'] == true;
      if (streaming) {
        response.headers.contentType = ContentType(
          'text',
          'event-stream',
          charset: 'utf-8',
        );
        response.headers.set('cache-control', 'no-cache');
        response.bufferOutput = false;
        data(chunk({'role': 'assistant', 'content': ''}, null));
        await response.flush();
        // Detect disconnected clients during long prompt processing as well.
        heartbeat = Timer.periodic(const Duration(seconds: 5), (_) {
          if (disconnected) return;
          response.write(': keepalive\n\n');
          response.flush().catchError((Object _) {
            disconnected = true;
            token.cancel();
          });
        });
      }
      var promptTokens = 0;
      final events = await engine.command(
        command,
        cancellation: token,
        onEvent: (event) {
          if (event['type'] == 'prepared') {
            promptTokens = event['tokens'] as int;
          }
          if (streaming && event['type'] == 'token') {
            data(chunk({'content': event['text']}, null));
          }
        },
      );
      if (disconnected) return;
      if (timedOut) throw ApiError(408, 'Request timed out');
      final reply = events.firstWhere((e) => e['type'] == 'reply');
      if (reply['cancelled'] == true || token.cancelled) {
        throw ApiError(503, 'Request cancelled');
      }
      final finish = reply['limited'] == true ? 'length' : 'stop';
      final usage = {
        'prompt_tokens': promptTokens,
        'completion_tokens': reply['completionTokens'],
        'total_tokens': promptTokens + (reply['completionTokens'] as int),
      };
      if (streaming) {
        data(chunk({}, finish));
        if (decoded['stream_options']?['include_usage'] == true) {
          data({
            'id': id,
            'object': 'chat.completion.chunk',
            'created': created,
            'model': model,
            'choices': [],
            'usage': usage,
          });
        }
        data('[DONE]');
      } else {
        _json(response, 200, {
          'id': id,
          'object': 'chat.completion',
          'created': created,
          'model': model,
          'choices': [
            {
              'index': 0,
              'message': {'role': 'assistant', 'content': reply['text']},
              'finish_reason': finish,
            },
          ],
          'usage': usage,
        });
      }
    } catch (error) {
      cancellation?.cancel();
      final status = timedOut
          ? 408
          : error is ApiError
          ? error.status
          : error is FormatException
          ? 400
          : error is TimeoutException
          ? 408
          : '$error'.contains('exceed context')
          ? 400
          : 500;
      final message = timedOut
          ? 'Request timed out'
          : error is ApiError
          ? error.message
          : '$error';
      final body = {
        'error': {
          'message': message,
          'type': status < 500 ? 'invalid_request_error' : 'server_error',
          'code': status,
        },
      };
      if (!disconnected) {
        try {
          if (streaming) {
            data(body);
            data('[DONE]');
          } else {
            _json(response, status, body);
          }
        } catch (_) {
          /* Peer may already be gone. */
        }
      }
    } finally {
      timeout?.cancel();
      heartbeat?.cancel();
      if (cancellation != null) _requests.remove(cancellation);
      onBusy?.call(_requests.isNotEmpty);
      try {
        await response.close();
      } catch (_) {
        /* Disconnected peer. */
      }
    }
  }
}
