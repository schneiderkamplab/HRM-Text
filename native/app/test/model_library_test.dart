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

class Headers implements HttpHeaders {
  @override
  String? value(String name) => null;
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class Response extends Stream<List<int>> implements HttpClientResponse {
  final Stream<List<int>> stream;
  @override
  final int contentLength;
  Response(this.stream, this.contentLength);
  @override
  int get statusCode => 200;
  @override
  HttpHeaders get headers => Headers();
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
      'repo': 'danish-foundation-models/DFM-Mimir-v1.5-GGUF',
      'revision': 'a' * 40,
      'file': 'test.gguf',
      'bytes': bytes.length,
      'profile': jsonDecode(await rootBundle.loadString('assets/profile.json')),
    };
  });
  tearDown(() async => dir.delete(recursive: true));

  test('saved catalog retains discovered entries and gains shipped models', () async {
    await File('${dir.path}/conversations.json').writeAsString(jsonEncode({
      'version': 1,
      'chats': [],
      'modelCatalog': {'version': 1, 'models': [descriptor]},
    }));
    final store = ChatStore(engine: FakeEngine(), directory: dir, manualStartup: true)
      ..persistence = false;
    await store.initialize();
    expect(store.library.catalog.any((a) => a.id == descriptor['id']), true);
    expect(store.library.catalog.where((a) => a.data['repo'] ==
      'danish-foundation-models/DFM-Mimir-v1.5-GGUF').length, greaterThanOrEqualTo(3));
    expect(store.library.catalog.any((a) => a.data['repo'] ==
      'danish-foundation-models/DFM-Mimir-GGUF'), true);
    await store.shutdown();
  });

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
      expect(find.text('DFM Mimir v1.5 Q4_K_M'), findsWidgets);
      expect(
        store.library.catalog.map((a) => a.data['repo']),
        contains('danish-foundation-models/DFM-Mimir-v1.5-GGUF'),
      );
      await tester.tap(find.byType(SwitchListTile));
      await tester.pump();
      expect(store.library.online, true);
      expect(store.onlineFeedback, false);
      await tester.scrollUntilVisible(find.textContaining('1.91 GB'), 250);
      expect(find.textContaining('1.91 GB'), findsWidgets);
      expect(tester.takeException(), isNull);
      await store.shutdown();
    },
  );
  test(
    'refresh ignores matching repositories outside the official organization',
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
            {'id': 'someone/DFM-Mimir-GGUF-v2'},
          ]),
        ],
      );
      final library = ModelLibrary(clientFactory: () => client);
      library.setOnline(true);
      await library.refresh();
      expect(library.error, isNull);
      expect(client.requests, 2);
      expect(library.discovered, isEmpty);
      expect(library.catalog.single.id, descriptor['id']);
      expect(library.installed, isEmpty);
    },
  );
  test('official files merge with curated profile precedence and source failure recovery', () async {
    Response reply(Object data) {
      final body = utf8.encode(jsonEncode(data));
      return Response(Stream.value(body), body.length);
    }

    final official = {
      ...descriptor,
      'repo': 'danish-foundation-models/MIMIR-GGUF',
    };
    List<Response> discovery() => [
      reply([
        {'id': official['repo']},
      ]),
      reply({'sha': 'a' * 40}),
      reply([
        {
          'type': 'file',
          'path': 'test.gguf',
          'size': 8,
          'lfs': {'oid': descriptor['id']},
        },
        {
          'type': 'file',
          'path': 'new.gguf',
          'size': 9,
          'lfs': {'oid': 'b' * 64},
        },
      ]),
    ];
    final client = Client(
      reply([]),
      responses: [
        reply({
          'version': 1,
          'models': [official],
        }),
        ...discovery(),
        reply({'version': 999}),
        ...discovery(),
      ],
    );
    final library = ModelLibrary(clientFactory: () => client)..setOnline(true);
    await library.refresh();
    expect(library.error, isNull);
    expect(library.catalog.length, 2);
    expect(library.catalog.first.data['profile'], descriptor['profile']);
    expect(library.catalog.first.data['source'], isNull);
    expect(library.catalog.last.data['source'], 'hf-discovery');
    await library.refresh();
    expect(library.error, contains('Catalog update failed'));
    expect(library.catalog.length, 2);
    expect(library.discovered, [official['repo']]);
  });
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
  test(
    'catalog filters old or remote entries with the same official policy',
    () {
      final library = ModelLibrary();
      library.readCatalog(
        jsonEncode({
          'version': 1,
          'models': [
            {...descriptor, 'repo': 'danish-foundation-models/MiMiR-GgUf'},
            {...descriptor, 'repo': 'noctrex/DFM-Mimir-GGUF'},
            {...descriptor, 'repo': 'danish-foundation-models/DFM-Mimir'},
            {...descriptor, 'repo': 'danish-foundation-models/DFM-GGUF'},
          ],
        }),
      );
      expect(
        library.catalog.single.data['repo'],
        'danish-foundation-models/MiMiR-GgUf',
      );
    },
  );
  test('stale discovery listings are filtered offline on restart', () async {
    final store = ChatStore(
      engine: FakeEngine(),
      directory: dir,
      manualStartup: true,
    );
    await store.initialize();
    final allowed = descriptor['repo'] as String;
    const excluded = 'noctrex/DFM-Mimir';
    store.library.readCatalog(
      jsonEncode({
        'version': 1,
        'models': [descriptor],
      }),
    );
    store.library.discovered = [
      allowed,
      excluded,
      'danish-foundation-models/Mimir',
    ];
    store.library.unavailable = [
      {'repo': allowed, 'file': 'split.gguf'},
      {'repo': excluded, 'file': 'split.gguf'},
    ];
    await store.save();
    await store.shutdown();
    final reopened = ChatStore(
      engine: FakeEngine(),
      directory: dir,
      manualStartup: true,
    );
    await reopened.initialize();
    expect(reopened.library.online, false);
    expect(reopened.library.discovered, [allowed]);
    expect(reopened.library.unavailable.single['repo'], allowed);
    expect(reopened.library.catalog.singleWhere((a) => a.id == descriptor['id']).data['repo'], allowed);
    await reopened.shutdown();
  });
  test('disallowed artifact cannot be downloaded directly', () async {
    final client = Client(Response(const Stream.empty(), 0));
    final library = ModelLibrary(clientFactory: () => client)..online = true;
    await library.download(
      ModelArtifact({...descriptor, 'repo': 'noctrex/DFM-Mimir'}),
    );
    expect(client.requests, 0);
    expect(library.error, contains('Only official'));
  });
  test('explicit IDs permit verified discovery and download, removal revokes access', () async {
    Response reply(Object data) {
      final body = utf8.encode(jsonEncode(data));
      return Response(Stream.value(body), body.length);
    }

    const repo = 'noctrex/DFM-Mimir';
    final client = Client(
      Response(Stream.value(bytes), bytes.length),
      responses: [
        reply({'version': 1, 'models': []}),
        reply([]),
        reply({'sha': 'a' * 40}),
        reply([
          {
            'type': 'file',
            'path': 'test.gguf',
            'size': bytes.length,
            'lfs': {'oid': descriptor['id']},
          },
        ]),
      ],
    );
    final library = ModelLibrary(clientFactory: () => client)..directory = dir;
    for (final invalid in [
      'https://huggingface.co/a/b',
      '../b',
      'a/b/c',
      'a',
      '',
    ]) {
      expect(
        () => library.setUserRepositories([invalid]),
        throwsFormatException,
      );
    }
    library.setUserRepositories([' $repo ', repo.toUpperCase()]);
    expect(library.userRepositories, [repo]);
    expect(library.online, false);
    library.setOnline(true);
    await library.refresh();
    expect(library.error, isNull);
    expect(client.requests, 4);
    final artifact = library.catalog.single;
    expect(artifact.data['qualification'], contains('User-specified'));
    expect(artifact.data['revision'], 'a' * 40);
    // The fake's response queue is no longer needed for the binary download.
    client.responses!.add(Response(Stream.value(bytes), bytes.length));
    await library.download(artifact);
    expect(library.error, isNull);
    expect(library.installed.single['id'], artifact.id);
    // A failed custom lookup retains its cached model even if official discovery succeeds.
    client.responses!.addAll([
      reply({'version': 1, 'models': []}),
      reply([]),
      reply({'sha': 'invalid'}),
    ]);
    await library.refresh();
    expect(library.error, contains(repo));
    expect(library.catalog.single.id, artifact.id);
    library.setUserRepositories([]);
    expect(library.catalog, isEmpty);
    expect(library.discovered, isEmpty);
    expect(library.installed, hasLength(1));
    final requests = client.requests;
    await library.download(artifact);
    expect(client.requests, requests);
    expect(library.error, contains('explicitly added'));
  });

  testWidgets('user can add and remove an HF ID without enabling networking', (
    tester,
  ) async {
    final store = ChatStore(
      engine: FakeEngine(),
      directory: dir,
      manualStartup: true,
    );
    await tester.runAsync(store.initialize);
    await tester.pumpWidget(MaterialApp(home: ModelLibraryView(store: store)));
    await tester.tap(find.byTooltip('Add HF repository'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'noctrex/DFM-Mimir');
    await tester.runAsync(() => tester.tap(find.text('Add')));
    await tester.pumpAndSettle();
    expect(store.library.userRepositories, ['noctrex/DFM-Mimir']);
    expect(store.library.online, false);
    expect(store.onlineFeedback, false);
    store.library.readCatalog(
      jsonEncode({
        'version': 1,
        'models': [
          {
            ...descriptor,
            'repo': 'noctrex/DFM-Mimir',
            'source': 'hf-discovery',
          },
        ],
      }),
    );
    await tester.runAsync(store.save);
    await tester.runAsync(store.shutdown);
    final reopened = ChatStore(
      engine: FakeEngine(),
      directory: dir,
      manualStartup: true,
    );
    await tester.runAsync(reopened.initialize);
    expect(reopened.library.userRepositories, ['noctrex/DFM-Mimir']);
    expect(reopened.library.catalog.singleWhere((a) => a.id == descriptor['id']).data['repo'], 'noctrex/DFM-Mimir');
    expect(reopened.library.online, false);
    await tester.pumpWidget(
      MaterialApp(home: ModelLibraryView(store: reopened)),
    );
    await tester.runAsync(
      () => tester.tap(find.byTooltip('Remove repository')),
    );
    await tester.pumpAndSettle();
    expect(reopened.library.userRepositories, isEmpty);
    await tester.runAsync(reopened.shutdown);
  });

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
