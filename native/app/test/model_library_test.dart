import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter/services.dart';
import 'package:flutter/material.dart';
import 'package:dfm_mimir/model_library_view.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:dfm_mimir/model_library.dart';
import 'package:dfm_mimir/store.dart';

import 'widget_test.dart' show FakeEngine;

class Response extends Stream<List<int>> implements HttpClientResponse {
  final Stream<List<int>> stream;
  @override
  final int contentLength;
  Response(this.stream, this.contentLength);
  @override
  int get statusCode => 200;
  @override
  StreamSubscription<List<int>> listen(
    void Function(List<int>)? onData, {
    Function? onError,
    void Function()? onDone,
    bool? cancelOnError,
  }) => stream.listen(
    onData,
    onError: onError,
    onDone: onDone,
    cancelOnError: cancelOnError,
  );
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class Request implements HttpClientRequest {
  final Response response;
  Request(this.response);
  @override
  bool followRedirects = false;
  @override
  Future<HttpClientResponse> close() async => response;
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class Client implements HttpClient {
  final Response response;
  int requests = 0;
  bool closed = false;
  final List<Response>? responses;
  Client(this.response, {this.responses});
  @override
  Duration? connectionTimeout;
  @override
  Future<HttpClientRequest> getUrl(Uri uri) async {
    requests++;
    expect(uri.scheme, 'https');
    return Request(responses?.removeAt(0) ?? response);
  }

  @override
  void close({bool force = false}) {
    closed = true;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Directory dir;
  late Map<String, dynamic> descriptor;
  final bytes = [71, 71, 85, 70, 3, 0, 0, 0];
  setUp(() async {
    dir = await Directory.systemTemp.createTemp('mimir-library');
    descriptor = {
      'id': sha256.convert(bytes).toString(),
      'name': 'Test Mimir',
      'repo': 'example/DFM-Mimir',
      'revision': 'a' * 40,
      'file': 'test.gguf',
      'bytes': bytes.length,
      'profile': jsonDecode(await rootBundle.loadString('assets/profile.json')),
    };
  });
  tearDown(() async => dir.delete(recursive: true));

  testWidgets(
    'model selector displays sizes and never enables feedback permission',
    (tester) async {
      final store = ChatStore(
        engine: FakeEngine(),
        directory: dir,
        manualStartup: true,
      )..persistence = false;
      await tester.runAsync(store.initialize);
      await tester.pumpWidget(
        MaterialApp(home: ModelLibraryView(store: store)),
      );
      expect(find.textContaining('Selected:'), findsOneWidget);
      expect(find.text('DFM Mimir v1 Q4_K_M'), findsOneWidget);
      expect(store.library.catalog.length, 3);
      await tester.tap(find.byType(SwitchListTile));
      await tester.pump();
      expect(store.library.online, true);
      expect(store.onlineFeedback, false);
      await tester.scrollUntilVisible(find.textContaining('1.91 GB'), 250);
      expect(find.textContaining('1.91 GB'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await store.shutdown();
    },
  );
  test(
    'refresh discovers repositories without granting compatibility',
    () async {
      Response jsonResponse(Object value) {
        final body = utf8.encode(jsonEncode(value));
        return Response(Stream.value(body), body.length);
      }

      final client = Client(
        jsonResponse([]),
        responses: [
          jsonResponse({
            'version': 1,
            'models': [descriptor],
          }),
          jsonResponse([
            {'id': 'someone/DFM-Mimir-v2'},
          ]),
        ],
      );
      final library = ModelLibrary(clientFactory: () => client);
      library.setOnline(true);
      await library.refresh();
      expect(library.error, isNull);
      expect(client.requests, 2);
      expect(library.discovered, ['someone/DFM-Mimir-v2']);
      expect(library.catalog.single.id, descriptor['id']);
      expect(library.installed, isEmpty);
    },
  );
  test('offline permission prevents all network construction', () async {
    final library = ModelLibrary(
      clientFactory: () => throw StateError('Network forbidden'),
    );
    await library.download(ModelArtifact(descriptor));
    await library.refresh();
    expect(library.error, contains('Enable'));
    expect(library.installed, isEmpty);
    await library.close();
  });
  test('streamed download verifies and installs without selecting', () async {
    final client = Client(Response(Stream.value(bytes), bytes.length));
    final library = ModelLibrary(clientFactory: () => client)..directory = dir;
    library.setOnline(true);
    await library.download(ModelArtifact(descriptor));
    expect(library.error, isNull);
    expect(library.installed.single['id'], descriptor['id']);
    expect(await File(library.installed.single['path']).readAsBytes(), bytes);
    expect(
      await File('${library.installed.single['path']}.part').exists(),
      false,
    );
    expect(client.closed, true);
    await library.close();
  });
  for (final failure in ['hash', 'size', 'magic']) {
    test('$failure mismatch never installs and removes partial file', () async {
      var body = bytes;
      if (failure == 'hash') descriptor['id'] = '0' * 64;
      if (failure == 'size') descriptor['bytes'] = bytes.length + 1;
      if (failure == 'magic') {
        body = [0, 0, 0, 0, 0, 0, 0, 0];
        descriptor['id'] = sha256.convert(body).toString();
      }
      final library = ModelLibrary(
        clientFactory: () => Client(Response(Stream.value(body), -1)),
      )..directory = dir;
      library.setOnline(true);
      await library.download(ModelArtifact(descriptor));
      expect(library.error, isNotNull);
      expect(library.installed, isEmpty);
      expect(await Directory('${dir.path}/models').list().toList(), isEmpty);
      await library.close();
    });
  }
  test(
    'revoking permission mid-stream cancels and cleans partial bytes',
    () async {
      late ModelLibrary library;
      Stream<List<int>> body() async* {
        yield bytes.sublist(0, 4);
        library.setOnline(false);
        yield bytes.sublist(4);
      }

      final client = Client(Response(body(), bytes.length));
      library = ModelLibrary(clientFactory: () => client)..directory = dir;
      library.setOnline(true);
      await library.download(ModelArtifact(descriptor));
      expect(library.error, 'Cancelled.');
      expect(library.installed, isEmpty);
      expect(client.closed, true);
      expect(await Directory('${dir.path}/models').list().toList(), isEmpty);
    },
  );
  test('catalog validation rejects unpinned revisions and unsafe paths', () {
    expect(
      () => ModelArtifact({...descriptor, 'revision': 'main'}),
      throwsFormatException,
    );
    expect(
      () => ModelArtifact({...descriptor, 'file': '../model.gguf'}),
      throwsFormatException,
    );
    expect(
      () => ModelArtifact({...descriptor, 'bytes': -1}),
      throwsFormatException,
    );
    final library = ModelLibrary();
    expect(
      () => library.readCatalog(
        jsonEncode({
          'version': 1,
          'models': [descriptor, descriptor],
        }),
      ),
      throwsFormatException,
    );
  });
  test('Android library selection persists offline, never enters native, protects selected model', () async {
    final engine = FakeEngine()
      ..handler = (_, _) => throw StateError('Native must not load');
    final store = ChatStore(
      engine: engine,
      directory: dir,
      manualStartup: true,
    );
    await store.initialize();
    final file = File('${dir.path}/local.gguf');
    await file.writeAsBytes(bytes);
    await store.importModel(file.path);
    final first = store.model!;
    await file.writeAsBytes([...bytes, 1]);
    await store.importModel(file.path);
    expect(store.library.installed.length, 2);
    await store.selectModel(first);
    expect(store.model!['id'], first['id']);
    expect(store.ready, false);
    await store.deleteModel(first);
    expect(await File(first['path']).exists(), true);
    await store.shutdown();
    final reopened = ChatStore(
      engine: FakeEngine(),
      directory: dir,
      manualStartup: true,
    );
    await reopened.initialize();
    expect(reopened.library.online, false);
    expect(reopened.library.installed.length, 2);
    expect(reopened.model!['id'], first['id']);
    await reopened.deleteModel(
      reopened.library.installed.firstWhere((m) => m['id'] != first['id']),
    );
    expect(reopened.library.installed.length, 1);
    await reopened.shutdown();
  });
}
