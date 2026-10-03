// ignore_for_file: avoid_print
// Temporary local test entry point. Never package as the application entry point.
import 'dart:async';
import 'dart:io';

import 'package:cupertino_http/cupertino_http.dart';
import 'package:dfm_mimir/network.dart';
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
    print('MIMIR_OS_TLS_PROBE_PASS');
    exit(0);
  } catch (error, stack) {
    print('MIMIR_OS_TLS_PROBE_FAIL: $error\n$stack');
    exit(1);
  }
}
