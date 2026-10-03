import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';

/// Rendering is local: model-authored images never fetch URLs or read files.
class MarkdownText extends StatelessWidget {
  final String content;
  const MarkdownText(this.content, {super.key});

  @override
  Widget build(BuildContext context) => MarkdownBody(
    data: content,
    selectable: true,
    fitContent: false,
    styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
      p: const TextStyle(fontSize: 15, height: 1.5),
      code: TextStyle(
        fontFamily: 'monospace',
        fontSize: 14,
        color: Theme.of(context).colorScheme.onSurface,
      ),
    ),
    imageBuilder: (uri, title, alt) =>
        Text('[Image: ${alt?.isNotEmpty == true ? alt : uri.toString()}]'),
    onTapLink: (text, href, title) {
      if (href == null) return;
      showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Link'),
          content: SelectableText(href),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close'),
            ),
            TextButton(
              onPressed: () async {
                await Clipboard.setData(ClipboardData(text: href));
                if (context.mounted) Navigator.pop(context);
              },
              child: const Text('Copy link'),
            ),
          ],
        ),
      );
    },
  );
}
