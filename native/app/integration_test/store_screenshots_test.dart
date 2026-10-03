import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:dfm_mimir/main.dart';
import 'package:dfm_mimir/store.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

// Real inference and production widgets; no personal chats or capture overlays.
void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('capture store screenshots with real local answers', (
    tester,
  ) async {
    final directory = await Directory.systemTemp.createTemp(
      'mimir-store-capture-',
    );
    final store = ChatStore(directory: directory);
    final boundary = GlobalKey();
    final captures = <String, String>{};
    binding.reportData = {'captures': captures};
    if (Platform.isMacOS) {
      tester.view.devicePixelRatio = 2;
      tester.view.physicalSize = const Size(2560, 1600);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetPhysicalSize);
    }
    Future<void> waitUntil(bool Function() done) async {
      for (var i = 0; i < 600 && !done(); i++) {
        await tester.pump(const Duration(seconds: 1));
        if (i % 30 == 0) {
          debugPrint(
            "capture waiting: ready=${store.ready} busy=${store.busy} notice=${store.notice}",
          );
        }
      }
      expect(done(), isTrue, reason: store.notice);
    }

    Future<void> capture(String name) async {
      debugPrint('capture: $name');
      FocusManager.instance.primaryFocus?.unfocus();
      // Native keyboard dismissal can finish after Flutter's animations settle.
      await tester.pump(const Duration(seconds: 1));
      await binding.reassembleApplication();
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      if (Platform.isIOS) {
        captures[name] = base64Encode(await binding.takeScreenshot(name));
        binding.reportData!.remove('screenshots');
        return;
      }
      final render =
          boundary.currentContext!.findRenderObject()! as RenderRepaintBoundary;
      final image = await render.toImage(
        pixelRatio: tester.view.devicePixelRatio,
      );
      try {
        final bytes = (await image.toByteData(format: ui.ImageByteFormat.png))!;
        captures[name] = base64Encode(bytes.buffer.asUint8List());
      } finally {
        image.dispose();
      }
    }

    Future<void> chat(String prompt, String name) async {
      store.newChat();
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('composer')));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('composer')), prompt);
      await tester.pump();
      expect(
        store.canSend,
        isTrue,
        reason: 'draft=${store.draft}; notice=${store.notice}',
      );
      await tester.tap(find.byTooltip('Send message'));
      await tester.pump();
      await waitUntil(() => !store.busy && store.messages.length == 2);
      expect(store.messages.last['content'].toString().trim(), isNotEmpty);
      await capture(name);
    }

    try {
      await tester.pumpWidget(
        RepaintBoundary(
          key: boundary,
          child: MimirApp(store: store),
        ),
      );
      await waitUntil(() => store.ready);
      expect(store.library.online, isFalse);
      expect(store.search.enabled, isFalse);
      expect(store.onlineFeedback, isFalse);
      await capture('01-welcome');
      await chat('Giv mig tre korte idéer til en gåtur.', '02-danish');
      await chat(
        'Answer in English. Give me three short tips for writing a clear email.',
        '03-english',
      );
      await tester.tap(find.byTooltip('Model and settings'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Appearance'));
      await capture('04-appearance');
      binding.reportData!['platform'] = Platform.operatingSystem;
      binding.reportData!['dimensions'] = [
        tester.view.physicalSize.width,
        tester.view.physicalSize.height,
      ];
      binding.reportData!['model'] = store.model;
      binding.reportData!['backend'] = store.actualBackend;
    } finally {
      await tester.pumpWidget(const SizedBox());
      await store.shutdown();
      await directory.delete(recursive: true);
    }
  }, timeout: const Timeout(Duration(minutes: 30)));
}
