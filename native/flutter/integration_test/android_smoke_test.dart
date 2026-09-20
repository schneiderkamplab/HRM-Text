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
      await store.shutdown();
      final archive = jsonDecode(
        await File('${directory.path}/conversations.json').readAsString(),
      );
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
