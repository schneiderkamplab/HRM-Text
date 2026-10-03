// ignore_for_file: avoid_print
// Temporary local test entry point. Never package as the application entry point.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:cupertino_http/cupertino_http.dart';
import 'package:dfm_mimir/network.dart';
import 'package:dfm_mimir/store.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

void check(bool condition, String message) {
  if (!condition) throw StateError(message);
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MaterialApp(home: Scaffold(body: Text('Apple OS TLS probe'))));
  try {
    var disabled = false;
    try {
      SecurityContext();
    } on ArgumentError catch (error) {
      disabled = error.message.toString().contains(
        'Secure Sockets unsupported',
      );
    }
    check(disabled, 'Dart TLS remains enabled');
    print('Dart TLS disabled');
    final client = createNetworkClient();
    check(client is CupertinoClient, 'Expected native Apple transport');
    final session = NetworkSession(client);
    try {
      final response = await session
          .send(
            'GET',
            Uri.parse(
              'https://raw.githubusercontent.com/schneiderkamplab/HRM-Text/main/native/app/assets/models.json',
            ),
          )
          .timeout(const Duration(seconds: 30));
      check(response.statusCode == 200, 'Catalog HTTPS failed');
      print('Native HTTPS status 200');
      check(
        (await response.stream.bytesToString()).contains('models'),
        'Bad catalog',
      );
    } finally {
      session.close();
    }
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    server.listen((request) async {
      print('Loopback request received');
      request.response.headers.contentType = ContentType.binary;
      request.response.bufferOutput = false;
      request.response.add(List.filled(16384, 65));
      await request.response.flush();
    });
    final streaming = NetworkSession(createNetworkClient());
    try {
      final response = await streaming.send(
        'GET',
        Uri.parse('http://127.0.0.1:${server.port}'),
      );
      print('Native stream headers received');
      final done = response.stream.drain<void>().then(
        (_) => false,
        onError: (Object error) => error is http.RequestAbortedException,
      );
      streaming.close();
      check(
        await done.timeout(const Duration(seconds: 5)),
        'Streaming abort failed',
      );
    } finally {
      streaming.close();
      await server.close(force: true);
    }
    final directory = await Directory.systemTemp.createTemp('mimir-os-tls-');
    final store = ChatStore(directory: directory);
    try {
      await store.initialize().timeout(const Duration(minutes: 3));
      check(store.ready, 'Model not ready: ${store.notice}');
      check(
        !store.search.enabled && !store.library.online && !store.onlineFeedback,
        'Networking should default to off',
      );
      await store.setLimits(1024, 32);
      check(store.ready, 'Reload failed: ${store.notice}');
      store.updateDraft('Svar kun med tallet: Hvad er 2 + 2?');
      await store.send().timeout(const Duration(minutes: 3));
      check(
        store.messages.length == 2 &&
            store.messages.last['content'].toString().contains('4'),
        'Templated generation failed: ${store.notice} ${store.messages}',
      );
      check(store.used != null, 'Context usage missing');
      print('Offline templated generation passed: ${store.modelStatus}');
      await store.setTextScale(1.25);
      await store.save();
      final saved = jsonDecode(
        await File('${directory.path}/conversations.json').readAsString(),
      );
      check(
        saved['textScale'] == 1.25 && saved['chats'].isNotEmpty,
        'Settings/chat persistence failed',
      );
      if (Platform.isMacOS) {
        await store.setApiEnabled(true, port: 0);
        check(
          store.apiServer?.port != null,
          'Local API failed: ${store.notice}',
        );
        final api = createNetworkClient();
        try {
          final reply = await api
              .post(
                Uri.parse('${store.apiServer!.address}/chat/completions'),
                headers: {'Content-Type': 'application/json'},
                body: jsonEncode({
                  'model': 'dfm-mimir',
                  'messages': [
                    {
                      'role': 'user',
                      'content': 'What is 2 + 2? Answer with just the number.',
                    },
                  ],
                  'max_tokens': 16,
                }),
              )
              .timeout(const Duration(minutes: 3));
          check(
            reply.statusCode == 200 &&
                jsonDecode(
                  reply.body,
                )['choices'][0]['message']['content'].toString().contains('4'),
            'Local OpenAI API generation failed: ${reply.statusCode} ${reply.body}',
          );
          print('Local OpenAI API generation passed');
        } finally {
          api.close();
          await store.setApiEnabled(false);
        }
      }
      print('Settings and chat persistence passed');
    } finally {
      await store.shutdown();
      await directory.delete(recursive: true);
    }
    print('MIMIR_OS_TLS_PROBE_PASS');
    exit(0);
  } catch (error, stack) {
    print('MIMIR_OS_TLS_PROBE_FAIL: $error\n$stack');
    exit(1);
  }
}
