import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:dfm_mimir/chat_view.dart';
import 'package:dfm_mimir/models.dart';

import 'widget_test.dart' show FakeEngine, fixture;

void main() {
  test('shortened prompt commits metadata, preserves original and rolls back cancellation', () async {
    final directory = await Directory.systemTemp.createTemp('mimir-prompt');
    final engine = FakeEngine();
    final store = fixture(engine, directory);
    var stop = false;
    try {
      store.showSummary = true;
      engine.handler = (command, event) async {
        if (command['op'] == 'count') {
          return [
            {'type': 'count', 'tokens': 50},
          ];
        }
        event!({'type': 'compacting'});
        event({'type': 'promptSummary', 'text': 'Shortened request'});
        expect(store.compacting, isTrue);
        expect(store.visibleSummary?['prompt'], isTrue);
        expect(store.visibleSummary?['summary'], 'Shortened request');
        event({'type': 'prepared', 'tokens': 50});
        return [
          {
            'type': 'reply',
            'text': 'Answer',
            'cancelled': stop,
            'compactedPrompt': 'Shortened request',
          },
        ];
      };
      store.updateDraft('Original long request');
      await store.send();
      expect(store.messages.first['content'], 'Original long request');
      expect(store.messages.first['compactedContent'], 'Shortened request');
      expect(store.notice, contains('shortened'));
      expect(store.preview, isNull);
      final saved = jsonDecode(
        await File('${directory.path}/conversations.json').readAsString(),
      );
      final restored = Conversation.fromJson(
        Map<String, dynamic>.from(saved['chats'][0]),
      );
      expect(restored.messages.first['compactedContent'], 'Shortened request');
      stop = true;
      store.updateDraft('Another long request');
      await store.send();
      expect(store.messages.length, 2);
      expect(store.draft, 'Another long request');
      expect(store.preview, isNull);
      restored.messages.first['compactedContent'] = '';
      expect(
        () => Conversation.fromJson(restored.toJson()),
        throwsFormatException,
      );
    } finally {
      await store.shutdown();
      await directory.delete(recursive: true);
    }
  });
  testWidgets('shortened prompt follows summary visibility setting', (
    tester,
  ) async {
    final directory = Directory.systemTemp.createTempSync('mimir-prompt-ui');
    final store = fixture(FakeEngine(), directory, persist: false);
    store.messages.addAll([
      {'role': 'user', 'content': 'Original', 'compactedContent': 'Shortened'},
      {'role': 'assistant', 'content': 'Answer'},
    ]);
    store.showSummary = true;
    await tester.pumpWidget(MaterialApp(home: ChatView(store: store)));
    expect(find.text('Original'), findsOneWidget);
    expect(find.text('Shortened prompt used for generation'), findsOneWidget);
    await tester.tap(find.text('Shortened prompt used for generation'));
    await tester.pumpAndSettle();
    expect(find.text('Shortened'), findsOneWidget);
    store.setCompaction(visible: false);
    await tester.pumpAndSettle();
    expect(find.text('Shortened prompt used for generation'), findsNothing);
    expect(find.text('Original'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    await store.shutdown();
    directory.deleteSync(recursive: true);
  });
}
