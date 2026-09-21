import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:dfm_mimir/feedback.dart';
import 'package:dfm_mimir/feedback_dialog.dart';
import 'package:dfm_mimir/models.dart';
import 'package:dfm_mimir/store.dart';
import 'package:dfm_mimir/chat_view.dart';

import 'widget_test.dart' show fixture, FakeEngine;

FeedbackSnapshot snapshot([Conversation? conversation]) => FeedbackSnapshot(
  conversation:
      conversation ??
      Conversation(
        modelID: 'model-sha',
        messages: [
          {'role': 'user', 'content': 'Hej'},
          {'role': 'assistant', 'content': 'Hej igen!'},
        ],
        memory: {'summary': 'Dansk summary', 'covered': 2},
      ),
  appVersion: 'test',
  contextTokens: 4096,
  replyTokens: 512,
  mixedLM: false,
);
String body(FeedbackDraft draft, {bool publication = true}) => draft.encode(
  snapshot(),
  rating: 'up',
  pseudonym: 'QuietOtter',
  comment: '',
  publication: publication,
);
void main() {
  test('snapshot is immutable and allowlists shared fields', () {
    final c = Conversation(
      id: 'local-id',
      title: 'private title',
      modelID: 'sha',
      messages: [
        {'role': 'user', 'content': 'original', 'private': 'secret'},
      ],
    );
    final s = snapshot(c);
    c.messages[0]['content'] = 'changed';
    final p = s.payload(
      id: 'receipt',
      rating: 'down',
      pseudonym: ' Name ',
      comment: '',
      publication: false,
    );
    expect(p['chat']['messages'][0], {'role': 'user', 'content': 'original'});
    expect(jsonEncode(p), isNot(contains('local-id')));
    expect(jsonEncode(p), isNot(contains('private')));
    expect(p['pseudonym'], 'Name');
    expect(p['consent'], {
      'improvement': true,
      'publication': false,
      'license': null,
    });
  });
  test('exact retries preserve ID; edits get new ID', () {
    final draft = FeedbackDraft();
    final first = body(draft);
    expect(body(draft), first);
    expect(
      jsonDecode(body(draft, publication: false))['id'],
      isNot(jsonDecode(first)['id']),
    );
  });
  test('pseudonym persists locally; online feedback starts disabled', () async {
    final dir = await Directory.systemTemp.createTemp('mimir-feedback-test');
    addTearDown(() => dir.delete(recursive: true));
    final identity = FeedbackIdentity(dir);
    final name = await identity.load();
    expect(await FeedbackIdentity(dir).load(), name);
    await identity.save('Custom Name');
    expect(await identity.load(), 'Custom Name');
    expect(FeedbackIdentity.generate(), isNot(name));
    expect(ChatStore(directory: dir).onlineFeedback, isFalse);
  });
  test('client requires HTTPS and limits payload', () async {
    expect(
      () => FeedbackClient(Uri.parse('http://example.org')),
      throwsArgumentError,
    );
    await expectLater(
      FeedbackClient(Uri.parse('https://example.org'))
          .submit(' ' * (feedbackMaxBytes + 1)),
      throwsA(isA<FeedbackFailure>()),
    );
  });
  test(
    'real HTTP client validates receipts, errors, redirects and timeouts',
    () async {
      final previousOverride = HttpOverrides.current;
      HttpOverrides.global = null;
      addTearDown(() => HttpOverrides.global = previousOverride);
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      addTearDown(() => server.close(force: true));
      int status = 201, count = 0;
      bool invalid = false, slow = false;
      server.listen((request) async {
        count++;
        final payload = jsonDecode(await utf8.decoder.bind(request).join());
        if (slow) {
          await Future<void>.delayed(const Duration(milliseconds: 800));
        }
        request.response.statusCode = status;
        if (status == 302) {
          request.response.headers.set(
            'location',
            'https://example.org/private',
          );
        }
        request.response.write(
          jsonEncode({
            'id': invalid ? 'wrong' : payload['id'],
            'receivedAt': 'now',
          }),
        );
        await request.response.close();
      });
      final client = FeedbackClient(
        Uri.parse('http://127.0.0.1:${server.port}/v1/feedback'),
        allowLoopback: true,
        timeout: const Duration(milliseconds: 500),
      );
      final json = body(FeedbackDraft());
      expect(await client.submit(json), jsonDecode(json)['id']);
      status = 200;
      expect(await client.submit(json), jsonDecode(json)['id']);
      for (final code in [400, 409, 413, 429, 503, 302]) {
        status = code;
        await expectLater(client.submit(json), throwsA(isA<FeedbackFailure>()));
      }
      expect(count, 8);
      status = 201;
      invalid = true;
      await expectLater(client.submit(json), throwsA(isA<FeedbackFailure>()));
      invalid = false;
      slow = true;
      await expectLater(client.submit(json), throwsA(isA<FeedbackFailure>()));
    },
  );
  testWidgets(
    'declining online permission leaves chat usable and preference off',
    (tester) async {
      final directory = Directory.systemTemp.createTempSync(
        'mimir-feedback-permission',
      );
      final store = fixture(FakeEngine(), directory, persist: false);
      store.active!.messages.addAll([
        {'role': 'user', 'content': 'Hej'},
        {'role': 'assistant', 'content': 'Hej!'},
      ]);
      await tester.pumpWidget(MaterialApp(home: ChatView(store: store)));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.byTooltip('Positive feedback'));
      await tester.tap(find.byTooltip('Positive feedback'));
      await tester.pumpAndSettle();
      expect(find.text('Allow online feedback?'), findsOneWidget);
      await tester.tap(find.text('Not now'));
      await tester.pumpAndSettle();
      expect(store.onlineFeedback, false);
      expect(find.byType(FeedbackDialog), findsNothing);
      await tester.enterText(
        find.byKey(const Key('composer')),
        'Continue offline',
      );
      await tester.pump();
      expect(store.canSend, true);
      await tester.pumpWidget(const SizedBox());
      await store.shutdown();
      directory.deleteSync(recursive: true);
    },
  );
  testWidgets('opening/cancelling sends nothing; publication defaults on', (
    tester,
  ) async {
    int sent = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => TextButton(
            onPressed: () => showDialog<void>(
              context: context,
              builder: (_) => FeedbackDialog(
                snapshot: snapshot(),
                rating: 'up',
                pseudonym: 'QuietOtter',
                savePseudonym: (_) async {},
                submit: (_) async {
                  sent++;
                  return 'receipt';
                },
              ),
            ),
            child: const Text('Open'),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    expect(
      tester.widget<CheckboxListTile>(find.byType(CheckboxListTile)).value,
      true,
    );
    expect(sent, 0);
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(sent, 0);
  });
  testWidgets('opt out, inspect summary, fail and retry exact payload', (
    tester,
  ) async {
    final sent = <String>[];
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: FeedbackDialog(
            snapshot: snapshot(),
            rating: 'down',
            pseudonym: 'QuietOtter',
            savePseudonym: (_) async {},
            submit: (payload) async {
              sent.add(payload);
              if (sent.length == 1) {
                throw const FeedbackFailure('Offline. Retry.');
              }
              return jsonDecode(payload)['id'];
            },
          ),
        ),
      ),
    );
    await tester.ensureVisible(find.byType(CheckboxListTile));
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Preview exact data to be shared'));
    await tester.tap(find.text('Preview exact data to be shared'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Dansk summary'), findsOneWidget);
    await tester.tap(find.text('Confirm and send'));
    await tester.pumpAndSettle();
    expect(sent.length, 1);
    expect(jsonDecode(sent.first)['consent']['publication'], false);
    expect(jsonDecode(sent.first)['consent']['license'], null);
    await tester.tap(find.text('Confirm and send'));
    await tester.pumpAndSettle();
    expect(sent.length, 2);
    expect(sent[0], sent[1]);
    expect(find.text('Thank you for your feedback'), findsOneWidget);
  });
}
