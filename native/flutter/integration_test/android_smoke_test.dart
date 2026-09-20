import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:mimir_flutter/main.dart';
import 'package:mimir_flutter/store.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Android bundled model generates a templated reply', (
    tester,
  ) async {
    // A separate archive leaves the user's conversations untouched.
    final directory = await Directory.systemTemp.createTemp('mimir-smoke-');
    final store = ChatStore(directory: directory);
    try {
      await tester.pumpWidget(MimirApp(store: store));
      for (var i = 0; i < 180 && !store.ready; i++) {
        await tester.pump(const Duration(seconds: 1));
        if (store.initialized && !store.loading && store.notice != null) break;
      }
      expect(store.ready, isTrue, reason: store.notice);
      expect(store.mixedLM, isFalse);
      expect(store.context, greaterThanOrEqualTo(1024));
      await tester.enterText(
        find.byKey(const Key('composer')),
        'Svar kun med tallet: Hvad er 2 + 2?',
      );
      await tester.pump();
      await tester.tap(find.byTooltip('Send message'));
      for (var i = 0; i < 180 && store.messages.length < 2; i++) {
        await tester.pump(const Duration(seconds: 1));
        if (!store.generating && store.notice != null) break;
      }
      expect(store.messages.length, 2, reason: store.notice);
      expect(store.messages.last['content'], contains('4'));
      expect(store.used, isNotNull);
      expect(store.lastReusedTokens, 0);
      Future<void> toggleMixed() async {
        await tester.tap(find.byTooltip('Model and settings'));
        await tester.pumpAndSettle();
        final toggle = find.byKey(const Key('mixed-lm-setting'));
        await tester.ensureVisible(toggle);
        await tester.tap(toggle);
        for (var i = 0; i < 180 && !store.ready; i++) {
          await tester.pump(const Duration(seconds: 1));
          if (!store.loading && store.notice != null) break;
        }
        expect(store.ready, isTrue, reason: store.notice);
        await tester.tap(find.text('Done'));
        await tester.pumpAndSettle();
      }

      Future<void> send(String prompt) async {
        final count = store.messages.length;
        // Re-establish the platform text-input connection after closing settings.
        await tester.tap(find.byKey(const Key('composer')));
        await tester.pumpAndSettle();
        await tester.enterText(find.byKey(const Key('composer')), prompt);
        await tester.pumpAndSettle();
        expect(
          store.canSend,
          isTrue,
          reason:
              'ready=${store.ready}, busy=${store.busy}, draft=${store.draft}, notice=${store.notice}',
        );
        await tester.tap(find.byTooltip('Send message'));
        await tester.pump();
        expect(
          store.generating || store.messages.length == count + 2,
          isTrue,
          reason: store.notice,
        );
        for (var i = 0; i < 180 && store.messages.length == count; i++) {
          await tester.pump(const Duration(seconds: 1));
          if (!store.generating && store.notice != null) break;
        }
        expect(
          store.messages.length,
          count + 2,
          reason:
              'generating=${store.generating}, streaming=${store.streaming}, notice=${store.notice}',
        );
      }

      await toggleMixed();
      expect(store.mixedLM, isTrue);
      await store.save();
      expect(
        jsonDecode(
          await File('${directory.path}/conversations.json').readAsString(),
        )['mixedLM'],
        isTrue,
      );
      await send('Svar kort: Hvad er 3 + 3?');
      expect(
        store.lastReusedTokens,
        0,
      ); // First request after context replacement.
      await send('Svar kort: Hvad er 4 + 4?');
      expect(store.lastReusedTokens, greaterThan(0));
      await toggleMixed();
      expect(store.mixedLM, isFalse);
      await send('Svar kun med tallet: Hvad er 2 + 2?');
      expect(store.lastReusedTokens, 0);
      expect(store.messages.last['content'], contains('4'));
      await store.shutdown();
      final archive = jsonDecode(
        await File('${directory.path}/conversations.json').readAsString(),
      );
      expect(archive['mixedLM'], isFalse);
      expect(
        archive['chats'].single['messages'].last['content'],
        contains('4'),
      );
    } finally {
      await tester.pumpWidget(const SizedBox());
      await store.shutdown();
      await directory.delete(recursive: true);
    }
  });
}
