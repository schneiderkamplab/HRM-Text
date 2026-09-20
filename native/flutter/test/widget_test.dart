import 'dart:io';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mimir_flutter/chat_view.dart';
import 'package:mimir_flutter/engine.dart';
import 'package:mimir_flutter/models.dart';
import 'package:mimir_flutter/store.dart';

class FakeEngine implements InferenceEngine {
  bool stopped = false, closed = false;
  Future<List<Json>> Function(Json, void Function(Json)?)? handler;
  @override
  Future<List<Json>> command(Json c, {void Function(Json)? onEvent}) async {
    if (handler != null) return handler!(c, onEvent);
    return c['op'] == 'count'
        ? [
            {'type': 'count', 'tokens': 42},
          ]
        : [];
  }

  @override
  void cancel() {
    stopped = true;
  }

  @override
  Future<void> close() async {
    closed = true;
  }
}

ChatStore fixture(FakeEngine e, Directory directory, {bool persist = true}) {
  final s = ChatStore(engine: e, directory: directory);
  s.profile = ModelProfile(
    Map<String, dynamic>.from(
      jsonDecode(File('assets/profile.json').readAsStringSync()),
    ),
  );
  s.persistence = persist;
  s.initialized = true;
  s.conversationsReady = true;
  s.ready = true;
  s.model = {'id': 'model', 'path': 'fake', 'name': 'Test Mimir'};
  s.newChat();
  return s;
}

void main() {
  test(
    'load exposes actual fallback backend and keeps explicit limits',
    () async {
      final directory = await Directory.systemTemp.createTemp(
        'mimir-backend-test',
      );
      final e = FakeEngine();
      final s = fixture(e, directory);
      try {
        final model = File('${directory.path}/model.gguf');
        await model.writeAsBytes([0]);
        s.model!['path'] = model.path;
        s.automatic = false;
        s.context = 2048;
        e.handler = (command, _) async {
          if (command['op'] == 'count') {
            return [
              {'type': 'count', 'tokens': 42},
            ];
          }
          expect(command['device'], 'auto');
          expect(command['context'], 2048);
          return [
            {
              'type': 'loaded',
              'device': 'CPU',
              'backend': 'CPU',
              'context': 2048,
              'trainingContext': 4096,
              'fallbackReasons': ['CUDA0: allocation failed'],
            },
          ];
        };
        await s.load();
        expect(s.ready, isTrue);
        expect(s.context, 2048);
        expect(s.engineLabel, contains('CPU'));
        expect(s.backendFallbackReasons.single, contains('CUDA0'));
      } finally {
        await s.shutdown();
        await directory.delete(recursive: true);
      }
    },
  );
  test('profile bounds and future model settings', () {
    final data = Map<String, dynamic>.from(
      jsonDecode(File('assets/profile.json').readAsStringSync()),
    );
    final p = ModelProfile(data);
    expect(p.limitsError(32768, 512), isNull);
    expect(p.limitsError(32769, 512), isNotNull);
    data['minimumContext'] = 2048;
    data['maximumContext'] = 65536;
    data['contextTiers'] = [2048, 65536];
    expect(ModelProfile(data).limitsError(65536, 4096), isNull);
  });
  test('streamed summary, successful commit, cancellation rollback and archive position', () async {
    final directory = await Directory.systemTemp.createTemp(
      'mimir-flutter-test',
    );
    final e = FakeEngine();
    final s = fixture(e, directory);
    try {
      s.active!.messages.addAll([
        {'role': 'user', 'content': 'Odense'},
        {'role': 'assistant', 'content': 'OK'},
      ]);
      s.showSummary = true;
      e.handler = (c, event) async {
        if (c['op'] == 'count') {
          return [
            {'type': 'count', 'tokens': 42},
          ];
        }
        event!({'type': 'compacting'});
        expect(s.compacting, isTrue);
        event({'type': 'summary', 'text': 'Partial', 'covered': 2});
        expect(s.visibleSummary?['summary'], 'Partial');
        expect(s.summaryPosition, 2);
        event({'type': 'prepared', 'tokens': 123});
        expect(s.compacting, isFalse);
        expect(s.used, 123);
        event({'type': 'token', 'text': 'Answer'});
        return [
          {
            'type': 'reply',
            'text': 'Answer',
            'cancelled': false,
            'limited': false,
            'memory': {'summary': 'Odense itinerary', 'covered': 2},
          },
        ];
      };
      s.updateDraft('Where?');
      await s.send();
      expect(s.messages.length, 4);
      expect(s.preview, isNull);
      expect(s.active!.memory?['position'], 2);
      final file = File('${directory.path}/conversations.json');
      final archive = jsonDecode(await file.readAsString());
      expect(
        Conversation.fromJson(Map<String, dynamic>.from(archive['chats'][0]))
            .memory?['position'],
        2,
      );
      e.handler = (c, event) async {
        if (c['op'] == 'count') {
          return [
            {'type': 'count', 'tokens': 42},
          ];
        }
        event!({'type': 'summary', 'text': 'Discard', 'covered': 4});
        s.stop();
        return [
          {'type': 'reply', 'cancelled': true},
        ];
      };
      s.updateDraft('Continue');
      await s.send();
      expect(e.stopped, isTrue);
      expect(s.messages.length, 4);
      expect(s.draft, 'Continue');
      expect(s.active!.memory?['summary'], 'Odense itinerary');
      s.setCompaction(visible: false);
      expect(s.visibleSummary, isNull);
      await s.shutdown();
    } finally {
      await directory.delete(recursive: true);
    }
  });
  test('first send preserves prompt when no conversation exists', () async {
    final d = Directory.systemTemp.createTempSync('mimir-first-send');
    final e = FakeEngine();
    final s = fixture(e, d, persist: false);
    s.chats.clear();
    s.selected = null;
    e.handler = (c, event) async {
      if (c['op'] == 'count') {
        return [
          {'type': 'count', 'tokens': 42},
        ];
      }
      expect(c['prompt'], 'First message');
      return [
        {
          'type': 'reply',
          'text': 'Hello',
          'cancelled': false,
          'limited': false,
        },
      ];
    };
    s.updateDraft('First message');
    await s.send();
    expect(s.active!.title, 'First message');
    expect(s.messages.first['content'], 'First message');
    await s.shutdown();
    d.deleteSync(recursive: true);
  });
  testWidgets(
    'new chat is available during model loading, after archive restore',
    (tester) async {
      final d = Directory.systemTemp.createTempSync('mimir-startup');
      final s = fixture(FakeEngine(), d, persist: false);
      s.loading = true;
      s.ready = false;
      s.conversationsReady = false;
      await tester.binding.setSurfaceSize(const Size(1100, 800));
      await tester.pumpWidget(MaterialApp(home: ChatView(store: s)));
      final toolbar = find.byWidgetPredicate(
        (w) => w is IconButton && w.tooltip == 'New chat',
      );
      expect(tester.widget<IconButton>(toolbar).onPressed, isNull);
      s.newChat();
      expect(s.chats.length, 1);
      s.conversationsReady = true;
      s.updateDraft('');
      await tester.pump();
      await tester.tap(toolbar);
      await tester.pump();
      expect(s.chats.length, 2);
      final selected = s.selected;
      await tester.tap(find.widgetWithText(FilledButton, 'New chat'));
      await tester.pump();
      expect(s.chats.length, 3);
      expect(s.selected, isNot(selected));
      await tester.enterText(
        find.byKey(const Key('composer')),
        'Draft while loading',
      );
      expect(s.draft, 'Draft while loading');
      expect(s.canSend, isFalse);
      s.loading = false;
      s.ready = true;
      expect(s.canSend, isTrue);
      s.generating = true;
      expect(s.canCreateChat, isFalse);
      s.generating = false;
      await tester.pumpWidget(const SizedBox());
      await s.shutdown();
      await tester.runAsync(() async {
        await d.delete(recursive: true);
      });
      await tester.binding.setSurfaceSize(null);
    },
  );
  testWidgets('iOS swipes over message text scroll the transcript', (
    tester,
  ) async {
    final d = Directory.systemTemp.createTempSync('mimir-ios-scroll');
    final s = fixture(FakeEngine(), d, persist: false);
    s.active!.messages.addAll([
      {'role': 'user', 'content': 'A long answer please'},
      {
        'role': 'assistant',
        'content': List.generate(
          70,
          (i) => 'Line $i of the answer.',
        ).join('\n'),
      },
    ]);
    await tester.binding.setSurfaceSize(const Size(430, 800));
    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData(platform: TargetPlatform.iOS),
        home: ChatView(store: s),
      ),
    );
    await tester.pump();
    final transcript = tester.widget<SingleChildScrollView>(
      find.byType(SingleChildScrollView),
    );
    expect(transcript.controller!.position.maxScrollExtent, greaterThan(200));
    await tester.dragFrom(const Offset(150, 350), const Offset(0, -220));
    await tester.pumpAndSettle();
    expect(transcript.controller!.offset, greaterThan(100));
    await tester.pumpWidget(const SizedBox());
    await s.shutdown();
    await tester.runAsync(() async {
      await d.delete(recursive: true);
    });
    await tester.binding.setSurfaceSize(null);
  });
  testWidgets('sidebar identity, branding and composer send', (tester) async {
    final directory = Directory.systemTemp.createTempSync(
      'mimir-flutter-widget',
    );
    final e = FakeEngine();
    final s = fixture(e, directory, persist: false);
    await tester.binding.setSurfaceSize(const Size(1100, 800));
    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData(platform: TargetPlatform.macOS),
        home: ChatView(store: s),
      ),
    );
    await tester.pump();
    expect(find.text('New chat'), findsWidgets);
    expect(find.text('DFM Mimir'), findsWidgets);
    await tester.enterText(find.byKey(const Key('composer')), 'Hello');
    await tester.pump();
    expect(s.canSend, isTrue);
    expect(find.byTooltip('Send message'), findsOneWidget);
    e.handler = (c, event) async => c['op'] == 'count'
        ? [
            {'type': 'count', 'tokens': 42},
          ]
        : [
            {
              'type': 'reply',
              'text': 'Hello back',
              'cancelled': false,
              'limited': false,
            },
          ];
    await tester.sendKeyDownEvent(LogicalKeyboardKey.shiftLeft);
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.shiftLeft);
    await tester.pump();
    expect(s.messages, isEmpty);
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pump();
    expect(s.messages.length, 2);
    expect(find.text('Hello back'), findsOneWidget);
    s.newChat();
    await tester.pump();
    expect(s.chats.length, 2);
    expect(s.active!.messages, isEmpty);
    await tester.pumpWidget(const SizedBox());
    await s.shutdown();
    await tester.runAsync(() async {
      await directory.delete(recursive: true);
    });
    await tester.binding.setSurfaceSize(null);
  });
}
