import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:dfm_mimir/search_view.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:dfm_mimir/search.dart';
import 'package:dfm_mimir/models.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const testKey = 'mimir_0123456789abcdef';
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));
  testWidgets('saved and edited keys are masked and can be revealed', (
    tester,
  ) async {
    FlutterSecureStorage.setMockInitialValues({searchCredentialName: testKey});
    final search = WebSearchController();
    Widget settings() => MaterialApp(
      home: Scaffold(
        body: SearchSettings(search: search, onChanged: () {}),
      ),
    );
    await tester.pumpWidget(settings());
    await tester.pumpAndSettle();
    TextField field() => tester.widget<TextField>(find.byType(TextField));
    expect(field().controller!.text, testKey);
    expect(field().obscureText, true);
    expect(field().obscuringCharacter, '*');
    await tester.tap(find.byTooltip('Show search key'));
    await tester.pump();
    expect(field().obscureText, false);
    const replacement = 'mimir_abcdef012345';
    await tester.enterText(find.byType(TextField), replacement);
    await tester.tap(find.byTooltip('Hide search key'));
    await tester.pump();
    expect(field().obscureText, true);
    expect(field().controller!.text, replacement);
    await tester.tap(find.text('Save search key'));
    await tester.pumpAndSettle();
    expect(field().controller!.text, replacement);
    expect(field().obscureText, true);
    await tester.tap(find.byTooltip('Show search key'));
    await tester.pump();
    expect(field().obscureText, false);
    await tester.pumpWidget(const SizedBox());
    await tester.pumpWidget(settings());
    await tester.pumpAndSettle();
    expect(field().controller!.text, replacement);
    expect(field().obscureText, true);
    await tester.tap(find.text('Forget search key'));
    await tester.pumpAndSettle();
    expect(field().controller!.text, isEmpty);
    expect(search.configured, false);
  });
  test('stock prompt upgrades but custom prompts survive', () {
    final data = jsonDecode(
      File('assets/profile.json').readAsStringSync(),
    ) as Map<String, dynamic>;
    expect(data['systemPrompt'], ModelProfile.defaultSystemPrompt);
    data['systemPrompt'] = ModelProfile.defaultSystemPrompt.replaceFirst(
      'research collaboration',
      'collaboration',
    );
    expect(
      ModelProfile(data).data['systemPrompt'],
      contains('research collaboration'),
    );
    data['systemPrompt'] = 'Custom research assistant';
    expect(
      ModelProfile(data).data['systemPrompt'],
      'Custom research assistant',
    );
  });
  test('key is separate, can be session-only, remembered, forgotten', () async {
    final s = WebSearchController();
    expect(s.enabled, false);
    await s.setKey(testKey, remember: false);
    final other = WebSearchController();
    await other.load();
    expect(other.configured, false);
    expect(s.configured, true);
    await s.setKey(testKey, remember: true);
    final reloaded = WebSearchController();
    await reloaded.load();
    expect(reloaded.configured, true);
    await s.setKey('', remember: false);
    final forgotten = WebSearchController();
    await forgotten.load();
    expect(forgotten.configured, false);
    await expectLater(
      s.setKey('jina_wrong', remember: true),
      throwsFormatException,
    );
  });
  test('network requires opt-in, query only, auth header, no redirects; disable cancels', () async {
    final old = HttpOverrides.current;
    HttpOverrides.global = null;
    addTearDown(() => HttpOverrides.global = old);
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    addTearDown(() => server.close(force: true));
    int calls = 0, status = 200;
    bool slow = false;
    final started = Completer<void>();
    server.listen((request) async {
      calls++;
      expect(request.headers.value('authorization'), 'Bearer $testKey');
      expect(jsonDecode(await utf8.decoder.bind(request).join()), {
        'query': 'Danish models',
      });
      if (slow) {
        started.complete();
        return;
      }
      request.response.statusCode = status;
      request.response.headers.set('location', 'https://example.com/');
      request.response.write(
        jsonEncode({
          'results': [
            {
              'title': 'DFM',
              'url': 'https://example.com',
              'description': 'Research',
            },
          ],
        }),
      );
      await request.response.close();
    });
    final s = WebSearchController(
      endpoint: Uri.parse('http://127.0.0.1:${server.port}'),
    );
    await s.setKey(testKey, remember: false);
    await expectLater(s.search('Danish models'), throwsStateError);
    expect(calls, 0);
    s.setEnabled(true);
    expect((await s.search('Danish models')).single['title'], 'DFM');
    for (final code in [401, 429, 503, 302]) {
      status = code;
      await expectLater(s.search('Danish models'), throwsStateError);
    }
    expect(calls, 5);
    status = 200;
    slow = true;
    final request = s.search('Danish models');
    final check = expectLater(request, throwsStateError);
    await started.future;
    s.setEnabled(false);
    await check;
    expect(s.busy, false);
  });
}
