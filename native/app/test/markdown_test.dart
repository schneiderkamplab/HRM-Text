import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
import 'package:dfm_mimir/chat_widgets.dart';
import 'package:dfm_mimir/markdown_text.dart';

Widget page(Widget child) => MaterialApp(
  home: Scaffold(
    body: SingleChildScrollView(child: SizedBox(width: 320, child: child)),
  ),
);

void main() {
  testWidgets('assistant markdown supports basic blocks on narrow layouts', (
    tester,
  ) async {
    await tester.pumpWidget(
      page(
        const ChatMessage(
          role: 'assistant',
          content: '# Heading\n\n**Bold** and *italic* with `code`.\n\n- First\n- Second\n\n1. One\n2. Two\n\n> Quote\n\n```dart\nprint("Hej");\n```',
        ),
      ),
    );
    expect(find.byType(MarkdownBody), findsOneWidget);
    expect(find.text('Heading', findRichText: true), findsOneWidget);
    expect(find.text('First', findRichText: true), findsOneWidget);
    expect(tester.takeException(), isNull);
    final body = tester.widget<MarkdownBody>(find.byType(MarkdownBody));
    expect(body.selectable, true);
  });

  testWidgets(
    'user text stays literal; streamed unfinished markup tolerates updates',
    (tester) async {
      await tester.pumpWidget(
        page(const ChatMessage(role: 'user', content: '**literal**')),
      );
      expect(find.byType(MarkdownBody), findsNothing);
      expect(find.text('**literal**'), findsOneWidget);
      for (final text in [
        '**He',
        '**Hej**\n\n```',
        '**Hej**\n\n```text\nhello\n```',
      ]) {
        await tester.pumpWidget(
          page(ChatMessage(role: 'assistant', content: text)),
        );
        expect(find.byType(MarkdownBody), findsOneWidget);
        expect(tester.takeException(), isNull);
      }
    },
  );

  testWidgets('images stay local placeholders and links reveal their target', (
    tester,
  ) async {
    await tester.pumpWidget(
      page(
        const MarkdownText(
          '![Remote](https://example.invalid/track.png)\n\n![Local](file:///private/test.png)\n\n[Example](https://example.invalid)',
        ),
      ),
    );
    expect(find.byType(Image), findsNothing);
    expect(find.text('[Image: Remote]'), findsOneWidget);
    expect(find.text('[Image: Local]'), findsOneWidget);
    // Invoke the same handler used by selectable rich-text links.
    tester.widget<MarkdownBody>(find.byType(MarkdownBody)).onTapLink!(
      'Example',
      'https://example.invalid',
      '',
    );
    await tester.pumpAndSettle();
    expect(find.text('https://example.invalid'), findsOneWidget);
    expect(find.text('Copy link'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
