import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:dfm_mimir/store.dart';
import 'package:dfm_mimir/settings_view.dart';

import 'widget_test.dart' show FakeEngine;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('model status describes actual backend and load state', () {
    final store = ChatStore(engine: FakeEngine());
    expect(store.modelStatus, 'Not loaded');
    store.loading = true;
    expect(store.modelStatus, 'Loading model…');
    store.loading = false;
    store.ready = true;
    store.actualBackend = 'Metal';
    expect(store.modelStatus, 'Loaded with acceleration (Apple Metal)');
    store.actualBackend = 'CPU';
    expect(store.modelStatus, 'Loaded on CPU');
    store.ready = false;
    expect(store.modelStatus, 'Not loaded');
  });
  test('Android startup does no native work and replaces unsafe automatic defaults', () async {
    final directory = await Directory.systemTemp.createTemp('mimir-startup');
    addTearDown(() => directory.delete(recursive: true));
    final engine = FakeEngine();
    var nativeCalls = 0;
    engine.handler = (_, _) {
      nativeCalls++;
      throw StateError('Startup must not enter native code');
    };
    await File('${directory.path}/conversations.json').writeAsString(
      jsonEncode({
        'version': 1,
        'chats': [],
        'automatic': true,
        'device': 'auto',
        'context': 32768,
        'reply': 8192,
      }),
    );
    final store = ChatStore(
      engine: engine,
      directory: directory,
      manualStartup: true,
    );
    await store.initialize();
    expect(store.initialized, true);
    expect(store.loading, false);
    expect(store.ready, false);
    expect(store.device, 'cpu');
    expect(store.context, 1024);
    expect(store.reply, 512);
    expect(store.automatic, false);
    await store.setLimits(2048, 512, backend: 'vulkan');
    expect(store.context, 2048);
    expect(store.device, 'vulkan');
    expect(store.ready, false);
    final saved = jsonDecode(
      await File('${directory.path}/conversations.json').readAsString(),
    );
    expect(saved['device'], 'vulkan');
    expect(saved['context'], 2048);
    final reopened = ChatStore(
      engine: engine,
      directory: directory,
      manualStartup: true,
    );
    await reopened.initialize();
    expect(reopened.device, 'vulkan');
    expect(reopened.loading, false);
    expect(reopened.ready, false);
    final imported = File('${directory.path}/import.gguf');
    await imported.writeAsBytes([0]);
    await reopened.importModel(imported.path);
    await reopened.setMixedLM(true);
    expect(reopened.mixedLM, true);
    expect(nativeCalls, 0);
  });
  test('explicit load preserves limits and backend switch cannot reenter a live driver', () async {
    final directory = await Directory.systemTemp.createTemp('mimir-load');
    addTearDown(() => directory.delete(recursive: true));
    final engine = FakeEngine();
    final calls = <Map<String, dynamic>>[];
    final store = ChatStore(
      engine: engine,
      directory: directory,
      manualStartup: true,
    );
    await store.initialize();
    final model = File('${directory.path}/test.gguf');
    await model.writeAsBytes([0]);
    store.model = {'id': 'test', 'path': model.path, 'bundled': false};
    engine.handler = (command, _) async {
      calls.add(command);
      if (command['op'] == 'count') {
        return [
          {'type': 'count', 'tokens': 0},
        ];
      }
      final saved = jsonDecode(
        await File('${directory.path}/conversations.json').readAsString(),
      );
      expect(saved['device'], 'cpu');
      expect(saved['context'], 1024);
      return [
        {
          'type': 'loaded',
          'context': 1024,
          'trainingContext': 4096,
          'device': 'CPU',
          'backend': 'CPU',
        },
      ];
    };
    await store.startModel();
    expect(store.ready, true);
    expect(calls.first['context'], 1024);
    expect(calls.first['device'], 'cpu');
    final previous = calls.length;
    await store.setLimits(2048, 512, backend: 'vulkan');
    expect(calls.length, previous);
    expect(store.ready, false);
    expect(store.notice, contains('Force-stop'));
  });
  testWidgets(
    'settings remain editable before model preparation; Load is explicit',
    (tester) async {
      final directory = Directory.systemTemp.createTempSync('mimir-startup-ui');
      final engine = FakeEngine();
      engine.handler = (_, _) => throw StateError('Unexpected native work');
      final store = ChatStore(
        engine: engine,
        directory: directory,
        manualStartup: true,
      );
      // Persistence is covered by the non-widget tests above. Avoid real file
      // writes on the widget test's fake clock (Windows retains open handles).
      store.persistence = false;
      addTearDown(() => directory.deleteSync(recursive: true));
      await tester.runAsync(store.initialize);
      await tester.binding.setSurfaceSize(const Size(430, 850));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: SettingsView(store: store)),
        ),
      );
      expect(find.text('Load model'), findsOneWidget);
      expect(find.byKey(const Key('text-size')), findsNothing);
      final contextDraft = find.widgetWithText(TextField, 'Context tokens');
      await tester.ensureVisible(contextDraft);
      await tester.enterText(contextDraft, '3072');
      await tester.ensureVisible(find.text('Online'));
      await tester.tap(find.text('Online'));
      await tester.pumpAndSettle();
      expect(find.text('Allow online feedback'), findsOneWidget);
      expect(find.text('Load model'), findsNothing);
      await tester.tap(find.text('Appearance'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('text-size')), findsOneWidget);
      expect(find.text('Show compaction summary in chat'), findsNothing);
      await tester.ensureVisible(find.text('Advanced'));
      await tester.tap(find.text('Advanced'));
      await tester.pumpAndSettle();
      expect(find.text('Automatically compact context'), findsOneWidget);
      expect(find.text('Show compaction summary in chat'), findsOneWidget);
      expect(find.text('Selected profile'), findsOneWidget);
      expect(find.text('Import model profile…'), findsNothing);
      expect(find.byKey(const Key('mixed-lm-setting')), findsNothing);
      store.setCompaction(visible: true);
      store.setCompaction(enabled: false);
      await tester.pumpAndSettle();
      expect(find.text('Show compaction summary in chat'), findsNothing);
      expect(store.showSummary, true);
      store.setCompaction(enabled: true);
      await tester.pumpAndSettle();
      expect(find.text('Show compaction summary in chat'), findsOneWidget);
      expect(find.text('Allow online feedback'), findsNothing);
      await tester.ensureVisible(find.text('Model'));
      await tester.tap(find.text('Model'));
      await tester.pumpAndSettle();
      expect(tester.widget<TextField>(contextDraft).controller!.text, '3072');
      expect(find.text('Use memory-based defaults'), findsNothing);
      final contextField = find.widgetWithText(TextField, 'Context tokens');
      await tester.ensureVisible(contextField);
      await tester.enterText(contextField, '2048');
      await tester.ensureVisible(find.text('Apply limits'));
      await tester.tap(find.text('Apply limits'));
      await tester.pumpAndSettle();
      expect(store.context, 2048);
      expect(store.ready, false);
      await tester.pumpWidget(const SizedBox());
      await store.shutdown();
    },
  );
}
