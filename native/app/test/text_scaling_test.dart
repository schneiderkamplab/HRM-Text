import 'dart:convert';
import 'dart:io';

import 'package:dfm_mimir/main.dart';
import 'package:dfm_mimir/settings_view.dart';
import 'package:dfm_mimir/store.dart';
import 'package:dfm_mimir/text_scaling.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'widget_test.dart' show FakeEngine;

class NonlinearScaler extends TextScaler {
  const NonlinearScaler();
  @override
  double scale(double size) => size + 5;
  @override
  double get textScaleFactor => 1.25;
}

class InitializedStore extends ChatStore {
  InitializedStore(Directory directory)
    : super(engine: FakeEngine(), directory: directory, manualStartup: true);
  Future<void> prepare() => super.initialize();
  @override
  Future<void> initialize() async {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('preserves system nonlinear scaling', () {
    const scaler = AppTextScaler(NonlinearScaler(), 1.5);
    expect(scaler.scale(10), 22.5);
    expect(scaler.scale(30), 52.5);
  });
  test('persists safely without inference work', () async {
    final directory = await Directory.systemTemp.createTemp('mimir-text-size');
    addTearDown(() => directory.delete(recursive: true));
    final engine = FakeEngine()
      ..handler = (_, _) => throw StateError('Native work');
    ChatStore create() =>
        ChatStore(engine: engine, directory: directory, manualStartup: true);
    final store = create();
    await store.initialize();
    expect(store.textScale, 1);
    store.generating = true;
    await store.setTextScale(1.5);
    for (final invalid in [double.nan, double.infinity, 0.5, 3.0]) {
      await store.setTextScale(invalid);
      expect(store.textScale, 1.5);
    }
    final restored = create();
    await restored.initialize();
    expect(restored.textScale, 1.5);
    final file = File('${directory.path}/conversations.json');
    final saved = jsonDecode(await file.readAsString()) as Map<String, dynamic>;
    for (final invalid in [null, 'huge', 10]) {
      saved['textScale'] = invalid;
      await file.writeAsString(jsonEncode(saved));
      final reopened = create();
      await reopened.initialize();
      expect(reopened.textScale, 1);
      expect(reopened.persistence, true);
    }
  });
  for (final width in [430.0, 1100.0]) {
    testWidgets('live composer and dialog scaling at width $width', (
      tester,
    ) async {
      final directory = Directory.systemTemp.createTempSync('mimir-scale-ui');
      addTearDown(() => directory.deleteSync(recursive: true));
      final store = InitializedStore(directory)..persistence = false;
      await tester.runAsync(store.prepare);
      await tester.binding.setSurfaceSize(Size(width, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      tester.platformDispatcher.textScaleFactorTestValue = 1.2;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      await tester.pumpWidget(MimirApp(store: store));
      await tester.pumpAndSettle();
      final composer = find.byKey(const Key('composer'));
      showDialog<void>(
        context: tester.element(composer),
        builder: (_) => SettingsView(store: store),
      );
      await tester.pumpAndSettle();
      final slider = find.byKey(const Key('text-size'));
      tester.widget<Slider>(slider).onChanged!(2);
      await tester.pumpAndSettle();
      expect(find.text('Text size · 200%'), findsOneWidget);
      expect(MediaQuery.textScalerOf(tester.element(slider)).scale(10), 24);
      expect(MediaQuery.textScalerOf(tester.element(composer)).scale(10), 24);
      expect(tester.takeException(), isNull);
      await tester.ensureVisible(find.text('Reset text size'));
      await tester.tap(find.text('Reset text size'));
      await tester.pumpAndSettle();
      expect(store.textScale, 1);
      expect(MediaQuery.textScalerOf(tester.element(slider)).scale(10), 12);
      await tester.pumpWidget(const SizedBox());
      await store.shutdown();
    });
  }
}
